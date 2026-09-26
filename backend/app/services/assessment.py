import re

from app.schemas import FoodObservation, ProfileData
from app.services.ingredient_taxonomy import (
    TAXONOMY_VERSION,
    ambiguous_ingredient_mentions,
    is_negated,
    match_ingredients,
)

RULE_VERSION = "prototype-2026-09-26.5"
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
# Human-readable origin of each record kind, used to say where a finding comes from.
SOURCE_LABELS = {
    "openfoodfacts": "a community source",
    "apify_off": "a community source",
    "manual": "an operator-reviewed label",
    "label_extraction": "a photo-extracted label",
    "demo": "a demonstration fixture",
    "dish": "the cooked dish you entered",
}


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


def source_label(food: FoodObservation) -> str:
    return SOURCE_LABELS.get(food.source.kind, "an imported record")


def nutrient_unit(nutrient: str) -> str:
    return {"_mg": "mg", "_kcal": "kcal", "_g": "g"}.get(nutrient[-3:], "")


def restriction_phrase(profile: ProfileData) -> str:
    """Name the recorded restrictions a missing declaration could hide a match for."""
    items = [f"your {allergen} allergy" for allergen in profile.allergies]
    items.extend(f"your {phrase} exclusion" for phrase in profile.ingredient_exclusions)
    if not items:
        return "your recorded restrictions"
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + " and " + items[-1]


def restriction_affects(profile: ProfileData) -> list[str]:
    return [
        *[f"allergy:{allergen}" for allergen in profile.allergies],
        *[f"exclusion:{phrase}" for phrase in profile.ingredient_exclusions],
    ]


def finding(
    code: str,
    group: str,
    title: str,
    detail: str,
    *,
    message: str,
    next_step: str | None = None,
    affects: list[str] | None = None,
    evidence: list[str] | None = None,
    **extra,
) -> dict:
    """One findings-v2 row: stable code plus specific, actionable wording."""
    return {
        "code": code,
        "group": group,
        "title": title,
        "detail": detail,
        "next_step": next_step,
        "affects": list(dict.fromkeys(affects or [])),
        "message": message,
        "evidence": list(evidence or []),
        **extra,
    }


def dedupe(findings: list[dict]) -> list[dict]:
    """Collapse findings sharing a code and field/nutrient so the UI shows one blocker."""
    seen: dict[tuple, dict] = {}
    ordered: list[dict] = []
    for item in findings:
        key = (
            item["code"],
            item.get("field") or item.get("nutrient") or item.get("restriction"),
        )
        existing = seen.get(key)
        if existing is not None:
            for field in ("evidence", "affects"):
                existing[field] = list(dict.fromkeys([*existing[field], *item[field]]))
            continue
        seen[key] = item
        ordered.append(item)
    return ordered


