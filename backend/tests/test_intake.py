"""Intake plan behaviour: triggers, evidence, and the safety boundary.

The plan only proposes; these tests pin the deterministic parts — which rule fires for
which lab value, what evidence travels with a target, and the rules that must never
produce a number.
"""

import pytest

from app.schemas import ProfileData
from app.services.conditions import awareness_codes, registry_payload, resolve_conditions
from app.services.intake import build_plan

REPORT_DATE = "2026-09-20"


def parameter(key, value, *, unit=None, low=None, high=None, status=None):
    return {
        "key": key,
        "label": key.replace("_", " "),
        "value": value,
        "unit": unit,
        "reference_low": low,
        "reference_high": high,
        "reference_source": "document" if low is not None or high is not None else "unknown",
        "status": status or ("high" if high is not None and value > high else "normal"),
    }


def report(report_id, parameters, status="confirmed"):
    return {
        "id": report_id,
        "collected_on": REPORT_DATE,
        "parameters": parameters,
        "status": status,
    }


def profile(**changes):
    return ProfileData.model_validate({"sex": "female", "age_band": "45_59", **changes})


def target_for(plan, nutrient):
    return next((item for item in plan["targets"] if item["nutrient"] == nutrient), None)


def test_hba1c_and_fasting_glucose_propose_a_sugar_limit():
    plan = build_plan(
        profile(),
        [report("r1", [parameter("hba1c_percent", 7.4, unit="%", low=4.0, high=5.6)])],
    )
    sugars = target_for(plan, "sugars_g")
    assert sugars is not None
    assert sugars["proposed_value"] == 25
    assert sugars["direction"] == "lower"
    assert sugars["confidence"] == "established"
    # The value is shown and the flag asks for clinician confirmation; it is not suppressed.
    assert sugars["requires_clinician"] is True
    assert sugars["suggested_limit_source"].startswith("Report 2026-09-20")
    assert "rule " in sugars["suggested_limit_source"]
    assert any(item["parameter_key"] == "hba1c_percent" for item in sugars["evidence"]), (
        "the lab value that triggered the rule must travel as evidence"
    )
    assert plan["reports_used"] == ["r1"]


def test_blood_pressure_proposes_the_hypertension_sodium_target():
    plan = build_plan(profile(), [report("r1", [parameter("systolic_bp_mmhg", 138, unit="mmHg")])])
    sodium = target_for(plan, "sodium_mg")
    assert sodium is not None
    assert sodium["proposed_value"] == 1500
    assert sodium["baseline_value"] == 2000
    assert any(item["parameter_key"] == "systolic_bp_mmhg" for item in sodium["evidence"])


def test_lipids_propose_a_saturated_fat_limit_and_a_fibre_target():
    plan = build_plan(
        profile(),
        [report("r1", [parameter("ldl_cholesterol_mg_dl", 151, unit="mg/dL", high=100)])],
    )
    saturated = target_for(plan, "saturated_fat_g")
    assert saturated is not None and saturated["proposed_value"] is not None
    fibre = target_for(plan, "fiber_g")
    assert fibre is not None and fibre["proposed_value"] >= 25


def test_low_haemoglobin_uses_the_sex_aware_low_reference():
    below = build_plan(
        profile(sex="female"),
        [report("r1", [parameter("hemoglobin_g_dl", 11.5, unit="g/dL", low=12.0, high=15.0)])],
    )
    assert target_for(below, "iron") is not None, "11.5 g/dL is below the female low reference"

    above = build_plan(
        profile(sex="female"),
        [report("r1", [parameter("hemoglobin_g_dl", 12.5, unit="g/dL", low=12.0, high=15.0)])],
    )
    assert target_for(above, "iron") is None

    unknown_sex = build_plan(
        profile(sex="unspecified"),
        [report("r1", [parameter("hemoglobin_g_dl", 11.5, unit="g/dL", low=12.0, high=15.0)])],
    )
    iron = target_for(unknown_sex, "iron")
    assert iron is not None
    assert any("widened range" in item["detail"] for item in iron["evidence"]), (
        "an unspecified sex must state that the widened low reference was used"
    )


