import re

from app.schemas import FoodObservation, ProfileData
from app.services.ingredient_taxonomy import (
    TAXONOMY_VERSION,
    ambiguous_ingredient_mentions,
    is_negated,
    match_ingredients,
)

RULE_VERSION = "prototype-2026-09-26.4"
ALIASES = {
    "milk": [
        "milk",
        "whey",
        "casein",
        "caseinate",
        "butter",
        "ghee",
        "paneer",
        "cheese",
        "cream",
        "yogurt",
    ],
    "eggs": ["egg", "eggs", "albumen", "egg white", "egg yolk"],
    "soy": ["soy", "soya", "soybean", "soybeans", "tofu"],
    "peanuts": ["peanut", "peanuts", "groundnut", "groundnuts"],
    "tree_nuts": [
        "almond",
        "almonds",
        "cashew",
        "cashews",
        "walnut",
        "walnuts",
        "hazelnut",
        "hazelnuts",
        "pistachio",
        "pistachios",
        "tree nuts",
    ],
    "sesame": ["sesame", "tahini"],
    "fish": ["fish", "anchovy", "anchovies", "salmon", "tuna"],
    "shellfish": ["shrimp", "prawn", "prawns", "crab", "lobster", "shellfish"],
}
AMBIGUOUS_TERMS = [
    "natural flavour",
    "natural flavor",
    "flavouring",
    "flavoring",
    "spice mix",
    "seasoning",
]


def phrase_matches(text: str, phrase: str) -> bool:
    # A hyphen joins a compound label (e.g. sugar-free); it is not a boundary
    # proving that the standalone ingredient "sugar" was declared.
    pattern = re.compile(r"(?<![\w-])" + re.escape(phrase) + r"(?![\w-])", re.I)
    return any(not is_negated(text, item.start(), item.end()) for item in pattern.finditer(text))


def _matches_exclusion(phrase: str, ingredient_findings: list[dict], declared: str) -> list[str]:
    """Resolve known user exclusions through aliases while keeping subtypes distinct."""
    excluded_terms = match_ingredients(phrase)
    if excluded_terms:
        evidence: list[str] = []
        for excluded in excluded_terms:
            for finding in ingredient_findings:
                same_concept = (
                    (excluded["matched_term"] == "wheat" and finding["wheat_allergen"])
                    or (
                        excluded["canonical_group"] == "sugars"
                        and excluded["matched_term"] == "sugar"
                        and finding["canonical_group"] == "sugars"
                    )
                    or (excluded["canonical_identity"] == finding["canonical_identity"])
                )
                if same_concept and finding["raw_evidence"] not in evidence:
                    evidence.append(finding["raw_evidence"])
        if evidence:
            return evidence
    # Generic exclusions can remain literal; generic flour means any recognized flour.
    if phrase.strip().casefold() == "flour":
        values = [
            x["raw_evidence"]
            for x in ingredient_findings
            if x["canonical_group"] == "flour" or x["subtype"] == "wheat_flour_unspecified"
        ]
        if values:
            return values
    if excluded_terms:
        return []
    return [phrase] if phrase_matches(declared, phrase) else []


def split_advisories(text: str | None) -> tuple[str, str]:
    """Keep embedded precautionary statements out of declared-ingredient matching."""
    if not text:
        return "", ""
    match = re.search(
        r"\b(?:may\s+contain(?:s)?|may\s+be\s+present|made\s+in\s+(?:a\s+)?facility|manufactured\s+in\s+(?:a\s+)?facility)\b",
        text,
        re.I,
    )
    if match:
        return text[: match.start()], text[match.start() :]
    return text, ""


def allergen_matches(text: str | None, allergen: str) -> list[str]:
    value = text or ""
    if allergen == "wheat":
        return [item["matched_term"] for item in match_ingredients(value) if item["wheat_allergen"]]
    if allergen == "milk":
        # Only mask the milk word in a named plant beverage. Other milk/whey remains visible.
        value = re.sub(
            r"\b(almond|soy|soya|oat|coconut|rice|cashew|pea)\s+milk\b",
            r"\1 beverage",
            value,
            flags=re.I,
        )
        value = re.sub(r"\bcocoa\s+butter\b", "cocoa fat", value, flags=re.I)
    return [alias for alias in ALIASES[allergen] if phrase_matches(value, alias)]


