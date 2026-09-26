"""The model fallback for ingredient wording the deterministic pass could not resolve.

A dish check resolves typed lines against a fixed reference vocabulary, so an everyday word the
vocabulary does not carry (``masala``, ``spice mix``, a house blend) stays unmatched and the check
says nothing about it. When the deterministic pass found no conflict and left such a line
unresolved, that wording is sent to the model once and the verdicts come back as ordinary
findings labelled ``model_estimate``.

Two rules keep that honest. A model row is always presented as a language judgement about the
wording that was typed: never a verified label match, never a diagnosis, and never carrying a
nutrient amount or a dose. And a row that found nothing is never shown as a clearance —
``no_concern_found`` produces no finding at all and stays only in the review block, because a
model's silence about a wording is not proof that the food is safe.
"""

from __future__ import annotations

from app.services.assessment import finding

# The vocabulary the provider is told to answer with. A row outside it is dropped rather than
# repaired into a verdict the model never gave.
INGREDIENT_REVIEW_VERDICTS = ("avoid", "limit", "no_concern_found", "cannot_determine")
INGREDIENT_REVIEW_CONFIDENCE = ("high", "medium", "low")

MODEL_REVIEW_CODE = "model_ingredient_review"
MODEL_UNCLEAR_CODE = "model_ingredient_unclear"
# Bound on the findings one review may add, so a long list of unresolved wording cannot bury the
# deterministic findings under model output.
MAX_MODEL_FINDINGS = 12
MODEL_REVIEW_NEXT_STEP = "Check the pack's ingredient list before relying on this meal."

REVIEW_STATUSES = ("applied", "skipped", "unavailable")
REVIEW_DISCLAIMER = (
    "This review is a language judgement about the wording that was typed, not a verified "
    "analysis of the product. It is not a diagnosis, it gives no nutrient amount, and a missing "
    "finding is not a clearance."
)

MESSAGE_APPLIED = (
    "A model reviewed the wording of the lines the reference vocabulary could not resolve. Each "
    "finding below is labelled as that model's language judgement, not a verified match against "
    "a product label."
)
MESSAGE_SKIPPED_DISABLED = (
    "Model review of the wording was turned off for this check, so every line rests on the "
    "reference check alone."
)
MESSAGE_SKIPPED_NOT_NEEDED = (
    "No wording review was needed: the reference check either resolved every line or already "
    "found a conflict, so nothing was left to interpret."
)
MESSAGE_UNAVAILABLE = (
    "The wording review could not run, so the lines it would have covered are unchecked: check "
    "the pack's ingredient list before relying on this meal."
)

# A finding is rebuilt into the frozen schema, so the wording kept in it is length-capped here
# rather than left to fail response validation.
_LABEL_LIMIT = 140
_NOT_A_LABEL_MATCH = (
    "A model judged the wording you typed and not a verified ingredient label, so this is not a "
    "matched fact: confirm the pack before relying on this meal."
)


def needs_review(food, result, unmatched) -> bool:
    """True only when the deterministic pass neither resolved a line nor found a conflict.

    ``unmatched`` is the dish block's list of lines no reference food matched, and ``result`` is
    the finished deterministic assessment. One unmatched line is enough to ask, but a conflict
    the deterministic pass already recorded — including an ingredient-exclusion match — means the
    check is not silent, so the model is never consulted then. Its verdicts must not be able to
    bury, soften or replace a finding the deterministic rules already produced.
    """
    if not unmatched:
        return False
    if result.get("conflicts") or result.get("status") == "recorded_conflict":
        return False
    return True


def apply_verdicts(dish_block, result, verdicts) -> dict:
    """Map model verdicts onto labelled findings and append them to ``result``.

    Only lines the deterministic pass could not resolve are in scope: ``dish_block`` is the dish
    result, so a row about any other wording is dropped. ``avoid`` and ``limit`` become
    considerations, ``cannot_determine`` becomes an unresolved interpretation gap, and
    ``no_concern_found`` produces no finding at all — it stays in the review block so the wording
    still reads as looked at. No nutrient number is ever emitted, no verdict is an instruction to
    eat or avoid the food, and none of them changes ``status``.
    """
    unresolved_texts = {
        item.get("input_text", "").strip().casefold() for item in dish_block.get("unmatched", [])
    }
    produced = 0
    for row in verdicts:
        if produced >= MAX_MODEL_FINDINGS:
            break
        text = row.get("input_text")
        if not isinstance(text, str) or text.strip().casefold() not in unresolved_texts:
            continue
        verdict = row.get("verdict")
        if verdict not in INGREDIENT_REVIEW_VERDICTS:
            continue
        if verdict == "no_concern_found":
            # A model's silence about a wording is not a clearance, so it never becomes a finding.
            continue
        short = text.strip()[:_LABEL_LIMIT]
        restriction = row.get("matched_restriction")
        reason = row.get("reason") or "the model gave no reason"
        related = f"your recorded {restriction}" if restriction else "the restrictions you recorded"
        affects = [f"restriction:{restriction}"] if restriction else [f"ingredient:{short}"]
        evidence = [f"{short} (model review)"]
        if verdict == "avoid":
            result["considerations"].append(
                finding(
                    MODEL_REVIEW_CODE,
                    "consideration",
                    f"Possible conflict: {short}",
                    f"A model read “{short}” as related to {related} and flagged a possible "
                    f"conflict: {reason} {_NOT_A_LABEL_MATCH}",
                    message=f"A model's wording review flagged this line against {related}.",
                    next_step=MODEL_REVIEW_NEXT_STEP,
                    affects=affects,
                    evidence=evidence,
                    confidence="model_estimate",
                )
            )
        elif verdict == "limit":
            result["considerations"].append(
                finding(
                    MODEL_REVIEW_CODE,
                    "consideration",
                    f"Limit or check: {short}",
                    f"A model read “{short}” as related to {related} and suggests limiting or "
                    f"double-checking it: {reason} {_NOT_A_LABEL_MATCH}",
                    message=f"A model's wording review suggests limiting or checking this line "
                    f"against {related}.",
                    next_step=MODEL_REVIEW_NEXT_STEP,
                    affects=affects,
                    evidence=evidence,
                    confidence="model_estimate",
                )
            )
        else:
            result["unresolved"].append(
                finding(
                    MODEL_UNCLEAR_CODE,
                    "unresolved",
                    f"Could not judge: {short}",
                    f"The wording “{short}” is too general to judge: {reason} A name like this "
                    "hides which ingredients it contains, so it supports neither a match with a "
                    "recorded restriction nor a clearance, and nothing was concluded either way.",
                    message="This line is too general for a match or a clearance.",
                    next_step=MODEL_REVIEW_NEXT_STEP,
                    affects=affects,
                    evidence=evidence,
                    field="ingredient_interpretation",
                    confidence="model_estimate",
                )
            )
        produced += 1
    return result


def build_review_block(verdicts, status, message) -> dict:
    """The review as the UI should read it: labelled, and never silent about what was read.

    ``verdicts`` keeps every row the model returned for a reviewed line, including
    ``no_concern_found`` ones, so the screen can show that a wording was read without presenting
    that as safety.
    """
    if status not in REVIEW_STATUSES:
        raise ValueError(f"Unsupported review status: {status}")
    return {
        "status": status,
        "verdicts": [
            {
                "input_text": row.get("input_text"),
                "verdict": row.get("verdict"),
                "reason": row.get("reason"),
                "matched_restriction": row.get("matched_restriction"),
                "confidence": row.get("confidence"),
            }
            for row in verdicts
        ],
        "message": message,
        "disclaimer": REVIEW_DISCLAIMER,
    }