def test_unconfirmed_reports_never_drive_a_proposal():
    plan = build_plan(
        profile(),
        [
            report(
                "r1",
                [parameter("hba1c_percent", 7.4, unit="%", low=4.0, high=5.6)],
                status="extracted",
            )
        ],
    )
    assert plan["targets"] == []
    assert plan["reports_used"] == []
    assert any("confirmed" in note for note in plan["notes"])


def test_clinician_only_rules_never_carry_a_number():
    plan = build_plan(profile(conditions=["ckd"]), [])
    clinician = [item for item in plan["targets"] if item["confidence"] == "clinician_only"]
    assert clinician, "CKD must produce clinician-only entries"
    assert all(item["proposed_value"] is None for item in clinician)
    assert all(item["requires_clinician"] is True for item in clinician)
    # A flagged-but-numeric proposal is a different thing and must keep its number.
    assert all(
        item["proposed_value"] is not None
        for item in plan["targets"]
        if item["requires_clinician"] and item["confidence"] != "clinician_only"
    )


def test_one_nutrient_merges_to_the_strictest_target_with_all_evidence():
    plan = build_plan(
        profile(conditions=["gout"]),
        [report("r1", [parameter("uric_acid_mg_dl", 7.4, unit="mg/dL", high=6.0)])],
    )
    sugars = [item for item in plan["targets"] if item["nutrient"] == "sugars_g"]
    assert len(sugars) == 1, "a nutrient must appear once"
    merged = sugars[0]
    assert merged["proposed_value"] == min(
        rule_value for rule_value in (25, 30, 50) if rule_value >= (merged["proposed_value"] or 0)
    )
    rules = {item["detail"] for item in merged["evidence"] if item["kind"] == "condition"} | {
        item["parameter_key"] for item in merged["evidence"] if item["kind"] == "lab"
    }
    assert rules, "merged evidence must keep its sources"


def test_unrecognised_conditions_are_reported_not_forced():
    plan = build_plan(profile(conditions=["Ehlers-Danlos syndrome", "high BP"]), [])
    assert plan["unrecognised_conditions"] == ["Ehlers-Danlos syndrome"]
    assert [item["slug"] for item in plan["conditions"]] == ["hypertension"]


def test_alias_resolution_accepts_lay_phrasings():
    recognised, unrecognised = resolve_conditions(["sugar problem", "BP", "high uric acid"])
    assert unrecognised == []
    assert {"type_2_diabetes", "hypertension", "gout"} <= set(recognised)


def test_registry_is_consistent_and_codes_are_registry_derived():
    payload = registry_payload()
    assert len(payload["conditions"]) >= 30
    slugs = [item["slug"] for item in payload["conditions"]]
    assert len(slugs) == len(set(slugs)), "slugs must be unique"
    for item in payload["conditions"]:
        assert item["awareness"].strip()
        assert item["sources"], item["slug"]
        assert item["category"]
    assert "condition_pack_unsupported" in awareness_codes()
    assert len(awareness_codes()) >= 3


def test_plan_api_requires_auth_and_never_writes_the_profile(client, db_engine):
    from app.models import HealthReport
    from tests.conftest import signup

    anonymous = client.post("/api/intake/plan", json={"profile_id": "x", "profile_version": 1})
    assert anonymous.status_code == 401

    headers = signup(client)
    profile_row = client.put(
        "/api/profiles/me", headers=headers, json={"data": {"sex": "female"}}
    ).json()
    owner_id = client.get("/api/auth/me", headers=headers).json()["id"]

    with db_engine.begin() as connection:
        connection.execute(
            HealthReport.__table__.insert(),
            [
                {
                    "id": "report-1",
                    "owner_id": owner_id,
                    "status": "confirmed",
                    "collected_on": REPORT_DATE,
                    "parameters": [parameter("hba1c_percent", 7.4, unit="%", low=4.0, high=5.6)],
                    "warnings": [],
                    "source": {},
                    "provider": {},
                    "note": "",
                }
            ],
        )

    response = client.post(
        "/api/intake/plan",
        headers=headers,
        json={"profile_id": profile_row["id"], "profile_version": profile_row["version"]},
    )
    assert response.status_code == 200, response.text
    plan = response.json()
    assert any(item["nutrient"] == "sugars_g" for item in plan["targets"])
    after = client.get("/api/profiles/me", headers=headers).json()
    assert after["version"] == profile_row["version"], "the plan must not write the profile"

    stale = client.post(
        "/api/intake/plan",
        headers=headers,
        json={"profile_id": profile_row["id"], "profile_version": profile_row["version"] + 5},
    )
    assert stale.status_code == 409
    assert stale.json()["code"] == "profile_version_stale"


