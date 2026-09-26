"""Recipe catalogue reads: reviewed templates plus bounded live Food.com imports.

Two kinds of row are served, and they are never mixed up:

* ``validated`` rows are reviewed ingredient templates (``validated_template``).
* ``imported_source`` rows came straight from the Food.com actor
  (``imported_template``). They keep the source's ingredient lines verbatim, are
  never called validated, and always carry ``source_note``.

A search may also start one bounded, pay-per-result actor run, but only when the
local result set is thin, the live path is enabled, a token exists and the query
has not been fetched before; that attempt is rate-limited by the ``recipes_live``
scope. Any live failure degrades to the cached or empty state with
``live_status="unavailable"`` instead of an error response.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_session
from app.integrations.off import ProviderError
from app.models import RecipeRecord, User
from app.rate_limit import enforce_user
from app.schemas import DishIngredient
from app.security import current_user
from app.services.recipes_live import (
    SOURCE_NOTE,
    cached_records,
    fetch_and_store,
    has_fetched,
    like_pattern,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/recipes",
    tags=["recipe templates"],
    dependencies=[Depends(current_user)],
)
VALIDATED_STATUS = "validated"
MAX_INGREDIENTS = 40
MAX_NOTES = 10
LIVE_SCOPE = "recipes_live"
LIVE_LIMIT_PER_MINUTE = 5
LIVE_WINDOW_SECONDS = 60
TEMPLATE_WARNING = (
    "Recipe template only; confirm every ingredient and preparation detail for the actual serving. "
    "No nutrition or suitability conclusion is supplied."
)
REVIEWED_NOTE = "Reviewed ingredient template; the actual serving's amounts and preparation still need confirming."
# Only these source keys are echoed to a client, and only as short strings.
SOURCE_KEYS = ("provider", "actor", "run_id", "dataset_id", "query", "reference", "retrieved_at")
NO_TEMPLATES_MESSAGE = (
    "No reviewed recipe templates are available yet. Imported recipe data stays hidden until its "
    "ingredient structure is reviewed."
)
TEMPLATES_MESSAGE = (
    "Templates are starting points only; confirm the actual serving's ingredients and preparation."
)
SOURCE_SUFFIX = (
    " Source rows are the Food.com list as written: amounts and preparation are not confirmed."
)


def _source_view(record: RecipeRecord) -> dict:
    source = record.source if isinstance(record.source, dict) else {}
    return {
        key: source[key]
        for key in SOURCE_KEYS
        if isinstance(source.get(key), str) and len(source[key]) <= 500
    }


def validated_template(record: RecipeRecord) -> dict | None:
    """Return a small allowlisted view only for reviewed, structurally valid records."""
    raw = record.raw if isinstance(record.raw, dict) else {}
    ingredients = raw.get("ingredients")
    if not isinstance(ingredients, list) or not 1 <= len(ingredients) <= MAX_INGREDIENTS:
        return None
    try:
        normalized = [DishIngredient.model_validate(item) for item in ingredients]
    except (TypeError, ValueError):
        return None

    notes = raw.get("cooking_notes", [])
    if (
        not isinstance(notes, list)
        or len(notes) > MAX_NOTES
        or any(not isinstance(note, str) or not note.strip() for note in notes)
    ):
        return None
    return {
        "id": record.id,
        "name": record.name,
        "ingredients": [item.model_dump(mode="json") for item in normalized],
        "cooking_notes": notes,
        "source": _source_view(record),
        "source_note": REVIEWED_NOTE,
        "review_status": "validated_ingredients_unverified_for_serving",
        "declarations_confirmed": False,
        "warnings": [TEMPLATE_WARNING],
    }


def imported_template(record: RecipeRecord) -> dict | None:
    """Return one Food.com source row, labelled as unreviewed and unconfirmed.

    The row is shown with the source's own wording, so a weight appears only when
    the line itself stated one. No nutrition field is exposed.
    """
    raw = record.raw if isinstance(record.raw, dict) else {}
    ingredients = raw.get("ingredients")
    if not isinstance(ingredients, list) or not 1 <= len(ingredients) <= MAX_INGREDIENTS:
        return None
    try:
        normalized = [DishIngredient.model_validate(item) for item in ingredients]
    except (TypeError, ValueError):
        return None

    notes = raw.get("cooking_notes", [])
    if (
        not isinstance(notes, list)
        or len(notes) > MAX_NOTES
        or any(not isinstance(note, str) or not note.strip() for note in notes)
    ):
        return None
    return {
        "id": record.id,
        "name": record.name,
        "ingredients": [item.model_dump(mode="json") for item in normalized],
        "cooking_notes": notes,
        "source": _source_view(record),
        "source_note": SOURCE_NOTE,
        "review_status": record.review_status,
        "declarations_confirmed": False,
        "warnings": [SOURCE_NOTE],
    }


def _pending_count(session: Session) -> int:
    return int(
        session.scalar(
            select(func.count())
            .select_from(RecipeRecord)
            .where(RecipeRecord.review_status != VALIDATED_STATUS)
        )
        or 0
    )


def local_recipes(session: Session, query: str, limit: int) -> tuple[list[dict], bool]:
    """Reviewed templates matching the search, then cached imported rows.

    Returns ``(recipes, has_imported)``. Reviewed rows are listed first because
    they are the ones a user may act on; imported rows only ever appear for a
    non-empty search, where the source's own query is recorded on the row.
    """
    statement = (
        select(RecipeRecord)
        .where(RecipeRecord.review_status == VALIDATED_STATUS)
        .order_by(RecipeRecord.name, RecipeRecord.id)
        .limit(limit)
    )
    if query:
        statement = statement.where(RecipeRecord.name.ilike(like_pattern(query), escape="\\"))
    recipes = []
    for record in session.scalars(statement):
        item = validated_template(record)
        if item is not None:
            recipes.append(item)

    has_imported = False
    if query:
        for record in cached_records(session, query, limit):
            item = imported_template(record)
            if item is not None:
                recipes.append(item)
                has_imported = True
    return recipes, has_imported


def _message(
    query: str, recipes: list[dict], has_imported: bool, live_status: str, provider_message: str
) -> str:
    """Plain wording for the state actually served: never a claim the rows do not support."""
    if recipes:
        return TEMPLATES_MESSAGE + (SOURCE_SUFFIX if has_imported else "")
    if live_status == "unavailable":
        return (
            f"{provider_message or 'The live recipe search is unavailable right now.'} "
            "You can still enter your own ingredient list."
        )
    if live_status == "disabled":
        return (
            "Live recipe search is off and no stored recipes match this search. "
            "You can still enter your own ingredient list."
        )
    if query:
        return "No recipes match this search. You can still enter your own ingredient list."
    return NO_TEMPLATES_MESSAGE


@router.get("")
@router.get("/")
async def list_recipes(
    request: Request,
    q: str = Query(default="", max_length=100),
    limit: int = Query(default=20, ge=1, le=50),
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
):
    """List reviewed templates and, when a search is thin, one bounded live import.

    Live status: ``cached`` (served from stored rows), ``fetched`` (a run added
    rows), ``disabled`` (live search off or no token), ``unavailable`` (the run
    failed; cached or empty rows are still returned). Requires a bearer token.
    """
    settings = get_settings()
    query = " ".join(q.split())[:100]
    recipes, has_imported = local_recipes(session, query, limit)
    live_status = "cached"
    provider_message = ""
    skipped = 0

    target = max(1, min(limit, settings.recipes_live_max_items))
    thin = len(recipes) < target
    if query and thin and not has_fetched(session, query):
        token = settings.apify_token.get_secret_value() if settings.apify_token else None
        if not settings.recipes_live_enabled or not token:
            live_status = "disabled"
        else:
            # Only the attempt to spend provider credit is throttled, not a cached read.
            enforce_user(LIVE_SCOPE, LIVE_LIMIT_PER_MINUTE, LIVE_WINDOW_SECONDS, user)
            # Release the read transaction before waiting on the provider.
            session.rollback()
            try:
                summary = await fetch_and_store(
                    session, query, limit, client=getattr(request.app.state, "http", None)
                )
            except ProviderError as exc:
                logger.info("live recipe search unavailable: %s", exc)
                live_status = "unavailable"
                provider_message = str(exc)
            else:
                live_status = "fetched" if summary["created"] else "cached"
                skipped = summary["skipped"]
                recipes, has_imported = local_recipes(session, query, limit)

    return {
        "recipes": recipes,
        "pending_count": _pending_count(session),
        "live_status": live_status,
        "query": query,
        "skipped_records": skipped,
        "message": _message(query, recipes, has_imported, live_status, provider_message),
    }


@router.get("/{recipe_id}")
def get_recipe(recipe_id: str, session: Session = Depends(get_session)):
    """Return one reviewed template or one imported source row. Requires a bearer token."""
    record = session.get(RecipeRecord, recipe_id)
    if record is None:
        raise HTTPException(404, "Reviewed recipe template not found")
    item = (
        validated_template(record)
        if record.review_status == VALIDATED_STATUS
        else imported_template(record)
    )
    if item is None:
        raise HTTPException(404, "Reviewed recipe template not found")
    return item
