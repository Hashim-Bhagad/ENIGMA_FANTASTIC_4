from app.schemas import FoodObservation, ProfileData
from app.services.assessment import assess


def select_replacements(
    profile: ProfileData,
    original: FoodObservation,
    products: list[tuple[str, FoodObservation]],
    portion: float | None = None,
) -> dict:
    original_result = assess(profile, original, portion)
    candidates, excluded = [], []
    for product_id, food in products:
        reason = None
        if not original.category or food.category != original.category:
            reason = "Not a confirmed comparable category"
        elif not original.basis or food.basis != original.basis:
            reason = "Missing or incompatible nutrition basis"
        result = assess(profile, food, portion)
        if reason is None and (result["conflicts"] or result["unresolved"]):
            reason = "Recorded conflict or unresolved required checks"
        comparisons, improvements = [], []
        if reason is None:
            for goal in profile.goals:
                before, after = (
                    original.nutrients.get(goal.nutrient),
                    food.nutrients.get(goal.nutrient),
                )
                if before is None or after is None:
                    reason = "Comparison nutrient is unknown"
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
                    reason = "Worsens another recorded comparison objective"
                    break
                if better:
                    improvements.append(goal.nutrient)
        if reason is None and original_result["conflicts"] and not result["conflicts"]:
            improvements.append("removes_recorded_conflicts")
        if reason is None and not improvements:
            reason = "No supported improvement established"
        if reason:
            excluded.append({"product_id": product_id, "reason": reason})
            continue
        candidates.append(
            {
                "product_id": product_id,
                "food": food.model_dump(mode="json"),
                "assessment": result,
                "comparisons": comparisons,
                "improvements": improvements,
            }
        )

    # Numeric ordering is entirely computed in code, in the user's declared goal order.
    def order(candidate):
        values = candidate["food"]["nutrients"]
        return tuple(
            values[x.nutrient] * (1 if x.direction == "lower" else -1) for x in profile.goals
        ) + (candidate["product_id"],)

    candidates.sort(key=order)
    return {
        "candidates": candidates[:5],
        "excluded": excluded,
        "ranking_method": "deterministic",
        "fallback_reason": None,
        "message": "Comparable improvements under the recorded checks."
        if candidates
        else "No eligible replacement found in the available catalog. Required checks were not relaxed.",
    }