def test_conditions_endpoint_serves_the_registry(client):
    from tests.conftest import signup

    assert client.get("/api/conditions").status_code == 401
    headers = signup(client)
    body = client.get("/api/conditions", headers=headers).json()
    assert len(body["conditions"]) >= 30
    assert body["categories"]
    assert any(item["slug"] == "hypertension" for item in body["conditions"])


@pytest.mark.parametrize("threshold_value,expected", [(129, False), (130, True)])
def test_boundary_values_follow_the_rule_comparator(threshold_value, expected):
    plan = build_plan(
        profile(), [report("r1", [parameter("systolic_bp_mmhg", threshold_value, unit="mmHg")])]
    )
    assert (target_for(plan, "sodium_mg") is not None) is expected


# --- Human-scale values -------------------------------------------------------------------


def test_sodium_target_states_grams_of_salt():
    plan = build_plan(profile(), [report("r1", [parameter("systolic_bp_mmhg", 138, unit="mmHg")])])
    sodium = target_for(plan, "sodium_mg")
    salt = next(row for row in sodium["equivalents"] if row["unit"] == "g")
    assert salt["label"] == "grams of salt"
    assert salt["value"] == pytest.approx(3.75), "salt = sodium x 2.5, in grams"
    assert sodium["display_value"] == "1500 mg sodium \u2248 3.8 g salt"
    assert "\u22483.8 g salt" in sodium["derivation"]


def test_sugar_target_states_teaspoons():
    plan = build_plan(
        profile(),
        [report("r1", [parameter("hba1c_percent", 7.4, unit="%", low=4.0, high=5.6)])],
    )
    sugars = target_for(plan, "sugars_g")
    teaspoons = sugars["equivalents"][0]
    assert teaspoons == {"label": "teaspoons of sugar", "value": 6.25, "unit": "tsp"}
    assert sugars["display_value"] == "25 g sugars \u2248 6 teaspoons"


def test_saturated_fat_target_states_percent_of_a_2000_kcal_day():
    plan = build_plan(
        profile(),
        [report("r1", [parameter("ldl_cholesterol_mg_dl", 151, unit="mg/dL", high=100)])],
    )
    saturated = target_for(plan, "saturated_fat_g")
    assert saturated["proposed_value"] == 15
    percent = saturated["equivalents"][0]
    assert percent["unit"] == "%"
    assert percent["value"] == pytest.approx(6.75), "15 g x 9 kcal / 2000 kcal"
    assert "6.8 % of a 2000 kcal day" in saturated["display_value"]


def test_fibre_and_protein_equivalents_are_grams():
    plan = build_plan(
        profile(),
        [report("r1", [parameter("ldl_cholesterol_mg_dl", 151, unit="mg/dL", high=100)])],
    )
    fibre = target_for(plan, "fiber_g")
    assert fibre["equivalents"] == [
        {"label": "grams of fibre", "value": float(fibre["proposed_value"]), "unit": "g"}
    ]
    assert fibre["display_value"] == "30 g fibre"


def test_equivalents_helper_converts_baseline_references_too():
    from app.services.intake import equivalents_for

    assert equivalents_for("sodium_mg", 2000)[0]["value"] == pytest.approx(5.0), "WHO 5 g salt"
    assert equivalents_for("sugars_g", 50)[0]["value"] == pytest.approx(12.5), "50 g free sugar"
    assert equivalents_for("saturated_fat_g", 20)[0]["value"] == pytest.approx(9.0)
    assert equivalents_for("sodium_mg", None) == []