def assess(profile: ProfileData, food: FoodObservation, portion: float | None = None) -> dict:
    conflicts, unresolved, considerations = [], [], []
    declared, embedded_advisory = split_advisories(food.ingredients_text)
    ingredient_findings = match_ingredients(declared)
    ambiguous = ambiguous_ingredient_mentions(declared, ingredient_findings)
    advisory = " ".join([food.advisories_text or "", embedded_advisory])
    origin = source_label(food)
    restrictions = restriction_phrase(profile)
    for allergen in dict.fromkeys(profile.allergies):
        matches = allergen_matches(declared, allergen)
        affects = [f"allergy:{allergen}"]
        if matches or allergen in food.declared_allergens:
            terms = ", ".join(matches) if matches else "the source's declared-allergen tag"
            conflicts.append(
                finding(
                    "allergen_declared",
                    "conflict",
                    f"Declared {allergen} found",
                    f"The ingredient panel reports {terms}, which matches your recorded {allergen} "
                    "allergy; this record fails that restriction.",
                    message=f"A recorded {allergen} allergy matches the available declaration.",
                    affects=affects,
                    evidence=matches or ["Source declared-allergen tag"],
                    kind="declared_allergen",
                    restriction=allergen,
                )
            )
        precautions = allergen_matches(advisory, allergen)
        if precautions or allergen in food.precautionary_allergens:
            terms = (
                ", ".join(precautions) if precautions else "the source's precautionary-allergen tag"
            )
            conflicts.append(
                finding(
                    "allergen_precautionary",
                    "conflict",
                    f"Precautionary advisory: {allergen}",
                    f"A precautionary statement names {terms}, warning of possible cross-contact "
                    f"with {allergen} rather than a declared ingredient.",
                    message=f"A precautionary statement concerns your recorded {allergen} allergy.",
                    next_step="Check the pack for how this advisory applies to the batch, and set "
                    "it aside if your clinician advises avoiding it.",
                    affects=affects,
                    evidence=precautions or ["Source precautionary-allergen tag"],
                    kind="precautionary_advisory",
                    restriction=allergen,
                )
            )
        if allergen in food.reported_allergens and not (
            matches
            or precautions
            or allergen in food.declared_allergens
            or allergen in food.precautionary_allergens
        ):
            conflicts.append(
                finding(
                    "allergen_source_reported",
                    "conflict",
                    f"Source tag reports {allergen}",
                    f"The catalog record tags {allergen}, but its ingredient and precautionary "
                    "text does not show it, so the tag may be stale or describe a different variant.",
                    message=f"The source reports {allergen}; confirm the ingredient or "
                    "precautionary statement on the pack.",
                    next_step=f"Check the pack's ingredient panel for {allergen} before trusting "
                    "this record.",
                    affects=affects,
                    evidence=[
                        "Source allergen tag; declaration/advisory classification unconfirmed"
                    ],
                    kind="source_reported_allergen",
                    restriction=allergen,
                )
            )
    for phrase in profile.ingredient_exclusions:
        evidence = _matches_exclusion(phrase, ingredient_findings, declared)
        if not evidence:
            continue
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
            finding(
                "exclusion_declared_match",
                "conflict",
                f"Exclusion match: {phrase[:50]}",
                f"The listed wording ({', '.join(evidence)}) matches your recorded exclusion "
                f"'{phrase}', so this record fails that restriction.",
                message=message,
                affects=[f"exclusion:{phrase}"],
                evidence=evidence,
                kind="ingredient_exclusion",
                restriction=phrase,
            )
        )

    if profile.allergies or profile.ingredient_exclusions:
        declaration_affects = ["field:ingredients", *restriction_affects(profile)]
        advisory_affects = ["field:advisories", *restriction_affects(profile)]
        cooked = food.source.kind == "dish"
        if not food.ingredients_complete:
            unresolved.append(
                finding(
                    "ingredients_not_confirmed",
                    "unresolved",
                    "Ingredient list not confirmed" if cooked else "Ingredient panel not confirmed",
                    f"This record comes from {origin}, so the ingredient list may be "
                    f"incomplete; {restrictions} cannot be excluded from this text.",
                    message="The complete ingredient declaration has not been confirmed.",
                    next_step=(
                        "Tick the ingredient-list confirmation on the meal check once every "
                        "ingredient, sauce, oil and topping is listed."
                        if cooked
                        else "Open the pack, photograph the ingredient panel, and mark Ingredients "
                        "complete in Review."
                    ),
                    affects=declaration_affects,
                    field="ingredients",
                )
            )
        if not food.advisories_complete:
            unresolved.append(
                finding(
                    "advisories_not_confirmed",
                    "unresolved",
                    "No packaged advisory panel" if cooked else "Advisory panel not confirmed",
                    f"A cooked dish has no packaged 'may contain' statement, so shared equipment, "
                    f"oil and cross-contact with {restrictions} stay unverified."
                    if cooked
                    else f"This record comes from {origin}, and no precautionary ('may contain') "
                    f"statement was recorded; {restrictions} cannot be ruled out from the advisory text.",
                    message="Precautionary allergen statements have not been fully checked.",
                    next_step=(
                        "Ask the cook about shared pans, oil and utensils, then tick the "
                        "confirmation box if you accept that limit."
                        if cooked
                        else "Check the pack for a 'may contain' statement and mark Advisories "
                        "complete in Review."
                    ),
                    affects=advisory_affects,
                    field="advisories",
                )
            )
        legacy_ambiguous = [x for x in AMBIGUOUS_TERMS if phrase_matches(declared, x)]
        if ambiguous or legacy_ambiguous:
            terms = [*[item["raw_evidence"] for item in ambiguous], *legacy_ambiguous]
            joined = ", ".join(dict.fromkeys(terms))
            unresolved.append(
                finding(
                    "ambiguous_ingredients",
                    "unresolved",
                    "Compound ingredient needs confirmation",
                    f"The list uses compound or unspecified wording ({joined}) that does not name "
                    f"its source, so {restrictions} cannot be excluded from it.",
                    message="Compound or unspecified ingredients need further confirmation for this profile.",
                    next_step=f"Ask the manufacturer or read the pack for the specific source named "
                    f"by: {joined}.",
                    affects=["field:ingredient_interpretation", *restriction_affects(profile)],
                    evidence=terms,
                    field="ingredient_interpretation",
                )
            )

    for limit in profile.limits:
        value = food.nutrients.get(limit.nutrient)
        unit = nutrient_unit(limit.nutrient)
        if value is None:
            unresolved.append(
                finding(
                    "limit_nutrient_unknown",
                    "unresolved",
                    f"{limit.nutrient} unknown for your limit",
                    f"No {limit.nutrient} value is available on the declared basis, so your "
                    f"recorded limit of {limit.maximum} {unit} ({limit.source}) cannot be checked "
                    "against this record.",
                    message="The nutrient needed for your recorded limit is unknown.",
                    next_step=f"Find the {limit.nutrient} value on the nutrition panel and enter it "
                    "in Review.",
                    affects=[f"limit:{limit.nutrient}"],
                    field=limit.nutrient,
                )
            )
            continue
        if portion is None or food.basis is None:
            unresolved.append(
                finding(
                    "portion_missing",
                    "unresolved",
                    "Portion not given for your limit",
                    f"Your recorded {limit.nutrient} limit is checked per portion in the declared "
                    f"{food.basis or '100g/100ml'} basis; no portion was supplied, so the "
                    "contribution cannot be calculated.",
                    message="Specify a portion in grams or millilitres matching the nutrient basis.",
                    next_step="Enter the portion you will eat in grams or millilitres.",
                    affects=[f"limit:{limit.nutrient}"],
                    field="portion",
                    nutrient=limit.nutrient,
                )
            )
            continue
        amount = value * portion / 100
        base = {
            "kind": "recorded_limit",
            "nutrient": limit.nutrient,
            "portion_amount": round(amount, 4),
            "maximum": limit.maximum,
            "scope": limit.scope,
            "source": limit.source,
        }
        if limit.scope == "portion" and amount > limit.maximum:
            conflicts.append(
                finding(
                    "limit_portion_exceeded",
                    "conflict",
                    f"Portion exceeds {limit.nutrient} maximum",
                    f"This portion supplies {round(amount, 4)} {unit} against your recorded "
                    f"per-portion maximum of {limit.maximum} {unit} ({limit.source}).",
                    message="This portion exceeds your recorded per-portion maximum.",
                    next_step=f"Reduce the portion or choose a record with less {limit.nutrient}.",
                    affects=[f"limit:{limit.nutrient}"],
                    evidence=[limit.source],
                    restriction=limit.nutrient,
                    **base,
                )
            )
        else:
            if limit.scope == "daily":
                base["daily_limit_percent"] = round(100 * amount / limit.maximum, 2)
                title = f"{limit.nutrient} is {base['daily_limit_percent']}% of your daily limit"
                text = (
                    f"This portion supplies {round(amount, 4)} {unit}, "
                    f"{base['daily_limit_percent']}% of your recorded daily {limit.nutrient} "
                    f"maximum of {limit.maximum} {unit} ({limit.source}); intake across the rest "
                    "of the day is not tracked."
                )
                message = "Contribution to your recorded daily maximum; daily consumption has not been tracked."
                code = "limit_daily_contribution"
            else:
                title = f"Within your {limit.nutrient} portion maximum"
                text = (
                    f"This portion supplies {round(amount, 4)} {unit}, within your recorded "
                    f"per-portion {limit.nutrient} maximum of {limit.maximum} {unit} "
                    f"({limit.source})."
                )
                message = "This portion is within the recorded per-portion maximum."
                code = "limit_portion_within"
            considerations.append(
                finding(
                    code,
                    "consideration",
                    title,
                    text,
                    message=message,
                    affects=[f"limit:{limit.nutrient}"],
                    evidence=[limit.source],
                    **base,
                )
            )

    for goal in profile.goals:
        if food.nutrients.get(goal.nutrient) is None:
            unresolved.append(
                finding(
                    "goal_nutrient_unknown",
                    "unresolved",
                    f"{goal.nutrient} unknown for your goal",
                    f"No {goal.nutrient} value is available on the declared basis, so this record "
                    f"cannot be compared against your '{goal.direction}' goal.",
                    message="Comparison-goal nutrient information is unknown.",
                    next_step=f"Find the {goal.nutrient} value on the nutrition panel before "
                    "comparing alternatives.",
                    affects=[f"goal:{goal.nutrient}"],
                    field=goal.nutrient,
                )
            )
    conditions = {x.casefold() for x in profile.conditions}
    if "diabetes" in conditions:
        carb = food.nutrients.get("carbohydrates_g")
        carb_text = "unknown on this record" if carb is None else f"{carb} g per {food.basis}"
        considerations.append(
            finding(
                "condition_carbohydrate_awareness",
                "consideration",
                "Diabetes awareness: review carbohydrate",
                f"Diabetes awareness pack: this record lists total carbohydrate as {carb_text}; "
                "review it against the portion you will eat, because sugar-free wording does not "
                "establish carbohydrate suitability.",
                message="Review total carbohydrate and portion; sugar-free does not establish "
                "carbohydrate suitability.",
                next_step="Check the portion against the carbohydrate guidance from your clinician.",
                affects=["condition:diabetes", "nutrient:carbohydrates_g"],
                kind="carbohydrate_awareness",
                carbohydrates_per_basis=carb,
                basis=food.basis,
            )
        )
        if carb is None:
            unresolved.append(
                finding(
                    "condition_carbohydrate_unknown",
                    "unresolved",
                    "Carbohydrate unknown for diabetes awareness",
                    "You recorded diabetes, but the total carbohydrate value is missing, so this "
                    "portion cannot be reviewed for carbohydrate.",
                    message="Total carbohydrate is unknown for the selected diabetes awareness pack.",
                    next_step="Find the total carbohydrate value on the nutrition panel.",
                    affects=["condition:diabetes", "nutrient:carbohydrates_g"],
                    field="carbohydrates_g",
                )
            )
    if "hypertension" in conditions:
        sodium = food.nutrients.get("sodium_mg")
        considerations.append(
            finding(
                "condition_sodium_awareness",
                "consideration",
                "Hypertension awareness: review sodium",
                "Hypertension awareness pack: this record lists sodium as "
                f"{'unknown' if sodium is None else f'{sodium} mg per {food.basis}'}; review it "
                "against any personal limit you recorded.",
                message="Review sodium and any personally recorded limit.",
                next_step="Compare the portion's sodium with the limit your clinician gave you.",
                affects=["condition:hypertension", "nutrient:sodium_mg"],
                kind="sodium_awareness",
                sodium_per_basis=sodium,
                basis=food.basis,
            )
        )
        if sodium is None:
            unresolved.append(
                finding(
                    "condition_sodium_unknown",
                    "unresolved",
                    "Sodium unknown for hypertension awareness",
                    "You recorded hypertension, but the sodium value is missing, so this portion "
                    "cannot be reviewed for sodium.",
                    message="Sodium is unknown for the selected hypertension awareness pack.",
                    next_step="Find the sodium value on the nutrition panel.",
                    affects=["condition:hypertension", "nutrient:sodium_mg"],
                    field="sodium_mg",
                )
            )
    if "ckd" in conditions:
        considerations.append(
            finding(
                "condition_ckd_limits_only",
                "consideration",
                "CKD: only your recorded limits are checked",
                "Kidney nutrient guidance depends on individual clinical advice, so this "
                "assessment evaluates only the limits, allergies and exclusions you recorded.",
                message="CKD nutrient restrictions depend on individual guidance; only your "
                "explicitly recorded limits are evaluated.",
                affects=["condition:ckd"],
                kind="individual_guidance",
            )
        )
    unsupported = [
        x for x in profile.conditions if x.casefold() not in {"diabetes", "hypertension", "ckd"}
    ]
    if unsupported:
        joined = ", ".join(unsupported)
        unresolved.append(
            finding(
                "condition_pack_unsupported",
                "unresolved",
                "No awareness pack for a recorded condition",
                f"No supported awareness pack covers {joined}, so only your explicitly recorded "
                "limits, allergies, exclusions and goals were checked.",
                message="No condition-specific assessment pack is active; explicit recorded "
                "restrictions are still checked.",
                next_step="Record any specific restriction your clinician gave you as a limit, "
                "allergy or exclusion.",
                affects=[f"condition:{x}" for x in unsupported],
                field="condition_guidance",
                conditions=unsupported,
            )
        )

    conflicts, unresolved, considerations = (
        dedupe(conflicts),
        dedupe(unresolved),
        dedupe(considerations),
    )
    if conflicts:
        failed = ", ".join(sorted({x["restriction"] for x in conflicts}))
        status_reason = (
            f"{len(conflicts)} conflict(s) with your recorded restrictions were found ({failed}), "
            "so this record fails a recorded check."
        )
        status = "recorded_conflict"
    elif unresolved:
        status_reason = (
            f"No conflict was found, but {len(unresolved)} required check(s) could not complete "
            "with the information available, so the result is inconclusive."
        )
        status = "needs_information"
    else:
        status_reason = (
            "All supported checks ran on the available declarations and found no match with your "
            "recorded restrictions."
        )
        status = "no_matching_concern_found"
    return {
        "rule_version": RULE_VERSION,
        "ingredient_taxonomy_version": TAXONOMY_VERSION,
        "status": status,
        "status_reason": status_reason,
        "conflicts": conflicts,
        "unresolved": unresolved,
        "ingredient_findings": ingredient_findings,
        "considerations": considerations,
        "source_warnings": food.source.warnings,
        "coverage": "Checks apply only to supported recorded restrictions and available declarations; this is not an overall safety verdict.",
    }