def assess(profile: ProfileData, food: FoodObservation, portion: float | None = None) -> dict:
    conflicts, unresolved, considerations = [], [], []
    declared, embedded_advisory = split_advisories(food.ingredients_text)
    ingredient_findings = match_ingredients(declared)
    ambiguous = ambiguous_ingredient_mentions(declared, ingredient_findings)
    advisory = " ".join([food.advisories_text or "", embedded_advisory])
    for allergen in dict.fromkeys(profile.allergies):
        matches = allergen_matches(declared, allergen)
        if matches or allergen in food.declared_allergens:
            conflicts.append(
                {
                    "kind": "declared_allergen",
                    "restriction": allergen,
                    "evidence": matches or ["Source declared-allergen tag"],
                    "message": f"A recorded {allergen} allergy matches the available declaration.",
                }
            )
        precautions = allergen_matches(advisory, allergen)
        if precautions or allergen in food.precautionary_allergens:
            conflicts.append(
                {
                    "kind": "precautionary_advisory",
                    "restriction": allergen,
                    "evidence": precautions or ["Source precautionary-allergen tag"],
                    "message": f"A precautionary statement concerns your recorded {allergen} allergy.",
                }
            )
        if allergen in food.reported_allergens and not (
            matches
            or precautions
            or allergen in food.declared_allergens
            or allergen in food.precautionary_allergens
        ):
            conflicts.append(
                {
                    "kind": "source_reported_allergen",
                    "restriction": allergen,
                    "evidence": [
                        "Source allergen tag; declaration/advisory classification unconfirmed"
                    ],
                    "message": f"The source reports {allergen}; confirm the ingredient or precautionary statement on the pack.",
                }
            )
    for phrase in profile.ingredient_exclusions:
        evidence = _matches_exclusion(phrase, ingredient_findings, declared)
        if evidence:
            if phrase.strip().casefold() == "sugar":
                message = (
                    "This listing matches your broad sugar-family exclusion. It identifies ingredient wording only; "
                    "added-sugar status and amount are not inferred."
                )
            elif any(value.casefold() != phrase.casefold() for value in evidence):
                message = (
                    "The listed wording matches your exclusion through the curated ingredient-name map; "
                    "this does not infer nutrient amount or clinical equivalence."
                )
            else:
                message = f"Matches your recorded exclusion: {phrase}."
            conflicts.append(
                {
                    "kind": "ingredient_exclusion",
                    "restriction": phrase,
                    "evidence": evidence,
                    "message": message,
                }
            )

    if profile.allergies or profile.ingredient_exclusions:
        if not food.ingredients_complete:
            unresolved.append(
                {
                    "field": "ingredients",
                    "message": "The complete ingredient declaration has not been confirmed.",
                }
            )
        if not food.advisories_complete:
            unresolved.append(
                {
                    "field": "advisories",
                    "message": "Precautionary allergen statements have not been fully checked.",
                }
            )
        legacy_ambiguous = [x for x in AMBIGUOUS_TERMS if phrase_matches(declared, x)]
        if ambiguous or legacy_ambiguous:
            unresolved.append(
                {
                    "field": "ingredient_interpretation",
                    "evidence": [
                        *[item["raw_evidence"] for item in ambiguous],
                        *legacy_ambiguous,
                    ],
                    "message": "Compound or unspecified ingredients need further confirmation for this profile.",
                }
            )

    for limit in profile.limits:
        value = food.nutrients.get(limit.nutrient)
        if value is None:
            unresolved.append(
                {
                    "field": limit.nutrient,
                    "message": "The nutrient needed for your recorded limit is unknown.",
                }
            )
            continue
        if portion is None or food.basis is None:
            unresolved.append(
                {
                    "field": "portion",
                    "nutrient": limit.nutrient,
                    "message": "Specify a portion in grams or millilitres matching the nutrient basis.",
                }
            )
            continue
        amount = value * portion / 100
        detail = {
            "kind": "recorded_limit",
            "nutrient": limit.nutrient,
            "portion_amount": round(amount, 4),
            "maximum": limit.maximum,
            "scope": limit.scope,
            "source": limit.source,
        }
        if limit.scope == "portion" and amount > limit.maximum:
            conflicts.append(
                {
                    **detail,
                    "restriction": limit.nutrient,
                    "message": "This portion exceeds your recorded per-portion maximum.",
                }
            )
        else:
            if limit.scope == "daily":
                detail["daily_limit_percent"] = round(100 * amount / limit.maximum, 2)
                detail["message"] = (
                    "Contribution to your recorded daily maximum; daily consumption has not been tracked."
                )
            else:
                detail["message"] = "This portion is within the recorded per-portion maximum."
            considerations.append(detail)

    for goal in profile.goals:
        if food.nutrients.get(goal.nutrient) is None:
            unresolved.append(
                {
                    "field": goal.nutrient,
                    "message": "Comparison-goal nutrient information is unknown.",
                }
            )
    conditions = {x.casefold() for x in profile.conditions}
    if "diabetes" in conditions:
        carb = food.nutrients.get("carbohydrates_g")
        considerations.append(
            {
                "kind": "carbohydrate_awareness",
                "carbohydrates_per_basis": carb,
                "basis": food.basis,
                "message": "Review total carbohydrate and portion; sugar-free does not establish carbohydrate suitability.",
            }
        )
        if carb is None:
            unresolved.append(
                {
                    "field": "carbohydrates_g",
                    "message": "Total carbohydrate is unknown for the selected diabetes awareness pack.",
                }
            )
    if "hypertension" in conditions:
        considerations.append(
            {
                "kind": "sodium_awareness",
                "sodium_per_basis": food.nutrients.get("sodium_mg"),
                "basis": food.basis,
                "message": "Review sodium and any personally recorded limit.",
            }
        )
        if food.nutrients.get("sodium_mg") is None:
            unresolved.append(
                {
                    "field": "sodium_mg",
                    "message": "Sodium is unknown for the selected hypertension awareness pack.",
                }
            )
    if "ckd" in conditions:
        considerations.append(
            {
                "kind": "individual_guidance",
                "message": "CKD nutrient restrictions depend on individual guidance; only your explicitly recorded limits are evaluated.",
            }
        )
    unsupported = [
        x for x in profile.conditions if x.casefold() not in {"diabetes", "hypertension", "ckd"}
    ]
    if unsupported:
        unresolved.append(
            {
                "field": "condition_guidance",
                "conditions": unsupported,
                "message": "No condition-specific assessment pack is active; explicit recorded restrictions are still checked.",
            }
        )
    return {
        "rule_version": RULE_VERSION,
        "ingredient_taxonomy_version": TAXONOMY_VERSION,
        "status": "recorded_conflict"
        if conflicts
        else "needs_information"
        if unresolved
        else "no_matching_concern_found",
        "conflicts": conflicts,
        "unresolved": unresolved,
        "ingredient_findings": ingredient_findings,
        "considerations": considerations,
        "source_warnings": food.source.warnings,
        "coverage": "Checks apply only to supported recorded restrictions and available declarations; this is not an overall safety verdict.",
    }