NUMERIC_SCENARIOS = [
    ({}, [report("r1", [parameter("hba1c_percent", 7.4, unit="%", low=4.0, high=5.6)])]),
    ({}, [report("r1", [parameter("systolic_bp_mmhg", 138, unit="mmHg")])]),
    ({}, [report("r1", [parameter("ldl_cholesterol_mg_dl", 151, unit="mg/dL", high=100)])]),
    ({"conditions": ["gout"]}, [report("r1", [parameter("uric_acid_mg_dl", 7.4, unit="mg/dL")])]),
    ({"conditions": ["ckd"]}, [report("r1", [parameter("egfr_ml_min", 45, unit="mL/min")])]),
    ({"conditions": ["hypertension"]}, []),
]


@pytest.mark.parametrize("changes,reports", NUMERIC_SCENARIOS)
def test_every_numeric_target_has_display_value_and_derivation(changes, reports):
    plan = build_plan(profile(**changes), reports)
    numeric = [item for item in plan["targets"] if item["proposed_value"] is not None]
    assert numeric, "these scenarios must produce a number"
    for target in numeric:
        assert target["display_value"], target["nutrient"]
        assert str(target["proposed_value"]) in target["display_value"]
        assert target["equivalents"], target["nutrient"]
        assert target["derivation"] and "\u2192" in target["derivation"], target["nutrient"]


def test_non_numeric_targets_explain_why_no_number_is_proposed():
    plan = build_plan(profile(conditions=["vitamin_d_deficiency"]), [])
    vitamin_d = target_for(plan, "vitamin_d")
    assert vitamin_d["proposed_value"] is None
    assert vitamin_d["display_value"] is None
    assert vitamin_d["equivalents"] == []
    assert vitamin_d["derivation"].endswith("no daily vitamin d number is proposed here")


def test_clinician_only_targets_carry_measured_values_and_a_clinician_derivation():
    plan = build_plan(profile(), [report("r1", [parameter("egfr_ml_min", 45, unit="mL/min")])])
    potassium = target_for(plan, "potassium_mg")
    assert potassium["confidence"] == "clinician_only"
    assert potassium["proposed_value"] is None
    assert potassium["display_value"] is None, "no converted number may leak into an ask"
    assert potassium["equivalents"] == []
    assert [item["parameter_key"] for item in potassium["measured"]] == ["egfr_ml_min"]
    assert "must be set by your clinician" in potassium["derivation"]


def test_high_potassium_target_keeps_measured_values_and_no_number():
    plan = build_plan(
        profile(),
        [
            report(
                "r1",
                [parameter("potassium_meq_l", 5.6, unit="mEq/L", low=3.5, high=5.1)],
            )
        ],
    )
    potassium = target_for(plan, "potassium_mg")
    assert potassium["confidence"] == "clinician_only"
    assert potassium["proposed_value"] is None and potassium["display_value"] is None
    row = potassium["measured"][0]
    assert (row["parameter_key"], row["value"], row["unit"]) == ("potassium_meq_l", 5.6, "mEq/L")
    assert (row["reference_low"], row["reference_high"]) == (3.5, 5.1)
    assert "clinician" in potassium["derivation"]


def test_measured_values_carry_unit_reference_range_and_report_date():
    plan = build_plan(
        profile(),
        [report("r1", [parameter("hba1c_percent", 7.4, unit="%", low=4.0, high=5.6)])],
    )
    measured = target_for(plan, "sugars_g")["measured"]
    assert len(measured) == 1
    row = measured[0]
    assert row["kind"] == "lab"
    assert (row["value"], row["unit"]) == (7.4, "%")
    assert (row["reference_low"], row["reference_high"]) == (4.0, 5.6)
    assert row["measured_on"] == REPORT_DATE
    assert row["report_id"] == "r1"


def test_condition_only_target_names_the_condition_and_shows_no_measurement():
    plan = build_plan(profile(conditions=["hypertension"]), [])
    sodium = target_for(plan, "sodium_mg")
    assert sodium["measured"] == []
    assert sodium["display_value"] == "1500 mg sodium \u2248 3.8 g salt"
    assert sodium["derivation"] == (
        "Recorded condition Hypertension \u2192 sodium ceiling 1500 mg/day (\u22483.8 g salt)"
    )


