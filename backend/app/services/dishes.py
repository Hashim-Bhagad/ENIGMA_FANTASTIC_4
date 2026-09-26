"""Cooked-dish assessment: user-typed ingredients resolved to reference composition rows.

This is deliberately conservative. An ingredient is resolved only by an explicit
reference code or an exact normalized-name match against ``ReferenceFood``; nothing is
guessed. A per-100g estimate exists only when *every* ingredient is both matched and
weighed in grams, otherwise the nutrition stays unknown.
"""

from __future__ import annotations

import unicodedata

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ReferenceFood
from app.schemas import DishRequest, FoodObservation, ProfileData
from app.services.assessment import assess

# Reference composition stores these keys; only label vocabulary keys are carried into the
# estimate (available carbohydrate/free sugars are not silently equated to label values).
DISH_NUTRIENTS = (
    "sodium_mg",
    "potassium_mg",
    "phosphorus_mg",
    "protein_g",
    "fat_g",
    "fiber_g",
    "energy_kcal",
)

COOKING_NOTES = {
    "deep_fried": {
        "label": "Deep fried",
        "title": "Deep frying adds unmeasured oil",
        "detail": "The ingredient list does not include the frying oil a deep-fried dish absorbs, "
        "so the reference estimate understates the fat actually eaten.",
        "next_step": "Treat the estimate as a floor and allow a margin for absorbed oil.",
        "message": "Deep-fried dishes absorb cooking oil that is not in the ingredient list.",
    },
    "pan_fried": {
        "label": "Pan fried",
        "title": "Pan frying adds cooking oil",
        "detail": "Oil or butter used in the pan is not part of the typed ingredient list, so its "
        "fat and energy sit outside the estimate.",
        "next_step": "Add the oil you actually used as an ingredient if you want it counted.",
        "message": "Pan-frying oil is not part of the typed ingredient list.",
    },
    "gravy_or_curry": {
        "label": "Gravy or curry base",
        "title": "Gravy or curry base is not measured",
        "detail": "A gravy or curry base often carries flour, cream or stock that is not in the "
        "typed list, so the estimate can miss both allergens and sodium.",
        "next_step": "Add every base ingredient, including thickeners and stock, to the list.",
        "message": "Thickeners and stock in a gravy or curry base are not measured here.",
    },
    "added_salt": {
        "label": "Salt added during cooking",
        "title": "Salt added during cooking is not measured",
        "detail": "Salt shaken in during cooking is not an ingredient you typed, so the sodium "
        "estimate is lower than the dish you will eat.",
        "next_step": "Add the salt you used as an ingredient, or reduce it and note the change.",
        "message": "Salt added during cooking is absent from the sodium estimate.",
    },
    "added_sugar": {
        "label": "Sugar added during cooking",
        "title": "Sugar added during cooking is not measured",
        "detail": "Sugar or syrup added while cooking is not in the typed list, so the reference "
        "sugars stay below what the dish contains.",
        "next_step": "Add the sugar or syrup you used as an ingredient if it should be counted.",
        "message": "Sugar added during cooking is absent from the estimate.",
    },
    "packaged_sauce": {
        "label": "Packaged sauce",
        "title": "Packaged sauce has its own declaration",
        "detail": "A packaged sauce or paste brings its own ingredient panel and precautionary "
        "statements, which are not checked against your restrictions here.",
        "next_step": "Scan or type the sauce's own label and assess it separately.",
        "message": "A packaged sauce's declaration is not checked by this dish assessment.",
    },
    "reused_oil": {
        "label": "Reused oil",
        "title": "Reused frying oil is not measured",
        "detail": "Oil reused across batches changes the fat actually absorbed and can carry "
        "traces from earlier foods; no reference value covers it.",
        "next_step": "Note the reuse when you interpret the fat estimate, or use fresh oil.",
        "message": "Reused frying oil is not represented in reference composition data.",
    },
    "restaurant_prepared": {
        "label": "Restaurant prepared",
        "title": "Restaurant preparation is unknown",
        "detail": "A restaurant kitchen's ingredients, oil and cross-contact are unknown and "
        "cannot be reconstructed from reference composition data.",
        "next_step": "Ask the kitchen about the ingredients and cross-contact before relying on "
        "this estimate.",
        "message": "Restaurant preparation details are unavailable to this estimate.",
    },
}

UNKNOWNS = [
    "Reference composition data describe individual edible ingredients, not the cooked dish you ate.",
    "Oil absorbed in frying, salt or sugar added during cooking, and sauces with their own "
    "labels are not measured here.",
    "Reference data report available carbohydrate and free sugars, not label total carbohydrate "
    "and sugars, so carbohydrate and sugar goals stay unknown.",
    "Weights you type are treated as the edible amounts used; cooking losses are not modelled.",
]

ASSUMPTIONS = [
    "An estimate appears only when every ingredient is matched to a reference food and given a "
    "weight in grams; the per-100g values are the summed ingredient nutrients divided by total "
    "grams, times 100, and are not a final cooked-yield measurement.",
    "A nutrient stays unknown unless every matched ingredient reports it.",
    "The declared ingredient list is treated as complete only because you confirmed it; kitchen "
    "cross-contact is not verified by this assessment.",
    "Cooking notes add awareness points only; they do not change the numbers.",
]


def normalize_name(value: str) -> str:
    """NFKC + casefold + punctuation/whitespace normalization for exact name matching."""
    text = unicodedata.normalize("NFKC", value).casefold()
    text = "".join(ch if ch.isalnum() or ch.isspace() else " " for ch in text)
    return " ".join(text.split())


