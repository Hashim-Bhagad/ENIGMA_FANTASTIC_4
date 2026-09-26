import re

from app.schemas import FoodObservation, ProfileData
from app.services.assessment import RULE_VERSION, assess
from app.services.conditions import awareness_codes  # noqa: E402

# Fixed engine codes plus every code the condition registry can emit, so adding a
# registry entry extends the contract instead of breaking this test.
STABLE_CODES = {
    *awareness_codes(),
    "allergen_declared",
    "allergen_precautionary",
    "allergen_source_reported",
    "exclusion_declared_match",
    "ingredients_not_confirmed",
    "advisories_not_confirmed",
    "ambiguous_ingredients",
    "limit_nutrient_unknown",
    "portion_missing",
    "limit_portion_exceeded",
    "limit_daily_contribution",
    "limit_portion_within",
    "goal_nutrient_unknown",
    "condition_carbohydrate_awareness",
    "condition_carbohydrate_unknown",
    "condition_sodium_awareness",
    "condition_sodium_unknown",
    "condition_ckd_limits_only",
    "condition_pack_unsupported",
}


def food(name="Record", **changes):
    return FoodObservation.model_validate(
        {
            "name": name,
            "category": "crackers",
            "basis": "100g",
            "ingredients_text": "Rice flour, salt",
            "advisories_text": "",
            "ingredients_complete": True,
            "advisories_complete": True,
            "nutrients": {"sodium_mg": 800, "carbohydrates_g": 60},
            "source": {"kind": "demo", "reference": "Synthetic test fixture"},
            **changes,
        }
    )


LIMIT_DAILY = {"nutrient": "sodium_mg", "maximum": 1500, "scope": "daily", "source": "Clinician"}
LIMIT_PORTION = {"nutrient": "sodium_mg", "maximum": 100, "scope": "portion", "source": "Clinician"}
LIMIT_PORTION_WIDE = {**LIMIT_PORTION, "maximum": 5000}

SCENARIOS = [
    ("declared", ProfileData(allergies=["milk"]), {"ingredients_text": "Rice, whey"}, None),
    (
        "precautionary",
        ProfileData(allergies=["peanuts"]),
        {"advisories_text": "May contain peanuts", "advisories_complete": False},
        None,
    ),
    ("reported", ProfileData(allergies=["milk"]), {"reported_allergens": ["milk"]}, None),
    (
        "exclusion",
        ProfileData(ingredient_exclusions=["sugar"]),
        {"ingredients_text": "Rice, sucrose"},
        None,
    ),
    ("ingredients-missing", ProfileData(allergies=["milk"]), {"ingredients_complete": False}, None),
    ("advisories-missing", ProfileData(allergies=["milk"]), {"advisories_complete": False}, None),
    ("ambiguous", ProfileData(allergies=["wheat"]), {"ingredients_text": "Flour"}, None),
    ("limit-unknown", ProfileData(limits=[LIMIT_DAILY]), {"nutrients": {}}, None),
    ("portion-missing", ProfileData(limits=[LIMIT_DAILY]), {}, None),
    ("portion-exceeded", ProfileData(limits=[LIMIT_PORTION]), {}, 30),
    ("limit-daily", ProfileData(limits=[LIMIT_DAILY]), {}, 30),
    ("limit-within", ProfileData(limits=[LIMIT_PORTION_WIDE]), {}, 30),
    ("goal-unknown", ProfileData(goals=[{"nutrient": "sodium_mg"}]), {"nutrients": {}}, None),
    (
        "diabetes-known",
        ProfileData(conditions=["diabetes"]),
        {},
        None,
    ),
    (
        "diabetes-unknown",
        ProfileData(conditions=["diabetes"]),
        {"nutrients": {"sodium_mg": 800}},
        None,
    ),
    ("hypertension-known", ProfileData(conditions=["hypertension"]), {}, None),
    (
        "hypertension-unknown",
        ProfileData(conditions=["hypertension"]),
        {"nutrients": {"carbohydrates_g": 60}},
        None,
    ),
    ("ckd", ProfileData(conditions=["ckd"]), {}, None),
    ("unsupported", ProfileData(conditions=["gout"]), {}, None),
]