def test_plan_keeps_its_existing_keys_and_the_avoid_list():
    plan = build_plan(profile(), [])
    assert {
        "version",
        "targets",
        "conditions",
        "unrecognised_conditions",
        "reports_used",
        "notes",
        "coverage",
    } <= set(plan)
    assert plan["avoid"] == []
    plan = build_plan(profile(conditions=["hypertension"]), [])
    assert {
        "nutrient",
        "label",
        "unit",
        "baseline_value",
        "baseline_source",
        "proposed_value",
        "direction",
        "rule_id",
        "basis",
        "confidence",
        "requires_clinician",
        "evidence",
        "questions",
        "limit_scope",
        "suggested_limit_source",
    } <= set(plan["targets"][0])


# --- Avoid groups ---------------------------------------------------------------------------


def avoid_ids(plan):
    return {group["id"] for group in plan["avoid"]}


def test_no_avoid_group_without_a_matching_lab_or_condition():
    assert build_plan(profile(), [])["avoid"] == []
    unrelated = build_plan(
        profile(conditions=["ibs"]),
        [report("r1", [parameter("sodium_meq_l", 140, unit="mEq/L", low=135, high=145)])],
    )
    assert unrelated["avoid"] == [], "a normal value and an unrelated condition fire nothing"


def test_unconfirmed_report_fires_no_avoid_group():
    plan = build_plan(
        profile(),
        [
            report(
                "r1",
                [parameter("hba1c_percent", 7.4, unit="%", low=4.0, high=5.6)],
                status="extracted",
            )
        ],
    )
    assert plan["avoid"] == []


def test_avoid_group_can_fire_from_a_lab_that_sets_no_target():
    plan = build_plan(
        profile(),
        [report("r1", [parameter("fasting_glucose_mg_dl", 130, unit="mg/dL", low=70, high=99)])],
    )
    assert avoid_ids(plan) == {"avoid_glycaemia_sugars_v1"}
    assert target_for(plan, "sugars_g") is None, "no rule proposes a sugar number from glucose"


AVOID_BOUNDARIES = [
    ("systolic_bp_mmhg", 129, "mmHg", None, None, "limit_sodium_high_bp_v1", False),
    ("systolic_bp_mmhg", 130, "mmHg", None, None, "limit_sodium_high_bp_v1", True),
    ("diastolic_bp_mmhg", 79, "mmHg", None, None, "limit_sodium_high_bp_v1", False),
    ("diastolic_bp_mmhg", 80, "mmHg", None, None, "limit_sodium_high_bp_v1", True),
    ("hba1c_percent", 6.4, "%", 4.0, 5.6, "avoid_glycaemia_sugars_v1", False),
    ("hba1c_percent", 6.5, "%", 4.0, 5.6, "avoid_glycaemia_sugars_v1", True),
    ("fasting_glucose_mg_dl", 125, "mg/dL", 70, 99, "avoid_glycaemia_sugars_v1", False),
    ("fasting_glucose_mg_dl", 126, "mg/dL", 70, 99, "avoid_glycaemia_sugars_v1", True),
    ("ldl_cholesterol_mg_dl", 129, "mg/dL", None, 100, "avoid_trans_fat_v1", False),
    ("ldl_cholesterol_mg_dl", 130, "mg/dL", None, 100, "avoid_trans_fat_v1", True),
    ("triglycerides_mg_dl", 149, "mg/dL", None, 150, "limit_saturated_fat_foods_v1", False),
    ("triglycerides_mg_dl", 150, "mg/dL", None, 150, "limit_saturated_fat_foods_v1", True),
    ("egfr_ml_min", 60, "mL/min", 90, None, "ask_high_potassium_foods_v1", False),
    ("egfr_ml_min", 60, "mL/min", 90, None, "ask_phosphate_additives_v1", False),
    (
        "egfr_ml_min",
        59,
        "mL/min",
        90,
        None,
        "avoid_potassium_chloride_salt_substitute_v1",
        True,
    ),
    ("potassium_meq_l", 4.9, "mEq/L", 3.5, 5.1, "ask_high_potassium_foods_v1", False),
    ("potassium_meq_l", 5.0, "mEq/L", 3.5, 5.1, "ask_high_potassium_foods_v1", True),
    ("uric_acid_mg_dl", 6.9, "mg/dL", None, 6.0, "avoid_gout_alcohol_organ_meats_v1", False),
    ("uric_acid_mg_dl", 7.0, "mg/dL", None, 6.0, "avoid_gout_alcohol_organ_meats_v1", True),
    (
        "hemoglobin_g_dl",
        12.0,
        "g/dL",
        12.0,
        15.0,
        "limit_anaemia_absorption_blockers_v1",
        False,
    ),
    ("hemoglobin_g_dl", 11.9, "g/dL", 12.0, 15.0, "limit_anaemia_absorption_blockers_v1", True),
    ("vitamin_b12_pg_ml", 200, "pg/mL", 200, None, "ask_b12_fortified_foods_v1", False),
    ("vitamin_b12_pg_ml", 199, "pg/mL", 200, None, "ask_b12_fortified_foods_v1", True),
    ("vitamin_d_ng_ml", 20, "ng/mL", 30, None, "ask_vitamin_d_supplement_v1", False),
    ("vitamin_d_ng_ml", 19, "ng/mL", 30, None, "ask_vitamin_d_supplement_v1", True),
    ("tsh_miu_l", 4.5, "mIU/L", None, 4.5, "ask_hypothyroidism_iodine_v1", False),
    ("tsh_miu_l", 4.6, "mIU/L", None, 4.5, "ask_hypothyroidism_iodine_v1", True),
    ("phosphorus_mg_dl", 4.4, "mg/dL", None, 4.5, "ask_phosphate_additives_v1", False),
    ("phosphorus_mg_dl", 4.5, "mg/dL", None, 4.5, "ask_phosphate_additives_v1", True),
]