def reference_index(session: Session) -> dict[str, ReferenceFood]:
    rows = session.scalars(select(ReferenceFood)).all()
    index: dict[str, ReferenceFood] = {}
    for row in rows:
        index.setdefault(normalize_name(row.name), row)
    return index


def cooking_considerations(notes: list[str]) -> list[dict]:
    findings = []
    for note in notes:
        spec = COOKING_NOTES.get(note)
        if spec is None:
            continue
        findings.append(
            {
                "code": f"cooking_{note}",
                "group": "consideration",
                "title": spec["title"],
                "detail": spec["detail"],
                "next_step": spec["next_step"],
                "affects": [f"cooking:{note}"],
                "message": spec["message"],
                "evidence": [spec["label"]],
                "kind": "cooking_note",
                "cooking_note": note,
            }
        )
    return findings


def _nutrient_value(row: ReferenceFood, key: str):
    nutrients = row.data.get("nutrients") if isinstance(row.data, dict) else None
    if not isinstance(nutrients, dict):
        return None
    value = nutrients.get(key)
    return value if isinstance(value, (int, float)) else None


def build_dish(session: Session, body: DishRequest) -> dict:
    """Resolve ingredients, estimate per-100g nutrients when fully known, and build the block."""
    index = reference_index(session)
    matches, unmatched, resolved = [], [], []
    for item in body.ingredients:
        row = None
        matched_by = "name"
        if item.reference_code:
            row = session.get(ReferenceFood, item.reference_code)
            matched_by = "reference_code"
            if row is None:
                unmatched.append(
                    {
                        "input_text": item.text,
                        "reason": f"No reference food has code {item.reference_code}.",
                    }
                )
                continue
        else:
            row = index.get(normalize_name(item.text))
            if row is None:
                unmatched.append(
                    {
                        "input_text": item.text,
                        "reason": "No reference food matches this name exactly; check the spelling "
                        "or pick a match from the reference-food search.",
                    }
                )
                continue
        data = row.data if isinstance(row.data, dict) else {}
        matches.append(
            {
                "input_text": item.text,
                "code": row.code,
                "name": row.name,
                "basis": data.get("basis"),
                "grams": item.grams,
                "matched_by": matched_by,
            }
        )
        resolved.append((row, item.grams))

    complete = (
        bool(resolved)
        and len(resolved) == len(body.ingredients)
        and all(grams is not None for _, grams in resolved)
    )
    nutrients: dict[str, float | None] = {}
    total_grams = None
    assumptions: list[str] = []
    warnings: list[str] = []
    if complete:
        total_grams = round(sum(grams for _, grams in resolved), 4)
        for key in DISH_NUTRIENTS:
            values = [_nutrient_value(row, key) for row, _ in resolved]
            if any(value is None for value in values):
                nutrients[key] = None
                assumptions.append(
                    f"{key} stays unknown because at least one ingredient has no reference value."
                )
                continue
            # Each value is per 100 g, so the ingredient contributes value * grams / 100.
            total_mass = sum(
                value * grams / 100 for value, (_, grams) in zip(values, resolved, strict=True)
            )
            nutrients[key] = round(total_mass / total_grams * 100, 2)
        basis = "100g"
        warnings.append(
            "Estimated from reference ingredient composition, not a measured prepared dish."
        )
    else:
        basis = None
        warnings.append(
            "No per-100g estimate: every ingredient must be matched to a reference food and "
            "weighed in grams."
        )
        if unmatched:
            warnings.append(
                f"{len(unmatched)} ingredient(s) were not matched to a reference food and are "
                "absent from any estimate."
            )
        elif not all(item.grams is not None for item in body.ingredients):
            warnings.append("One or more ingredients have no weight in grams.")
    assumptions.append(
        "Reference data report available carbohydrate and free sugars, not label total "
        "carbohydrate and sugars, so carbohydrate and sugar goals cannot be evaluated here."
    )

    ingredients_text = ", ".join(item.text for item in body.ingredients)
    food = FoodObservation.model_validate(
        {
            "name": body.name,
            "category": None,
            "basis": basis,
            "ingredients_text": ingredients_text,
            "advisories_text": "" if body.declarations_confirmed else None,
            "ingredients_complete": body.declarations_confirmed,
            "advisories_complete": body.declarations_confirmed,
            "nutrients": nutrients if complete else {},
            "source": {
                "kind": "dish",
                "reference": f"dish:{normalize_name(body.name)}",
                "warnings": warnings,
            },
        }
    )
    block = {
        "name": body.name,
        "matches": matches,
        "unmatched": unmatched,
        "estimate": {
            "available": complete,
            "basis": basis,
            "nutrients": nutrients if complete else {},
            "total_grams": total_grams,
            "assumptions": assumptions,
        },
    }
    return {
        "food": food,
        "block": block,
        "considerations": cooking_considerations(body.cooking_notes),
    }


def assess_dish(session: Session, profile_data: ProfileData, body: DishRequest) -> tuple:
    """Assess one cooked dish, merging cooking-note considerations into the engine result."""
    dish = build_dish(session, body)
    result = assess(profile_data, dish["food"], body.portion_g)
    result["considerations"] = [*result["considerations"], *dish["considerations"]]
    result["portion"] = body.portion_g
    result["source_trace"] = None
    result["dish"] = dish["block"]
    return dish["food"], result


def dish_options() -> dict:
    return {
        "cooking_notes": [
            {
                "code": code,
                "label": spec["label"],
                "detail": spec["detail"],
                "next_step": spec["next_step"],
            }
            for code, spec in COOKING_NOTES.items()
        ],
        "unknowns": list(UNKNOWNS),
        "assumptions": list(ASSUMPTIONS),
    }
