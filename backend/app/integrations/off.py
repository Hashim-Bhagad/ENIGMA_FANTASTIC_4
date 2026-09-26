import math
import re
from datetime import UTC, datetime

import httpx

from app.schemas import FoodObservation
from app.services.assessment import split_advisories

FIELDS = "code,product_name,product_name_en,brands,categories_tags,ingredients_text,ingredients_text_en,allergens_tags,traces_tags,nutriments,nutrition_data_per,last_modified_t"
NUTRIENTS = {
    "energy-kcal": ("energy_kcal", 1),
    "carbohydrates": ("carbohydrates_g", 1),
    "proteins": ("protein_g", 1),
    "fat": ("fat_g", 1),
    "saturated-fat": ("saturated_fat_g", 1),
    "sugars": ("sugars_g", 1),
    "fiber": ("fiber_g", 1),
    "sodium": ("sodium_mg", 1000),
    "potassium": ("potassium_mg", 1000),
    "phosphorus": ("phosphorus_mg", 1000),
}
TAG_MAP = {
    "milk": "milk",
    "eggs": "eggs",
    "soybeans": "soy",
    "peanuts": "peanuts",
    "nuts": "tree_nuts",
    "sesame-seeds": "sesame",
    "fish": "fish",
    "crustaceans": "shellfish",
    "molluscs": "shellfish",
    "wheat": "wheat",
}

# These are deliberately specific Open Food Facts taxonomy tags, not arbitrary
# category words from a product name or a free-text category field. Ancestor tags
# such as en:snacks are intentionally omitted. A recognized tag is useful for
# finding like-for-like products, but it is not a clinical or nutrient claim.
OFF_CATEGORY_TAGS = {
    "en:biscuits": "biscuits",
    "en:breakfast-cereals": "breakfast_cereals",
    "en:chocolate-spreads": "chocolate_spreads",
    "en:fruit-jams": "fruit_jams",
    "en:peanut-butters": "peanut_butters",
    "en:crackers-appetizers": "crackers_appetizers",
    "en:crackers-breakfast": "crackers_breakfast",
}
BARCODE_PATTERN = re.compile(r"(?:\d{8}|\d{12,14})\Z", re.ASCII)


class ProviderError(Exception):
    """An upstream request failed; no successful data result may be inferred."""


def valid_nutrient(value, target: str, factor: float, warnings: list[str]):
    if value is None or value == "":
        return None
    try:
        amount = float(value) * factor
    except (TypeError, ValueError):
        warnings.append(f"Unparseable source value for {target}; retained as unknown.")
        return None
    bound = 100000 if target.endswith("_mg") else 1000 if target.endswith("_kcal") else 100
    if not math.isfinite(amount) or amount < 0 or amount > bound:
        warnings.append(
            f"Implausible source value for {target}; quarantined, not corrected or used."
        )
        return None
    return amount


def tags_to_allergens(tags):
    return sorted({TAG_MAP[x.split(":")[-1]] for x in tags if x.split(":")[-1] in TAG_MAP})


def normalize_off_category(tags) -> tuple[str | None, str | None]:
    """Return one allow-listed comparable category, or an auditable reason.

    OFF category tags commonly include ancestors and can also include unrelated
    user-entered values. Only exact allow-listed taxonomy IDs participate. If a
    record has two supported category IDs, it stays uncategorized until curated.
    """
    if not isinstance(tags, list) or not tags:
        return (
            None,
            "No supported Open Food Facts category tag; manual curation is needed for comparisons.",
        )
    recognized = {
        OFF_CATEGORY_TAGS[tag.casefold()]
        for tag in tags
        if isinstance(tag, str) and tag.casefold() in OFF_CATEGORY_TAGS
    }
    if len(recognized) == 1:
        return next(iter(recognized)), None
    if len(recognized) > 1:
        return (
            None,
            "Multiple supported Open Food Facts categories conflict; category left unknown pending curation.",
        )
    return (
        None,
        "Open Food Facts categories are outside the supported comparison list; manual curation is needed.",
    )


