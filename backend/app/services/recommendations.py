"""Two-tier replacement search: verified candidates plus a review tier of unconfirmed records.

A candidate only reaches ``needs_review`` when it is blocked *solely* by unknown or
incomplete data. Anything failing a real rule stays in ``excluded``.
"""

from app.schemas import FoodObservation, ProfileData
from app.services.assessment import assess

SOURCE_SHORT = {
    "openfoodfacts": "Community record",
    "apify_off": "Community record",
    "manual": "Operator-reviewed record",
    "label_extraction": "Photo-extracted record",
    "demo": "Demo fixture",
    "dish": "Entered dish",
}


def _review_reasons(result: dict, food: FoodObservation, blocked: str | None) -> list[str]:
    """Short, specific strings derived from the candidate's unresolved findings."""
    prefix = SOURCE_SHORT.get(food.source.kind, "Unverified record")
    reasons: list[str] = []
    for item in result["unresolved"]:
        code = item["code"]
        if code == "ingredients_not_confirmed":
            reasons.append(f"{prefix}: ingredient panel not confirmed")
        elif code == "advisories_not_confirmed":
            reasons.append(f"{prefix}: advisory statement not confirmed")
        elif code == "ambiguous_ingredients":
            reasons.append("Ambiguous ingredient wording: confirm the specific source")
        elif code == "limit_nutrient_unknown":
            reasons.append(f"{item.get('field')} value missing for a limit you recorded")
        elif code == "portion_missing":
            reasons.append("Portion basis unknown")
        elif code == "goal_nutrient_unknown":
            reasons.append(f"{item.get('field')} value missing for a comparison goal")
        elif code == "condition_carbohydrate_unknown":
            reasons.append("Carbohydrate value missing for your diabetes check")
        elif code == "condition_sodium_unknown":
            reasons.append("Sodium value missing for your hypertension check")
        elif code == "condition_pack_unsupported":
            reasons.append("No specific checks cover one of your recorded conditions")
        else:
            reasons.append(item["title"])
    if blocked:
        reasons.append(blocked)
    return list(dict.fromkeys(reasons))[:10]


def select_replacements(
    profile: ProfileData,
    original: FoodObservation,
    products: list[tuple[str, FoodObservation]],
    portion: float | None = None,
) -> dict:
    original_result = assess(profile, original, portion)
    candidates, needs_review, excluded = [], [], []
    for product_id, food in products:
        result = assess(profile, food, portion)
        if not original.category or food.category != original.category:
            excluded.append(
                {"product_id": product_id, "reason": "Not a confirmed comparable category"}
            )
            continue
        if not original.basis or food.basis != original.basis:
            excluded.append(
                {"product_id": product_id, "reason": "Missing or incompatible nutrition basis"}
            )
            continue
        if result["conflicts"]:
            excluded.append({"product_id": product_id, "reason": "Recorded conflict remains"})
            continue
        comparisons, improvements, blocked = [], [], None
        for goal in profile.goals:
            before, after = (
                original.nutrients.get(goal.nutrient),
                food.nutrients.get(goal.nutrient),
            )
            if before is None or after is None:
                blocked = f"Comparison nutrient unknown: {goal.nutrient}"
                break
            change = after - before
            better = change < 0 if goal.direction == "lower" else change > 0
            worse = change > 0 if goal.direction == "lower" else change < 0
            comparisons.append(
                {
                    "nutrient": goal.nutrient,
                    "original": before,
                    "replacement": after,
                    "difference": round(change, 4),
                    "basis": food.basis,
                    "improved": better,
                }
            )
            if worse:
                blocked = "Worsens another recorded comparison objective"
                break
            if better:
                improvements.append(goal.nutrient)
        if blocked == "Worsens another recorded comparison objective":
            excluded.append({"product_id": product_id, "reason": blocked})
            continue
        if blocked is None and original_result["conflicts"] and not result["conflicts"]:
            improvements.append("removes_recorded_conflicts")
        if blocked is None and not improvements:
            excluded.append(
                {"product_id": product_id, "reason": "No supported improvement established"}
            )
            continue
        entry = {
            "product_id": product_id,
            "food": food.model_dump(mode="json"),
            "assessment": result,
            "comparisons": comparisons,
            "improvements": improvements,
        }
        reasons = _review_reasons(result, food, blocked)
        if reasons:
            needs_review.append({**entry, "verified": False, "review_reasons": reasons})
        else:
            candidates.append({**entry, "verified": True, "review_reasons": []})

    # Numeric ordering is entirely computed in code, in the user's declared goal order.
    def order(candidate):
        values = candidate["food"]["nutrients"]
        return tuple(
            values[x.nutrient] * (1 if x.direction == "lower" else -1) for x in profile.goals
        ) + (candidate["product_id"],)

    candidates.sort(key=order)
    needs_review.sort(key=lambda candidate: candidate["product_id"])
    message = (
        "Comparable improvements under the recorded checks."
        if candidates
        else "No eligible replacement found in the available catalog. Required checks were not relaxed."
    )
    if needs_review:
        message += (
            " Unverified candidates are unconfirmed community data: they failed no recorded check, "
            "but missing information prevented verification, and no check was relaxed."
        )
    return {
        "candidates": candidates[:5],
        "needs_review": needs_review[:5],
        "excluded": excluded,
        "ranking_method": "deterministic",
        "fallback_reason": None,
        "message": message,
    }
