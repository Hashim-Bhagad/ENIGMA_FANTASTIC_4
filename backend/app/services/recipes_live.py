"""Live Food.com recipe search through a pay-per-result Apify actor.

Rows fetched here are staged as ``RecipeRecord`` rows with
``review_status="imported_source"``. They are *not* reviewed templates: the
ingredient lines are kept exactly as the source wrote them, and a weight is
attached only when the line itself states one. Nothing on this path derives a
nutrition figure or promotes a row into the reviewed set.

Caching: each stored row's ``source.query_key`` is the normalised query text, so
a repeated search is answered from ``recipe_records`` with no new actor run. The
caller decides when a live run is worth attempting (see
``app/api/recipes.py``) and must not run a query twice: one run is charged per
returned result.
"""

from __future__ import annotations

import hashlib
import logging
import re
from datetime import UTC, datetime

import httpx
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.integrations.apify import ApifyReader
from app.integrations.off import ProviderError
from app.models import RecipeRecord

logger = logging.getLogger(__name__)

PROVIDER = "Apify food.com scraper"
ACTOR = "parseforge/food-com-scraper"
ACTOR_ID = "L9lMlZe30ghx2Zdv3"
IMPORTED_STATUS = "imported_source"
# What the rows can honestly support: the source list as written, nothing checked.
SOURCE_NOTE = "Food.com source list — ingredients as written; amounts and preparation not confirmed"
MAX_INGREDIENTS = 40
# Matches DishIngredient's 200-character line cap, so every stored line is servable.
MAX_LINE = 200
CLIENT_TIMEOUT_SECONDS = 30

# Only these units turn a line into a weight. A cup, spoon, clove or "to taste"
# stays null: converting them would invent a mass the source never stated.
MASS_UNITS = {
    "g": 1.0,
    "gram": 1.0,
    "grams": 1.0,
    "kg": 1000.0,
    "kilogram": 1000.0,
    "kilograms": 1000.0,
    "oz": 28.349523125,
    "ounce": 28.349523125,
    "ounces": 28.349523125,
    "lb": 453.59237,
    "lbs": 453.59237,
    "pound": 453.59237,
    "pounds": 453.59237,
}
_UNIT_PATTERN = "|".join(sorted(MASS_UNITS, key=len, reverse=True))
# A quantity is a whole number, a decimal, a fraction, or "1 1/2".
_QUANTITY_PATTERN = r"\d+\s+\d+/\d+|\d+/\d+|\d+(?:\.\d+)?"
MASS_RE = re.compile(
    rf"(?<![\w.])(?P<quantity>{_QUANTITY_PATTERN})\s*(?P<unit>{_UNIT_PATTERN})\b\.?",
    re.IGNORECASE,
)
FRACTION_RE = re.compile(r"^(\d+)\s+(\d+)/(\d+)$")


def query_key(query: str) -> str:
    """Normalise a query so "Paneer  Butter" and "paneer butter" share one cache entry."""
    return " ".join(query.lower().split())[:100]


def like_pattern(query: str) -> str:
    """Treat user-entered %, _ and backslashes as literal characters in SQL LIKE."""
    escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _quantity(text: str) -> float | None:
    match = FRACTION_RE.match(text.strip())
    if match:
        whole, numerator, denominator = (int(part) for part in match.groups())
        return whole + numerator / denominator if denominator else None
    if "/" in text:
        numerator, _, denominator = text.partition("/")
        return int(numerator) / int(denominator) if int(denominator) else None
    try:
        return float(text)
    except ValueError:
        return None


def extract_grams(line: str) -> float | None:
    """Return the mass a line states, or ``None`` when it states none.

    "200 g paneer" and "1/2 lb butter" have a mass; "1 cup rice", "2 cloves" and
    "salt, to taste" do not, so they stay ``None``. A conversion to grams is
    rounded to 2 decimals.
    """
    if not isinstance(line, str):
        return None
    match = MASS_RE.search(line)
    if match is None:
        return None
    amount = _quantity(match.group("quantity"))
    if amount is None:
        return None
    grams = round(amount * MASS_UNITS[match.group("unit").lower()], 2)
    # A weight must be positive to be servable; "0 g" states no usable mass.
    return grams if grams > 0 else None


def _lines_from_text(value: str) -> list[str]:
    """Split a delimited ingredient string without splitting on every comma."""
    for separator in ("\n", ";", "|"):
        if separator in value:
            parts = value.split(separator)
            break
    else:
        parts = value.split(",") if value.count(",") else [value]
    return parts


def ingredient_lines(raw: dict) -> list[str]:
    """Read ingredient lines from the shapes the sources use.

    Accepts a ``list[str]``, a ``list[dict]`` (``text``/``name``/``ingredient``
    plus an optional explicit numeric ``grams``), or one delimited string.
    """
    value = raw.get("ingredients")
    if value is None:
        value = raw.get("ingredient_lines")
    if isinstance(value, str):
        candidates = _lines_from_text(value)
    elif isinstance(value, list):
        candidates = value
    else:
        return []

    lines: list[str] = []
    for item in candidates:
        if isinstance(item, str):
            text = item.strip()
        elif isinstance(item, dict):
            text = next(
                (
                    item[key].strip()
                    for key in ("text", "name", "ingredient")
                    if isinstance(item.get(key), str) and item[key].strip()
                ),
                "",
            )
        else:
            text = ""
        if text:
            # Kept verbatim (inner spacing included) so the label can claim the line is as written.
            lines.append(text[:MAX_LINE])
    return lines


def recipe_name(raw: dict) -> str | None:
    """Read the recipe name from ``title``/``name``, or ``None`` when it has none."""
    for key in ("title", "name"):
        value = raw.get(key)
        if isinstance(value, str) and value.strip():
            return " ".join(value.split())[:300]
    return None