@pytest.mark.parametrize("key,value,unit,low,high,group_id,expected", AVOID_BOUNDARIES)
def test_avoid_groups_fire_only_on_their_own_trigger(
    key, value, unit, low, high, group_id, expected
):
    plan = build_plan(
        profile(), [report("r1", [parameter(key, value, unit=unit, low=low, high=high)])]
    )
    assert (group_id in avoid_ids(plan)) is expected, (key, value, group_id)


def test_avoid_evidence_points_at_the_lab_value_that_fired():
    plan = build_plan(
        profile(),
        [report("r1", [parameter("hba1c_percent", 7.4, unit="%", low=4.0, high=5.6)])],
    )
    group = next(item for item in plan["avoid"] if item["id"] == "avoid_glycaemia_sugars_v1")
    lab = next(item for item in group["evidence"] if item["kind"] == "lab")
    assert lab["parameter_key"] == "hba1c_percent"
    assert lab["value"] == 7.4
    assert lab["measured_on"] == REPORT_DATE
    assert lab["report_id"] == "r1"


def test_avoid_evidence_points_at_the_condition_that_fired():
    plan = build_plan(profile(conditions=["ckd"]), [])
    group = next(item for item in plan["avoid"] if item["id"] == "ask_phosphate_additives_v1")
    assert [item["label"] for item in group["evidence"]] == ["Chronic kidney disease"]
    assert all(item["kind"] == "condition" for item in group["evidence"])


def test_ckd_warns_about_potassium_chloride_salt_substitutes():
    plan = build_plan(profile(conditions=["ckd"]), [])
    group = next(
        item
        for item in plan["avoid"]
        if item["id"] == "avoid_potassium_chloride_salt_substitute_v1"
    )
    assert group["severity"] == "avoid"
    assert "potassium chloride" in group["items"][0]["label"].lower()
    assert any(item["kind"] == "condition" for item in group["evidence"])


def test_gout_avoid_and_limit_groups_split_by_severity():
    plan = build_plan(profile(conditions=["gout"]), [])
    severity = {group["id"]: group["severity"] for group in plan["avoid"]}
    assert severity["avoid_gout_alcohol_organ_meats_v1"] == "avoid"
    assert severity["limit_gout_purines_fructose_v1"] == "limit"


def test_b12_low_asks_rather_than_listing_a_food_to_avoid():
    plan = build_plan(
        profile(),
        [report("r1", [parameter("vitamin_b12_pg_ml", 150, unit="pg/mL", low=200)])],
    )
    group = next(item for item in plan["avoid"] if item["id"] == "ask_b12_fortified_foods_v1")
    assert group["severity"] == "ask"
    assert target_for(plan, "vitamin_b12")["proposed_value"] is None


