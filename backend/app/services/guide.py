"""Guide assembly: registry-backed condition detail plus the recorded-profile summary.

The response keys are unchanged from the prototype: ``exclusions``, ``recorded_limits``,
``comparison_goals``, ``condition_information``, ``unsupported_conditions``, ``questions`` and
``coverage``. ``condition_information`` keeps ``condition``/``message``/``source`` working and
adds registry-sourced detail (slug, label, category, nutrient focus, questions, confidence).
``intake_summary`` is additive and compact; the full plan lives at ``POST /api/intake/plan``.
"""

from app.schemas import ProfileData
from app.services.conditions import condition_info, resolve_conditions
from app.services.intake import build_plan

QUESTIONS = [
    "Is this the complete ingredient declaration?",
    "Are precautionary allergen statements visible?",
    "Do the nutrient units and portion match this pack?",
]


def make_guide(profile: ProfileData):
    recognised, unrecognised = resolve_conditions(profile.conditions)
    condition_information = []
    for slug in recognised:
        info = condition_info(slug)
        if info is None:
            continue
        condition_information.append(
            {
                # Legacy keys, still present and still user-facing.
                "condition": info["label"],
                "message": info["awareness"],
                "source": info["sources"][0] if info["sources"] else "",
                # Additive registry detail the client renders as a searchable card.
                "slug": info["slug"],
                "label": info["label"],
                "category": info["category"],
                "aliases": info["aliases"],
                "nutrient_focus": info["nutrient_focus"],
                "awareness": info["awareness"],
                "questions": info["questions"],
                "sources": info["sources"],
                "lab_links": info["lab_links"],
                "confidence": info["guidance_confidence"],
                "guidance_confidence": info["guidance_confidence"],
            }
        )

    plan = build_plan(profile, [])
    intake_summary = {
        "version": plan["version"],
        "target_count": len(plan["targets"]),
        "targets": [
            {
                "nutrient": target["nutrient"],
                "label": target["label"],
                "direction": target["direction"],
                "proposed_value": target["proposed_value"],
                "unit": target["unit"],
                "confidence": target["confidence"],
                "requires_clinician": target["requires_clinician"],
            }
            for target in plan["targets"]
        ],
        "notes": plan["notes"],
    }

    return {
        "exclusions": profile.allergies + profile.ingredient_exclusions,
        "recorded_limits": [x.model_dump() for x in profile.limits],
        "comparison_goals": [x.model_dump() for x in profile.goals],
        "condition_information": condition_information,
        "unsupported_conditions": unrecognised,
        "questions": QUESTIONS,
        "intake_summary": intake_summary,
        "coverage": (
            "Prototype awareness content; a selected condition does not activate a complete "
            "clinical diet."
        ),
    }