def recipe_reference(raw: dict) -> str | None:
    """Read the source URL from ``url``/``link`` (used for the row's identity)."""
    for key in ("url", "link"):
        value = raw.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()[:500]
    return None


def row_id(key: str, identity: str) -> str:
    """A stable id per (query, recipe), so re-running the same search never duplicates a row."""
    return hashlib.sha256(f"food-com|{key}|{identity}".encode()).hexdigest()


def prepare_row(
    raw: dict, query: str, key: str, run_id: str, dataset_id: str, retrieved_at: str
) -> tuple[RecipeRecord | None, str | None]:
    """Convert one actor row, or explain why it cannot be used.

    Returns ``(record, None)`` for a usable row and ``(None, reason)`` for a skip;
    a skip never aborts the batch. ``rating`` and ``nutrition`` are tolerated
    where a source supplies them but are not converted: no nutrition maths is
    done from these rows.
    """
    if not isinstance(raw, dict):
        return None, "row is not an object"
    if raw.get("error"):
        return None, "row reports a scrape error"
    name = recipe_name(raw)
    if name is None:
        return None, "no recipe name"
    lines = ingredient_lines(raw)
    if not lines:
        return None, "no ingredient lines"
    if len(lines) > MAX_INGREDIENTS:
        return None, f"more than {MAX_INGREDIENTS} ingredient lines"

    ingredients = [{"text": line, "grams": extract_grams(line)} for line in lines]
    reference = recipe_reference(raw)
    identity = reference or f"{name}|{'|'.join(lines)}"
    source = {
        "provider": PROVIDER,
        "actor": ACTOR,
        "actor_id": ACTOR_ID,
        "run_id": run_id,
        "dataset_id": dataset_id,
        "query": query,
        "query_key": key,
        "retrieved_at": retrieved_at,
    }
    if reference:
        source["reference"] = reference
    record = RecipeRecord(
        id=row_id(key, identity),
        name=name,
        raw={"ingredients": ingredients, "cooking_notes": []},
        source=source,
        review_status=IMPORTED_STATUS,
    )
    return record, None


async def fetch_and_store(
    session: Session, query: str, limit: int, *, client: httpx.AsyncClient | None = None
) -> dict:
    """Run one bounded Food.com search and stage its rows as unreviewed imports.

    ``limit`` is capped by ``recipes_live_max_items`` so a caller cannot raise the
    spend; the run's own timeout comes from ``recipes_live_timeout_seconds``. A
    row that already exists (same query and recipe) is reused, so a repeated call
    adds nothing. Returns ``{"created", "reused", "skipped", "skipped_reasons",
    "run_id", "dataset_id", "cost_usd", "status"}``; unusable rows are counted,
    never fatal.

    The caller owns the cache decision: this function always starts a run, so it
    must only be called for a query that has not been fetched yet (see
    ``has_fetched``).
    """
    settings = get_settings()
    token = settings.apify_token.get_secret_value() if settings.apify_token else None
    if not token:
        raise ProviderError("Live recipe search needs an Apify token.")
    key = query_key(query)
    if not key:
        raise ProviderError("Enter a search term for the live recipe search.")
    max_items = max(1, min(limit, settings.recipes_live_max_items))

    owned = client is None
    http_client = client or httpx.AsyncClient(
        timeout=CLIENT_TIMEOUT_SECONDS, follow_redirects=False
    )
    try:
        reader = ApifyReader(http_client, token)
        result = await reader.search_recipes(
            query, max_items, settings.recipes_live_timeout_seconds, token
        )
    finally:
        if owned:
            await http_client.aclose()

    retrieved_at = datetime.now(UTC).isoformat()
    typed_query = " ".join(query.split())[:100]
    created, reused, skipped, skipped_reasons = 0, 0, 0, []
    for index, raw in enumerate(result["items"]):
        record, reason = prepare_row(
            raw, typed_query, key, result["run_id"], result["dataset_id"], retrieved_at
        )
        if record is None:
            skipped += 1
            skipped_reasons.append({"record_index": index, "reason": reason})
            logger.warning("skipped Food.com row index=%s reason=%s", index, reason)
            continue
        if session.get(RecipeRecord, record.id) is None:
            session.add(record)
            created += 1
        else:
            reused += 1
    session.commit()
    return {
        "created": created,
        "reused": reused,
        "skipped": skipped,
        "skipped_reasons": skipped_reasons,
        "run_id": result["run_id"],
        "dataset_id": result["dataset_id"],
        "cost_usd": result["cost_usd"],
        "status": result["status"],
    }


def cached_records(session: Session, query: str, limit: int) -> list[RecipeRecord]:
    """Imported rows already stored for this search: same query, or a matching name."""
    key = query_key(query)
    statement = (
        select(RecipeRecord)
        .where(RecipeRecord.review_status == IMPORTED_STATUS)
        .where(
            or_(
                RecipeRecord.source["query_key"].as_string() == key,
                RecipeRecord.name.ilike(like_pattern(query), escape="\\"),
            )
        )
        .order_by(RecipeRecord.name, RecipeRecord.id)
        .limit(limit)
    )
    return list(session.scalars(statement))


def has_fetched(session: Session, query: str) -> bool:
    """True when a run already stored rows for this exact query, so it must not run again."""
    key = query_key(query)
    if not key:
        return False
    statement = (
        select(RecipeRecord.id)
        .where(RecipeRecord.review_status == IMPORTED_STATUS)
        .where(RecipeRecord.source["query_key"].as_string() == key)
        .limit(1)
    )
    return session.scalar(statement) is not None