def findings(result):
    return [*result["conflicts"], *result["unresolved"], *result["considerations"]]


def test_every_stable_code_is_emitted_by_at_least_one_scenario():
    emitted = set()
    for _name, profile, changes, portion in SCENARIOS:
        result = assess(profile, food(**changes), portion)
        emitted.update(finding["code"] for finding in findings(result))
    assert emitted == STABLE_CODES


def test_findings_carry_the_full_shape_and_valid_groups():
    for name, profile, changes, portion in SCENARIOS:
        result = assess(profile, food(**changes), portion)
        for group, items in (
            ("conflict", result["conflicts"]),
            ("unresolved", result["unresolved"]),
            ("consideration", result["considerations"]),
        ):
            for finding in items:
                assert finding["code"] in STABLE_CODES, (name, finding["code"])
                assert finding["group"] == group
                assert 2 <= len(finding["title"]) <= 160
                assert 2 <= len(finding["detail"]) <= 700
                assert finding["next_step"] is None or len(finding["next_step"]) <= 400
                assert isinstance(finding["affects"], list)
                assert 2 <= len(finding["message"]) <= 400
                assert isinstance(finding["evidence"], list)
        unique = {
            (item["code"], item.get("field") or item.get("nutrient"))
            for item in result["unresolved"]
        }
        assert len(unique) == len(result["unresolved"])


def test_unresolved_findings_are_specific_and_never_only_an_unconfirmed_note():
    specific = {
        "ingredients_not_confirmed": ("ingredient list", "cannot be excluded"),
        "advisories_not_confirmed": ("advisory text", "cannot be ruled out"),
        "ambiguous_ingredients": ("does not name its source", "cannot be excluded"),
        "limit_nutrient_unknown": ("recorded limit", "cannot be checked"),
        "portion_missing": ("no portion was supplied",),
        "goal_nutrient_unknown": ("cannot be compared",),
        "condition_carbohydrate_unknown": ("total carbohydrate value is missing",),
        "condition_sodium_unknown": ("sodium value is missing",),
        "condition_pack_unsupported": ("No supported awareness pack covers",),
    }
    for name, profile, changes, portion in SCENARIOS:
        result = assess(profile, food(**changes), portion)
        for finding in result["unresolved"]:
            code = finding["code"]
            assert finding["next_step"], (name, code)
            assert len(finding["detail"]) >= 60, (name, code, finding["detail"])
            # Never a bare "has not been confirmed" style sentence.
            assert not re.fullmatch(
                r"(?i)\s*(?:the |this )?[^.]*\bnot\b[^.]*confirmed\.?\s*", finding["detail"]
            ), (name, code)
            tokens = specific[code]
            assert any(token in finding["detail"] for token in tokens), (name, code)
        assert result["status_reason"]
        assert result["status_reason"].endswith(".")
        assert result["rule_version"] == RULE_VERSION


def test_duplicate_unresolved_blockers_are_deduplicated_per_code_and_field():
    profile = ProfileData(
        limits=[
            {**LIMIT_DAILY, "maximum": 1500},
            {**LIMIT_DAILY, "scope": "portion", "maximum": 2000},
        ]
    )
    result = assess(profile, food(), None)
    portion_missing = [x for x in result["unresolved"] if x["code"] == "portion_missing"]
    assert len(portion_missing) == 1
    assert portion_missing[0]["field"] == "portion"


def test_status_reason_explains_the_overall_status():
    conflict = assess(ProfileData(allergies=["milk"]), food(ingredients_text="Rice, whey"))
    assert conflict["status"] == "recorded_conflict"
    assert "conflict" in conflict["status_reason"].lower()

    unresolved = assess(ProfileData(allergies=["milk"]), food(ingredients_complete=False))
    assert unresolved["status"] == "needs_information"
    assert "could not complete" in unresolved["status_reason"]

    clean = assess(ProfileData(allergies=["milk"]), food())
    assert clean["status"] == "no_matching_concern_found"
    assert "no match" in clean["status_reason"]
