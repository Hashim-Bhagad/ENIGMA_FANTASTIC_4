"""Deterministic follow-up cards with optional Jev selection of one highlight."""

import asyncio
import logging

import httpx

logger = logging.getLogger(__name__)

NUTRIENT_FIELDS = {
    "sodium_mg",
    "potassium_mg",
    "phosphorus_mg",
    "carbohydrates_g",
    "protein_g",
    "fat_g",
    "saturated_fat_g",
    "sugars_g",
    "fiber_g",
    "energy_kcal",
}

# Lower numbers appear first when Jev is unavailable or uncertain. The ordering is
# a product UX fallback only; it does not change the assessment's checks or status.
PRIORITY = {
    "review_recorded_conflict": 0,
    "confirm_ingredients": 1,
    "clarify_compound_ingredients": 2,
    "check_precautionary_advisory": 3,
    "ask_preparation_and_cross_contact": 3,
    "capture_nutrition_values": 4,
    "enter_portion": 5,
    "record_clinician_limits": 6,
    "review_assessment": 7,
}


def build_followups(result: dict, food: dict) -> list[dict]:
    """Create a finite set of user-facing prompts from saved finding codes.

    Finding text is not sent to Jev. Only these approved generic cards and their IDs
    are eligible for selection, so generated/model text cannot become a new claim.
    """
    conflicts = result.get("conflicts") or []
    unresolved = result.get("unresolved") or []
    source_kind = (food.get("source") or {}).get("kind")
    grouped: dict[str, list[str]] = {}

    def collect(card_id: str, findings: list[dict]):
        grouped.setdefault(card_id, []).extend(
            str(item.get("code")) for item in findings if item.get("code")
        )

    explicit_conflicts = [
        item
        for item in conflicts
        if item.get("code")
        in {"allergen_declared", "exclusion_declared_match", "limit_portion_exceeded"}
    ]
    if explicit_conflicts:
        collect("review_recorded_conflict", explicit_conflicts)

    ingredient_findings = [
        item for item in unresolved if item.get("code") == "ingredients_not_confirmed"
    ]
    if ingredient_findings:
        collect("confirm_ingredients", ingredient_findings)

    compound_findings = [item for item in unresolved if item.get("code") == "ambiguous_ingredients"]
    if compound_findings:
        collect("clarify_compound_ingredients", compound_findings)

    advisory_findings = [
        item
        for item in [*conflicts, *unresolved]
        if item.get("code")
        in {
            "allergen_precautionary",
            "allergen_source_reported",
            "advisories_not_confirmed",
        }
    ]
    if advisory_findings:
        card = (
            "ask_preparation_and_cross_contact"
            if source_kind == "dish"
            else "check_precautionary_advisory"
        )
        collect(card, advisory_findings)

    nutrient_findings = [
        item
        for item in unresolved
        if item.get("code")
        in {
            "limit_nutrient_unknown",
            "goal_nutrient_unknown",
            "condition_carbohydrate_unknown",
            "condition_sodium_unknown",
        }
    ]
    if nutrient_findings:
        fields = sorted(
            {
                field
                for item in nutrient_findings
                if (field := item.get("field") or item.get("nutrient")) in NUTRIENT_FIELDS
            }
        )
        if fields:
            collect("capture_nutrition_values", nutrient_findings)

    portion_findings = [item for item in unresolved if item.get("code") == "portion_missing"]
    if portion_findings:
        collect("enter_portion", portion_findings)

    unsupported_findings = [
        item for item in unresolved if item.get("code") == "condition_pack_unsupported"
    ]
    if unsupported_findings:
        collect("record_clinician_limits", unsupported_findings)

    cards = []
    for card_id, codes in grouped.items():
        if card_id == "review_recorded_conflict":
            card = {
                "id": card_id,
                "title": "Review the recorded conflict",
                "question": "Would you like to review the finding and the restriction it matched?",
                "action": "Open the saved finding and check the matching label evidence and recorded restriction.",
            }
        elif card_id == "confirm_ingredients":
            card = {
                "id": card_id,
                "title": "Confirm the full ingredient panel",
                "question": "Can you photograph or enter the complete ingredient list, including compound ingredients?",
                "action": "Capture the ingredient panel and confirm it in Review; until then this check remains unresolved.",
            }
        elif card_id == "clarify_compound_ingredients":
            card = {
                "id": card_id,
                "title": "Clarify a compound ingredient",
                "question": "Can you find the specific source of the named sauce, seasoning, flavouring, or compound ingredient?",
                "action": "Check the package or ask the manufacturer for the source; keep the ingredient unresolved until confirmed.",
            }
        elif card_id == "check_precautionary_advisory":
            card = {
                "id": card_id,
                "title": "Check the precautionary statement",
                "question": "Can you check the pack's full 'may contain' or shared-facility statement?",
                "action": "Photograph the advisory panel or confirm its exact wording in Review; this does not establish absence of cross-contact.",
            }
        elif card_id == "ask_preparation_and_cross_contact":
            card = {
                "id": card_id,
                "title": "Ask about preparation and cross-contact",
                "question": "Can you ask which sauces, oils, shared pans, utensils, or preparation surfaces were used?",
                "action": "Record the cook's answer and any limits; unknown preparation or cross-contact stays unresolved.",
            }
        elif card_id == "capture_nutrition_values":
            fields = sorted(
                {
                    field
                    for item in nutrient_findings
                    if (field := item.get("field") or item.get("nutrient")) in NUTRIENT_FIELDS
                }
            )
            field_text = ", ".join(fields)
            card = {
                "id": card_id,
                "title": "Capture the missing nutrition values",
                "question": f"Can you read {field_text} from the nutrition panel and include whether values are per 100 g, per 100 ml, or per serving?",
                "action": "Photograph the full nutrition table and its basis heading; enter only values and units shown on the label.",
            }
        elif card_id == "enter_portion":
            card = {
                "id": card_id,
                "title": "Enter the portion you plan to eat",
                "question": "How many grams or millilitres will you have?",
                "action": "Enter a portion matching the saved observation's 100 g or 100 ml basis.",
            }
        else:  # record_clinician_limits
            card = {
                "id": card_id,
                "title": "Record specific clinician guidance",
                "question": "Did your clinician give you a specific food or nutrient limit to record?",
                "action": "Add only a limit you were given; unsupported condition guidance is not inferred by this app.",
            }
        card["related_findings"] = sorted(set(codes))
        cards.append(card)

    cards.sort(key=lambda card: (PRIORITY[card["id"]], card["id"]))
    return cards


