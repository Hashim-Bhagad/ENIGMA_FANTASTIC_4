"""Cooked-dish assessment endpoints.

Dish assessments reuse the ``Assessment`` record so history and detail lookups keep
working; the dish block is merged into the stored result.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.accounts import owned_profile
from app.db import get_session
from app.errors import ApiError
from app.models import Assessment, User
from app.schemas import DishAssessmentResponse, DishOptions, DishRequest, ProfileData
from app.security import current_user
from app.services.dishes import COOKING_NOTES, dish_options
from app.services.dishes import assess_dish as run_dish_assessment

router = APIRouter(prefix="/api", tags=["dishes"], dependencies=[Depends(current_user)])


@router.get("/dishes/options", response_model=DishOptions)
def options():
    return dish_options()


@router.post("/dishes/assess", status_code=201, response_model=DishAssessmentResponse)
def create_dish_assessment(
    body: DishRequest,
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
):
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
