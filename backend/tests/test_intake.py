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
