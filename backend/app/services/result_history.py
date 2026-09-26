"""Serve stored assessments through the current response contract.

Findings gained stable codes, titles, next steps and a status reason after the first
records were written. Older rows are *not* rewritten: they are normalised on read, so the
stored evidence stays exactly as recorded and the API keeps one response shape.
"""

from __future__ import annotations

LEGACY_NOTE = (
    "Recorded before findings carried codes, next steps and a status reason; the stored "
    "findings are shown unchanged."
)

_SECTIONS = (
    ("conflict", "conflicts"),
    ("unresolved", "unresolved"),
    ("consideration", "considerations"),
)
_REQUIRED = ("code", "group", "title", "detail")


def _normalize_finding(finding: object, group: str) -> object:
    if not isinstance(finding, dict) or all(key in finding for key in _REQUIRED):
        return finding
    message = str(finding.get("message") or finding.get("kind") or "Recorded finding")
    defaults = {
        "code": f"legacy_{finding.get('kind') or group}",
        "group": group,
        "title": message[:160],
        "detail": message,
        "next_step": None,
        "affects": [],
        "evidence": [],
    }
    return {**defaults, **finding}


# Everything the response model requires, with the value a record written before the
# current contract can honestly claim.
_DEFAULTS: dict = {
    "rule_version": "legacy",
    "ingredient_taxonomy_version": "unknown",
    "status": "needs_information",
    "conflicts": [],
    "unresolved": [],
    "considerations": [],
    "ingredient_findings": [],
    "source_warnings": [],
    "coverage": "Recorded before the current coverage statement was added.",
}

_STATUSES = {"recorded_conflict", "needs_information", "no_matching_concern_found"}


def normalize_result(result: object) -> object:
    """Return the stored result with every field the current contract requires."""
    if not isinstance(result, dict):
        return result
    normalized = {**_DEFAULTS, **result}
    normalized["status_reason"] = normalized.get("status_reason") or LEGACY_NOTE
    if normalized.get("status") not in _STATUSES:
        # The status is derivable from the stored findings, so no verdict is invented.
        normalized["status"] = (
            "recorded_conflict"
            if normalized["conflicts"]
            else "needs_information"
            if normalized["unresolved"]
            else "no_matching_concern_found"
        )
    for group, key in _SECTIONS:
        items = normalized.get(key)
        if isinstance(items, list):
            normalized[key] = [_normalize_finding(item, group) for item in items]
    return normalized


def normalize_assessment_payload(payload: object) -> object:
    """Normalise a stored result that also carries nested assessments (a recommendation run)."""
    if not isinstance(payload, dict):
        return payload
    normalized = normalize_result(payload)
    for key in ("candidates", "needs_review"):
        items = normalized.get(key)
        if isinstance(items, list):
            normalized[key] = [
                {**item, "assessment": normalize_result(item.get("assessment"))}
                if isinstance(item, dict)
                else item
                for item in items
            ]
    return normalized