async def select_followup(cards: list[dict], models) -> dict:
    """Select one approved card with Jev, or return the deterministic first card."""
    if not cards:
        return {
            "selected_question": None,
            "selection_method": "none",
            "fallback_reason": "no_followups",
            "confidence": None,
        }
    deterministic = cards[0]
    settings = models.settings
    if not settings.typesafe_api_key:
        return {
            "selected_question": deterministic,
            "selection_method": "deterministic",
            "fallback_reason": "jev_not_configured",
            "confidence": None,
        }

    options = {
        card["id"]: f"{card['title']}. Prompt: {card['question']} Action: {card['action']}"
        for card in cards
    }
    payload = {
        "model": settings.typesafe_model,
        "state": {"available_followups": options},
        "questions": {
            "followup": {
                "type": "choice",
                "instructions": (
                    "Choose the most useful available follow-up prompt for helping the user "
                    "provide missing evidence or review an existing finding. Select only an "
                    "available ID. Do not assess medical safety or infer facts."
                ),
                "criteria": options,
            }
        },
    }
    try:
        async with asyncio.timeout(5):
            response = await models.client.post(
                "https://api.typesafe.ai/v1/systemone",
                timeout=5,
                headers={"Authorization": "Bearer " + settings.typesafe_api_key.get_secret_value()},
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
        if not isinstance(data, dict) or not isinstance(data.get("model"), str):
            raise ValueError("Invalid response model")
        answers = data.get("answers")
        if not isinstance(answers, dict) or set(answers) != {"followup"}:
            raise ValueError("Unexpected Jev answer IDs")
        answer = answers["followup"]
        if not isinstance(answer, dict) or answer.get("type") != "choice":
            raise ValueError("Unexpected Jev answer type")
        choice = answer.get("choice")
        confidence = float(answer.get("confidence"))
        probabilities = answer.get("probabilities")
        if (
            choice not in options
            or not 0 <= confidence <= 1
            or not isinstance(probabilities, dict)
            or set(probabilities) != set(options)
        ):
            raise ValueError("Invalid Jev choice")
        values = [float(value) for value in probabilities.values()]
        if any(not 0 <= value <= 1 for value in values) or abs(sum(values) - 1) > 0.01:
            raise ValueError("Invalid Jev probability distribution")
        if confidence < 0.65:
            raise ValueError("Jev follow-up choice is uncertain")
        return {
            "selected_question": next(card for card in cards if card["id"] == choice),
            "selection_method": "jev_choice",
            "fallback_reason": None,
            "confidence": confidence,
            "model": data["model"],
        }
    except (httpx.HTTPError, TimeoutError, ValueError, TypeError, KeyError) as exc:
        logger.warning(
            "follow-up selection provider failed status=%s type=%s",
            getattr(getattr(exc, "response", None), "status_code", None),
            type(exc).__name__,
        )
        return {
            "selected_question": deterministic,
            "selection_method": "deterministic",
            "fallback_reason": "jev_invalid_or_unavailable",
            "confidence": None,
        }
