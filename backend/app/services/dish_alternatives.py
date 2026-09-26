"""Ingredient swaps for the lines a dish check flagged.

Two sources, in this order: the reviewed catalogue in ``alternatives.py`` (deterministic) and,
only for a flagged line the catalogue does not cover, the model. Every option is then screened
against **all** of the user's recorded restrictions — allergies and ingredient exclusions — so a
swap for one allergy is never offered when it carries another. Suggestions stay labelled: they
are cooking ideas to verify on the pack, never an allergy-safety confirmation.
"""

from __future__ import annotations

from app.schemas import ProfileData
from app.services.alternatives import CATALOG
from app.services.assessment import allergen_matches
from app.services.dishes import normalize_name
from app.services.ingredient_taxonomy import match_ingredients

ALTERNATIVES_VERSION = "dish-alternatives-2026-09-26.1"
MAX_MODEL_LINES = 5
MAX_OPTIONS_PER_LINE = 3

DISCLAIMER = (
    "Swaps are cooking ideas, not allergy-safety confirmation: check the full ingredient and "
    "advisory label, and ask about cross-contact, before relying on one."
)


def catalogue_options(ingredient: str) -> dict | None:
    """The reviewed catalogue entry covering this wording, if any."""
    normalized = normalize_name(ingredient)
    for item in CATALOG:
        name = normalize_name(item["ingredient"])
        if name in normalized or normalized in name:
            return item
    return None


def conflicts_for(text: str, profile: ProfileData) -> list[str]:
    """Every recorded restriction the given wording would trip.

    Uses the same matchers as the assessment, so a suggestion is screened exactly like a
    declared ingredient: an allergy through its alias matcher, an exclusion through the
    taxonomy plus a literal fallback.
    """
    conflicts: list[str] = []
    for allergen in profile.allergies:
        if allergen_matches(text, allergen):
            conflicts.append(f"allergy:{allergen}")
    findings = match_ingredients(text)
    for phrase in profile.ingredient_exclusions:
        target = normalize_name(phrase)
        if not target:
            continue
        if phrase in text.casefold():
            conflicts.append(f"exclusion:{phrase}")
            continue
        for finding in findings:
            matched = normalize_name(finding["matched_term"])
            if matched == target or target in matched or matched in target:
                conflicts.append(f"exclusion:{phrase}")
                break
    return list(dict.fromkeys(conflicts))


def screen_options(options: list[dict], profile: ProfileData) -> tuple[list[dict], int]:
    """Keep only options that clash with nothing the user recorded. Returns (kept, dropped)."""
    kept, dropped = [], 0
    for option in options:
        text = str(option.get("text") or "").strip()
        if not text:
            continue
        conflicts = conflicts_for(text, profile)
        if conflicts:
            dropped += 1
            continue
        kept.append({**option, "text": text, "conflicts": []})
    return kept[:MAX_OPTIONS_PER_LINE], dropped


def _restriction_from_affects(finding: dict) -> str | None:
    for value in finding.get("affects", []) or []:
        if isinstance(value, str) and value.startswith("restriction:"):
            return value.split(":", 1)[1] or None
    return None


def flagged_lines(dish_block: dict, result: dict) -> list[dict]:
    """The dish lines that need a swap.

    Two sources: a deterministic conflict (its evidence names the wording that matched) and a
    model verdict of avoid/limit, which names the wording it read and the restriction it relates
    to. A line nobody could judge is a question rather than a conflict, so it is not offered
    swaps.
    """
    flagged: dict[str, dict] = {}

    def add(line_text: str, reason: str, source: str, resolved_to: str | None = None) -> None:
        entry = {"input_text": line_text, "reason": reason, "source": source}
        if resolved_to and resolved_to != line_text:
            entry["resolved_to"] = resolved_to
        flagged.setdefault(line_text, entry)

    # Model verdicts carry the wording they read in their evidence line.
    for finding in result.get("considerations", []):
        if finding.get("code") != "model_ingredient_review":
            continue
        restriction = _restriction_from_affects(finding)
        for evidence in finding.get("evidence", []) or []:
            wording = str(evidence).replace(" (model review)", "").strip()
            if wording:
                add(
                    wording,
                    f"Model reading: possible problem with {restriction}"
                    if restriction
                    else finding.get("title", ""),
                    "model",
                )

    # Deterministic conflicts: match the evidence wording back to the dish line it came from.
    known_lines = {item["input_text"]: item.get("name") for item in dish_block.get("matches", [])}
    # An exclusion can match wording the reference vocabulary never resolved, so unmatched lines
    # are candidates too: the flag came from the typed text, not from a resolved reference.
    for item in dish_block.get("unmatched", []):
        known_lines.setdefault(item["input_text"], None)
    for finding in result.get("conflicts", []):
        restriction = finding.get("restriction")
        if not restriction:
            continue
        for evidence in finding.get("evidence", []) or []:
            evidence_norm = normalize_name(str(evidence))
            if not evidence_norm:
                continue
            for line, resolved_name in known_lines.items():
                line_norm = normalize_name(line)
                if evidence_norm in line_norm or line_norm in evidence_norm:
                    add(line, f"Flagged against {restriction}", "check", resolved_name)
                    break
    return list(flagged.values())


def build_alternatives(
    dish_block: dict, result: dict, profile: ProfileData, model_options=None
) -> dict:
    """Assemble the alternatives block. ``model_options`` maps wording → model suggestions."""
    lines = flagged_lines(dish_block, result)
    entries, dropped_total = [], 0
    for line in lines:
        wording = line.get("resolved_to") or line["input_text"]
        entry = catalogue_options(wording) or catalogue_options(line["input_text"])
        source = "catalogue"
        options = (
            [{"text": text, "why": entry["reason"]} for text in entry["alternatives"]]
            if entry
            else []
        )
        if not options:
            supplied = (model_options or {}).get(line["input_text"], [])
            if supplied:
                source = "model"
                options = supplied
        screened, dropped = screen_options(options, profile)
        dropped_total += dropped
        if not screened:
            entries.append(
                {
                    **line,
                    "options": [],
                    "source": source,
                    "note": (
                        "No swap passed your recorded restrictions. Omit the ingredient or ask the "
                        "cook to confirm a replacement."
                    ),
                }
            )
            continue
        entries.append({**line, "options": screened, "source": source})

    notes = [DISCLAIMER]
    if dropped_total:
        notes.append(
            f"{dropped_total} suggested swap(s) were removed because they conflict with a recorded "
            "restriction."
        )
    if not entries:
        notes.append(
            "No ingredient in this meal matched a recorded restriction, so no swap is suggested."
        )
    return {"version": ALTERNATIVES_VERSION, "entries": entries, "notes": notes}