def test_hypothyroidism_group_does_not_claim_goitrogen_avoidance():
    plan = build_plan(profile(conditions=["hypothyroidism"]), [])
    group = next(item for item in plan["avoid"] if item["id"] == "ask_hypothyroidism_iodine_v1")
    assert group["severity"] == "ask"
    assert "does not claim that avoiding" in group["detail"]


def test_avoid_table_is_well_formed():
    from app.services.intake import AVOID_RULES, NUTRIENT_META

    ids = [rule["id"] for rule in AVOID_RULES]
    assert len(ids) == len(set(ids)), "avoid rule ids must be unique"
    assert len(ids) >= 10
    for rule in AVOID_RULES:
        assert rule["severity"] in {"avoid", "limit", "ask"}
        assert rule["confidence"] in {"established", "general_wellbeing", "clinician_only"}
        assert rule["title"].strip() and rule["detail"].strip()
        assert rule["conditions"] or rule["labs"], rule["id"]
        assert rule["sources"] and all(url.startswith("https://") for url in rule["sources"])
        assert rule["items"]
        for trigger in rule["labs"]:
            assert trigger["op"] in {">=", ">", "<=", "<", "below_ref"}
        for item in rule["items"]:
            assert item["label"].strip() and item["reason"].strip(), rule["id"]
            assert item["examples"], rule["id"]
            assert set(item["linked_nutrients"]) <= set(NUTRIENT_META), rule["id"]


def test_every_avoid_rule_is_reachable_from_its_own_trigger():
    from app.services.intake import AVOID_RULES

    plan = build_plan(
        profile(
            conditions=[
                "type_2_diabetes",
                "hypertension",
                "dyslipidaemia",
                "ckd",
                "gout",
                "iron_deficiency_anaemia",
                "vitamin_b12_deficiency",
                "vitamin_d_deficiency",
                "hypothyroidism",
            ]
        ),
        [
            report(
                "r1",
                [
                    parameter("hba1c_percent", 7.4, unit="%", low=4.0, high=5.6),
                    parameter("systolic_bp_mmhg", 150, unit="mmHg"),
                    parameter("egfr_ml_min", 40, unit="mL/min", low=90),
                    parameter("uric_acid_mg_dl", 8.0, unit="mg/dL", high=6.0),
                    parameter("hemoglobin_g_dl", 10.0, unit="g/dL", low=12.0, high=15.0),
                    parameter("vitamin_b12_pg_ml", 150, unit="pg/mL", low=200),
                    parameter("vitamin_d_ng_ml", 15, unit="ng/mL", low=30),
                    parameter("tsh_miu_l", 6.0, unit="mIU/L", high=4.5),
                ],
            )
        ],
    )
    assert avoid_ids(plan) == {rule["id"] for rule in AVOID_RULES}


def test_every_fired_avoid_group_carries_evidence_items_and_sources():
    plan = build_plan(
        profile(
            conditions=["type_2_diabetes", "hypertension", "ckd", "gout", "iron_deficiency_anaemia"]
        ),
        [
            report(
                "r1",
                [
                    parameter("hba1c_percent", 7.4, unit="%", low=4.0, high=5.6),
                    parameter("systolic_bp_mmhg", 150, unit="mmHg"),
                    parameter("egfr_ml_min", 40, unit="mL/min", low=90),
                    parameter("uric_acid_mg_dl", 8.0, unit="mg/dL", high=6.0),
                    parameter("hemoglobin_g_dl", 10.0, unit="g/dL", low=12.0, high=15.0),
                ],
            )
        ],
    )
    assert plan["avoid"]
    for group in plan["avoid"]:
        assert group["severity"] in {"avoid", "limit", "ask"}
        assert group["detail"].strip()
        assert group["sources"] and all(url.startswith("https://") for url in group["sources"])
        assert group["evidence"], group["id"]
        assert all(item["kind"] in {"lab", "condition"} for item in group["evidence"])
        assert group["items"], group["id"]
        for item in group["items"]:
            assert item["label"].strip() and item["reason"].strip() and item["examples"]
    assert any("not a statement that it is safe" in note for note in plan["notes"]), (
        "the plan must say a food that is not listed is not declared safe"
    )
