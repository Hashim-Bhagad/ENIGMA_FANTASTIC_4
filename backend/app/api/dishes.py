"""Cooked-dish assessment endpoints.

Dish assessments reuse the ``Assessment`` record so history and detail lookups keep
working; the dish block is merged into the stored result.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.accounts import owned_profile
from app.db import get_session
from app.errors import ApiError
from app.integrations.off import ProviderError
from app.models import Assessment, User
from app.rate_limit import enforce_user, rate_limit
from app.schemas import (
    DishAssessmentResponse,
    DishDraftRequest,
    DishDraftResponse,
    DishOptions,
    DishRequest,
    ProfileData,
)
from app.security import current_user
from app.services.dish_alternatives import (
    MAX_MODEL_LINES,
    build_alternatives,
    catalogue_options,
    flagged_lines,
)
from app.services.dish_review import (
    MESSAGE_APPLIED,
    MESSAGE_SKIPPED_DISABLED,
    MESSAGE_SKIPPED_NOT_NEEDED,
    MESSAGE_UNAVAILABLE,
    apply_verdicts,
    build_review_block,
    needs_review,
)
from app.services.dishes import COOKING_NOTES, dish_options
from app.services.dishes import assess_dish as run_dish_assessment

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["dishes"], dependencies=[Depends(current_user)])

# The wording fallback spends provider credit, so it is budgeted separately from the dish draft.
DISH_REVIEW_SCOPE = "dish_review"


@router.get("/dishes/options", response_model=DishOptions)
def options():
    return dish_options()


@router.post(
    "/dishes/draft",
    dependencies=[Depends(rate_limit("dish_draft", 10, 60, "user"))],
    response_model=DishDraftResponse,
)
async def create_dish_draft(body: DishDraftRequest, request: Request):
    """Draft a starting ingredient list for a dish name.

    The result is a model's suggestion of what usually goes into one common version of the
    dish. It is not a recipe, not a reviewed record and not measured, so it is labelled as a
    draft and the user corrects every line before any check runs. Provider failures and
    unusable output both fall back to manual entry.
    """
    try:
        return await request.app.state.models.draft_dish(body.name)
    except ProviderError as exc:
        logger.warning("dish draft failed: %s", type(exc).__name__)
        raise HTTPException(503, str(exc)) from exc


async def _model_review(
    request: Request,
    body: DishRequest,
    profile_data: ProfileData,
    food,
    result: dict,
    dish: dict,
    user: User,
) -> dict:
    """Run the wording fallback once, or explain why it did not run.

    Only the lines the reference vocabulary could not resolve are reviewed, and only when the
    deterministic pass found no conflict. A provider failure never fails the assessment: the
    review is marked unavailable with the instruction to check the pack, and every other part of
    the result stands unchanged.
    """
    if not body.use_model_review:
        return build_review_block([], "skipped", MESSAGE_SKIPPED_DISABLED)
    unmatched = dish["unmatched"]
    if not needs_review(food, result, unmatched):
        return build_review_block([], "skipped", MESSAGE_SKIPPED_NOT_NEEDED)
    enforce_user(DISH_REVIEW_SCOPE, 10, 60, user)
    restrictions = [*profile_data.allergies, *profile_data.ingredient_exclusions]
    try:
        verdicts = await request.app.state.models.review_ingredients(
            [item["input_text"] for item in unmatched],
            restrictions,
            profile_data.conditions,
        )
    except ProviderError as exc:
        logger.warning("dish wording review failed: %s", type(exc).__name__)
        return build_review_block([], "unavailable", MESSAGE_UNAVAILABLE)
    apply_verdicts(dish, result, verdicts)
    return build_review_block(verdicts, "applied", MESSAGE_APPLIED)


async def _alternatives(
    request: Request,
    profile_data: ProfileData,
    result: dict,
    dish: dict,
    user: User,
) -> dict:
    """Swaps for the lines this check flagged.

    The reviewed catalogue answers first; only the flagged lines it cannot cover are sent to the
    model, and every suggestion — catalogue or model — is screened against all of the user's
    recorded restrictions before it is shown. A provider failure leaves the catalogue answers in
    place and says the extra suggestions were unavailable.
    """
    lines = flagged_lines(dish, result)
    if not lines:
        return build_alternatives(dish, result, profile_data)

    needs_model = [
        line["input_text"]
        for line in lines
        if not (
            catalogue_options(line.get("resolved_to") or line["input_text"])
            or catalogue_options(line["input_text"])
        )
    ]
    model_options: dict = {}
    if needs_model[:MAX_MODEL_LINES]:
        restrictions = [*profile_data.allergies, *profile_data.ingredient_exclusions]
        try:
            # Swaps share the review budget because both spend provider credit; a spent budget
            # only costs the extra suggestions, never the assessment itself.
            enforce_user(DISH_REVIEW_SCOPE, 10, 60, user)
            model_options = await request.app.state.models.suggest_swaps(
                needs_model[:MAX_MODEL_LINES], restrictions
            )
        except ApiError:
            block = build_alternatives(dish, result, profile_data)
            block["notes"].append(
                "Extra substitute suggestions were skipped: this minute's suggestion budget is "
                "used. The reviewed swaps above still apply."
            )
            return block
        except ProviderError as exc:
            logger.warning("dish swap suggestions failed: %s", type(exc).__name__)
            block = build_alternatives(dish, result, profile_data)
            block["notes"].append(
                "Extra substitute suggestions were unavailable; the reviewed swaps above still apply."
            )
            return block
    return build_alternatives(dish, result, profile_data, model_options)


@router.post("/dishes/assess", status_code=201, response_model=DishAssessmentResponse)
async def create_dish_assessment(
    body: DishRequest,
    request: Request,
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
):
    """Assess one cooked dish from its typed ingredients and the confirmed declarations.

    The deterministic check runs first and always stands on its own. When it resolved nothing
    about a line but found no conflict, the wording of that line is sent to the model once and
    its verdicts come back as clearly labelled findings; that review never replaces a
    deterministic finding and never turns its own silence into a clearance.
    """
    unknown_notes = [note for note in body.cooking_notes if note not in COOKING_NOTES]
    if unknown_notes:
        raise HTTPException(422, f"Unknown cooking notes: {', '.join(unknown_notes)}")
    profile = owned_profile(session, user.id, body.profile_id)
    if profile.version != body.profile_version:
        raise ApiError(409, "profile_version_stale", "Profile changed; reload before assessment")
    profile_data = ProfileData.model_validate(profile.data)
    # Lock/check the profile version through the write so an edit cannot race this snapshot.
    session.refresh(profile, with_for_update=True)
    if profile.version != body.profile_version:
        raise ApiError(409, "profile_version_stale", "Profile changed; reload before assessment")
    food, result = run_dish_assessment(session, profile_data, body)
    dish = result["dish"]
    dish["model_review"] = await _model_review(
        request, body, profile_data, food, result, dish, user
    )
    dish["alternatives"] = await _alternatives(request, profile_data, result, dish, user)
    record = Assessment(
        owner_id=user.id,
        profile_id=profile.id,
        profile_version=profile.version,
        profile_snapshot=profile_data.model_dump(mode="json"),
        food_snapshot=food.model_dump(mode="json"),
        result=result,
    )
    session.add(record)
    session.commit()
    return {"id": record.id, "dish": result["dish"], "assessment": result}
