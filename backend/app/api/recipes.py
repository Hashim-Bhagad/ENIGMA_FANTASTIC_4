"""Read-only access to explicitly reviewed recipe templates."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import RecipeRecord
from app.schemas import DishIngredient
from app.security import current_user

router = APIRouter(
    prefix="/api/recipes",
    tags=["recipe templates"],
    dependencies=[Depends(current_user)],
)
VALIDATED_STATUS = "validated"
MAX_INGREDIENTS = 40
MAX_NOTES = 10
TEMPLATE_WARNING = (
    "Recipe template only; confirm every ingredient and preparation detail for the actual serving. "
    "No nutrition or suitability conclusion is supplied."
)


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
    source = record.source if isinstance(record.source, dict) else {}
    source_view = {}
    for key in ("provider", "reference", "dataset_id"):
        value = source.get(key)
        if isinstance(value, str) and len(value) <= 500:
            source_view[key] = value
    return {
        "id": record.id,
        "name": record.name,
        "ingredients": [item.model_dump(mode="json") for item in normalized],
        "cooking_notes": notes,
        "source": source_view,
        "review_status": "validated_ingredients_unverified_for_serving",
        "declarations_confirmed": False,
        "warnings": [TEMPLATE_WARNING],
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


@router.get("")
@router.get("/")
def list_recipes(
    q: str = Query(default="", max_length=100),
    limit: int = Query(default=20, ge=1, le=50),
    session: Session = Depends(get_session),
):
    query = q.strip()
    statement = (
        select(RecipeRecord)
        .where(RecipeRecord.review_status == VALIDATED_STATUS)
        .order_by(RecipeRecord.name, RecipeRecord.id)
        .limit(limit)
    )
    if query:
        escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        statement = statement.where(RecipeRecord.name.ilike(f"%{escaped}%", escape="\\"))

    recipes = []
    for record in session.scalars(statement):
        item = validated_template(record)
        if item is not None:
            recipes.append(item)
    pending = _pending_count(session)
    message = (
        "No reviewed recipe templates are available yet. Imported recipe data stays hidden until its ingredient structure is reviewed."
        if not recipes
        else "Templates are starting points only; confirm the actual serving's ingredients and preparation."
    )
    return {"recipes": recipes, "pending_count": pending, "message": message}


@router.get("/{recipe_id}")
def get_recipe(recipe_id: str, session: Session = Depends(get_session)):
    record = session.get(RecipeRecord, recipe_id)
    if record is None or record.review_status != VALIDATED_STATUS:
        raise HTTPException(404, "Reviewed recipe template not found")
    item = validated_template(record)
    if item is None:
        raise HTTPException(404, "Reviewed recipe template not found")
    return item
