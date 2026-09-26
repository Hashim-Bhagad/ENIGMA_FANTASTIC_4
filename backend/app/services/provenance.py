"""Explain a saved catalog observation without making another provider request."""

import hashlib
import json

from app.integrations.off import NUTRIENTS
from app.models import Product


def product_provenance(product: Product) -> dict:
    food, raw = product.observation, product.raw or {}
    source = food["source"]
    basis = food.get("basis")
    source_basis = raw.get("nutrition_data_per")
    raw_nutrients = raw.get("nutriments")
    raw_nutrients = raw_nutrients if isinstance(raw_nutrients, dict) else {}
    fields = []
    for source_key, (target, factor) in NUTRIENTS.items():
        value = food.get("nutrients", {}).get(target)
        unit = target.rsplit("_", 1)[1]
        entry = {
            "field": target,
            "status": "available" if value is not None else "unknown",
            "source_field": None,
            "source_value": None,
            "source_unit": None,
            "value": value,
            "unit": unit,
            "basis": basis,
            "transformation": None,
            "reason": None,
        }
        if product.source_kind == "openfoodfacts":
            raw_key = source_key + "_100g"
            source_value = raw_nutrients.get(raw_key)
            entry.update(
                source_field="nutriments." + raw_key,
                source_value=source_value,
                source_unit="kcal" if source_key == "energy-kcal" else "g",
                transformation="Source grams × 1000 → milligrams"
                if factor == 1000
                else "Source value retained in its normalized unit",
            )
            if source_basis not in {"100g", "100ml"}:
                entry.update(
                    status="unknown_basis",
                    reason="The source does not provide the supported measurement basis; the raw amount is not used.",
                )
            elif source_value is None or source_value == "":
                entry.update(
                    status="missing",
                    reason="This nutrient field is absent from the saved source response.",
                )
            elif value is None:
                entry.update(
                    status="unusable",
                    reason="The raw value was unparseable, negative, nonfinite, or outside the allowed bounds; it was not corrected or used.",
                )
            if value is None:
                entry["transformation"] = "No usable normalized value produced"
        elif product.source_kind == "apify_off":
            entry.update(
                status="untraceable_units",
                reason="This flattened export has no validated nutrient unit and basis. Its numbers are not used as normalized facts.",
            )
        else:
            entry.update(
                source_field="reviewed_observation.nutrients." + target
                if "reviewed_observation" in raw
                else "observation.nutrients." + target,
                source_value=value,
                source_unit=unit,
                transformation="Recorded observation; no upstream unit conversion trace is available",
                reason="Operator-reviewed label entry"
                if product.source_kind == "manual"
                else "Synthetic demo value"
                if product.source_kind == "demo"
                else "Model-extracted observation requiring user review",
            )
        fields.append(entry)

    for target in ("name", "ingredients_text", "advisories_text"):
        raw_key, source_value = None, None
        if product.source_kind == "openfoodfacts":
            choices = (
                ("product_name_en", "product_name")
                if target == "name"
                else ("ingredients_text_en", "ingredients_text")
            )
            raw_key = next((key for key in choices if raw.get(key)), None)
            source_value = raw.get(raw_key) if raw_key else None
        fields.append(
            {
                "field": target,
                "status": "available" if food.get(target) else "missing",
                "source_field": raw_key,
                "source_value": source_value,
                "source_unit": None,
                "value": food.get(target),
                "unit": None,
                "basis": None,
                "transformation": "Ingredient declaration and embedded precautionary statements are separated by code"
                if target != "name" and product.source_kind == "openfoodfacts"
                else None,
                "reason": "Saved source observation"
                if food.get(target)
                else "No usable text in the saved observation",
            }
        )

    digest = hashlib.sha256(
        json.dumps(raw, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    ).hexdigest()
    return {
        "product_id": product.id,
        "barcode": product.barcode,
        "snapshot_updated_at": product.updated_at.isoformat(),
        "raw_snapshot_sha256": digest,
        "source": {
            "kind": source["kind"],
            "reference": source["reference"],
            "retrieved_at": source.get("retrieved_at"),
            "source_modified_at": raw.get("last_modified_t"),
        },
        "fields": fields,
        "source_salt": {
            "source_field": "nutriments.salt_100g",
            "source_value": raw_nutrients.get("salt_100g"),
            "source_unit": "g",
            "used_by_backend": False,
            "reason": "The backend reads sodium_100g and does not calculate sodium from salt. Open Food Facts may itself derive nutrient fields upstream; this trace does not prove direct label measurement.",
        }
        if product.source_kind == "openfoodfacts"
        else None,
        "limitations": [
            *source.get("warnings", []),
            "This trace describes the saved catalog response, not an independently verified laboratory result or current package.",
            "User corrections can differ from these original source values and are recorded with the assessment.",
        ],
    }