def normalize_off(raw: dict, category: str | None = None) -> FoodObservation:
    warnings = ["Community-contributed record; confirm the physical pack and current variant."]
    declared, advisory = split_advisories(
        raw.get("ingredients_text_en") or raw.get("ingredients_text")
    )
    if not declared:
        warnings.append("Ingredient declaration is absent.")
    if category is None:
        category, category_warning = normalize_off_category(raw.get("categories_tags"))
        if category_warning:
            warnings.append(category_warning)
    basis = raw.get("nutrition_data_per")
    if basis not in ("100g", "100ml"):
        basis = None
        warnings.append(
            "A compatible nutrient basis is not explicit; nutrient comparisons remain unknown."
        )
    nutrients = {
        target: valid_nutrient(
            raw.get("nutriments", {}).get(key + "_100g"), target, factor, warnings
        )
        if basis
        else None
        for key, (target, factor) in NUTRIENTS.items()
    }
    # The values in *_100g are normalized to grams in OFF, irrespective of entry-unit labels.
    if any(x.split(":")[-1] == "gluten" for x in raw.get("allergens_tags", [])):
        warnings.append(
            "A gluten tag is present; its cereal source is not resolved to a wheat declaration."
        )
    code = str(raw.get("code", ""))
    barcode = code if BARCODE_PATTERN.fullmatch(code) else None
    if code and barcode is None:
        warnings.append("Source barcode has an unsupported format and was not used as a barcode.")
    return FoodObservation(
        name=raw.get("product_name_en") or raw.get("product_name") or f"Product {code}",
        brand=raw.get("brands") or None,
        barcode=barcode,
        category=category,
        basis=basis,
        ingredients_text=declared or None,
        advisories_text=advisory or None,
        # A populated community field is not confirmation of full label inspection.
        ingredients_complete=False,
        advisories_complete=False,
        # OFF tags can combine ingredient and advisory statements. Keep their evidence separate.
        reported_allergens=tags_to_allergens(raw.get("allergens_tags", [])),
        precautionary_allergens=tags_to_allergens(raw.get("traces_tags", [])),
        nutrients=nutrients,
        source={
            "kind": "openfoodfacts",
            "reference": f"https://world.openfoodfacts.org/product/{code}",
            "retrieved_at": datetime.now(UTC).isoformat(),
            "warnings": warnings,
        },
    )


def normalize_apify_off(raw: dict, dataset_id: str, category: str | None = None):
    # This flattened actor has no reliable nutrient-unit/basis metadata. Read raw originals for assessment.
    declared, advisory = split_advisories(raw.get("ingredients_text"))
    nutrients = {}
    for target, _ in NUTRIENTS.values():
        nutrients[target] = None
    warnings = [
        "Flattened Apify export lacks explicit nutrient units and separates allergen/advisory information incompletely; confirm against the original OFF record."
    ]
    return FoodObservation(
        name=raw.get("product_name") or "Unnamed imported product",
        brand=raw.get("brands") or None,
        barcode=str(raw["barcode"]) if raw.get("barcode") else None,
        category=category,
        basis=None,
        ingredients_text=declared or None,
        advisories_text=advisory or None,
        nutrients=nutrients,
        source={
            "kind": "apify_off",
            "reference": f"https://api.apify.com/v2/datasets/{dataset_id}/items",
            "retrieved_at": raw.get("fetched_at"),
            "warnings": warnings,
        },
    )


class OpenFoodFacts:
    def __init__(self, client: httpx.AsyncClient, user_agent: str):
        self.client = client
        self.headers = {"User-Agent": user_agent}

    async def product(self, barcode: str) -> dict | None:
        try:
            response = await self.client.get(
                f"https://world.openfoodfacts.org/api/v3/product/{barcode}.json",
                params={"fields": FIELDS},
                headers=self.headers,
            )
            if response.status_code == 404:
                return None
            response.raise_for_status()
            data = response.json()
            if data.get("status") in (0, "failure") or not data.get("product"):
                return None
            return data["product"]
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            raise ProviderError(
                "Open Food Facts lookup failed; use a saved record or manual label entry."
            ) from exc

    async def search(self, query: str, limit: int = 5) -> list[dict]:
        # The current documented product endpoint is v3; this is the separately tested legacy search endpoint.
        try:
            response = await self.client.get(
                "https://world.openfoodfacts.org/cgi/search.pl",
                params={
                    "search_terms": query,
                    "search_simple": 1,
                    "action": "process",
                    "json": 1,
                    "page_size": limit,
                    "fields": FIELDS,
                },
                headers=self.headers,
            )
            response.raise_for_status()
            return response.json().get("products", [])[:limit]
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            raise ProviderError(
                "Open Food Facts search is unavailable; saved catalog search is still available."
            ) from exc
