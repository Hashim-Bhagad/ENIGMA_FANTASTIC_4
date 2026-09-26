from uuid import uuid4

from sqlalchemy.orm import Session

from app.models import ReferenceFood
from app.schemas import DishRequest, ProfileData
from app.services.dishes import assess_dish, build_dish, cooking_considerations, dish_options
from tests.conftest import signup


def seed(session: Session, code: str, name: str, basis: str, nutrients: dict):
    session.add(
        ReferenceFood(
            code=code,
            name=name,
            data={"code": code, "name": name, "basis": basis, "nutrients": nutrients},
            source={"dataset": "IFCT fixture"},
        )
    )
    return name


def dish_request(**changes):
    payload = {
        "profile_id": uuid4(),
        "profile_version": 1,
        "name": "Rice and lentil bowl",
        "ingredients": [
            {"text": "Rice", "reference_code": "A001", "grams": 100},
            {"text": "Lentils", "grams": 100},
        ],
        "cooking_notes": [],
        "declarations_confirmed": True,
        "portion_g": 200,
    }
    payload.update(changes)
    return DishRequest.model_validate(payload)


def test_matched_and_weighed_ingredients_produce_a_per_100g_estimate(db_engine):
    with Session(db_engine) as session:
        seed(session, "A001", "Rice", "100g_edible_portion", {"sodium_mg": 5, "protein_g": 7})
        seed(session, "B001", "Lentils", "100g_edible_portion", {"sodium_mg": 10, "protein_g": 25})
        session.commit()
        dish = build_dish(session, dish_request())

    estimate = dish["block"]["estimate"]
    assert estimate["available"] is True
    assert estimate["basis"] == "100g"
    assert estimate["total_grams"] == 200
    # (5 + 10) / 200 * 100 = 7.5 mg sodium per 100 g; (7 + 25) / 200 * 100 = 16 g protein.
    assert estimate["nutrients"]["sodium_mg"] == 7.5
    assert estimate["nutrients"]["protein_g"] == 16
    # Reference composition has no energy/sugar value, so unknown keys stay unknown.
    assert estimate["nutrients"]["energy_kcal"] is None
    assert [match["matched_by"] for match in dish["block"]["matches"]] == [
        "reference_code",
        "name",
    ]
    assert dish["food"].basis == "100g"
    assert dish["food"].source.kind == "dish"
    assert dish["food"].source.reference.startswith("dish:")


def test_matched_and_weighed_dish_produces_a_portion_contribution(db_engine):
    with Session(db_engine) as session:
        seed(session, "A001", "Rice", "100g_edible_portion", {"sodium_mg": 100})
        seed(session, "B001", "Lentils", "100g_edible_portion", {"sodium_mg": 20})
        session.commit()
        profile = ProfileData(
            limits=[
                {"nutrient": "sodium_mg", "maximum": 1500, "scope": "daily", "source": "Clinician"}
            ]
        )
        _, result = assess_dish(session, profile, dish_request())

    # (100 + 20) / 200 * 100 = 60 mg per 100 g; a 200 g portion contributes 120 mg.
    contribution = next(
        item for item in result["considerations"] if item["code"] == "limit_daily_contribution"
    )
    assert contribution["portion_amount"] == 120
    assert contribution["daily_limit_percent"] == 8


def test_partial_estimate_covers_matched_ingredients_and_names_what_it_left_out(db_engine):
    """A reference table is not a recipe book: unmatched salt/sugar must not kill the estimate."""
    with Session(db_engine) as session:
        seed(session, "A001", "Rice", "100g_edible_portion", {"sodium_mg": 5})
        seed(session, "B001", "Lentils", "100g_edible_portion", {"sodium_mg": 10})
        session.commit()
        body = dish_request(
            ingredients=[
                {"text": "Rice", "reference_code": "A001", "grams": 100},
                {"text": "Lentils", "reference_code": "B001", "grams": 100},
                {"text": "Unicorn steak", "grams": 100},
                {"text": "Salt", "grams": 3},
            ]
        )
        dish = build_dish(session, body)
        profile = ProfileData(
            limits=[
                {"nutrient": "sodium_mg", "maximum": 1500, "scope": "daily", "source": "Clinician"}
            ]
        )
        _, result = assess_dish(session, profile, body)

    estimate = dish["block"]["estimate"]
    assert estimate["available"] is True
    assert estimate["basis"] == "100g"
    assert estimate["matched_count"] == 2
    assert estimate["matched_grams"] == 200
    # Sodium per 100 g of the two weighed references: (5*1 + 10*1) / 200 * 100 = 7.5 mg.
    assert estimate["nutrients"]["sodium_mg"] == 7.5
    assert {item["input_text"] for item in estimate["excluded"]} == {"Unicorn steak", "Salt"}
    assert all(item["reason"] for item in estimate["excluded"])
    assert "2 of 4" in estimate["coverage_note"]
    assert "Left out" in estimate["coverage_note"]
    assert any("floor" in warning for warning in dish["food"].source.warnings)
    assert any(item["code"] == "limit_daily_contribution" for item in result["considerations"])


def test_ingredient_without_grams_yields_no_estimate(db_engine):
    with Session(db_engine) as session:
        seed(session, "A001", "Rice", "100g_edible_portion", {"sodium_mg": 5})
        session.commit()
        dish = build_dish(
            session,
            dish_request(ingredients=[{"text": "Rice", "reference_code": "A001"}]),
        )
    assert dish["block"]["estimate"]["available"] is False
    assert dish["block"]["unmatched"] == []
    assert dish["food"].nutrients == {}


def test_name_matching_is_exact_and_never_fuzzy(db_engine):
    with Session(db_engine) as session:
        seed(session, "A001", "Rice, raw", "100g_edible_portion", {"sodium_mg": 5})
        session.commit()
        dish = build_dish(
            session,
            dish_request(ingredients=[{"text": "rice", "grams": 100}]),
        )
    assert dish["block"]["matches"] == []
    assert dish["block"]["unmatched"][0]["input_text"] == "rice"


def test_cooking_notes_produce_considerations_with_full_shape():
    findings = cooking_considerations(["deep_fried", "added_salt"])
    assert [item["code"] for item in findings] == ["cooking_deep_fried", "cooking_added_salt"]
    for item in findings:
        assert item["group"] == "consideration"
        assert item["title"] and item["detail"] and item["next_step"]
        assert item["affects"] == [f"cooking:{item['cooking_note']}"]


def test_dish_options_expose_the_vocabulary_and_copy():
    options = dish_options()
    codes = [item["code"] for item in options["cooking_notes"]]
    assert "deep_fried" in codes and "restaurant_prepared" in codes
    assert all(item["label"] for item in options["cooking_notes"])
    assert options["unknowns"] and options["assumptions"]


def test_dish_endpoints_require_auth_and_return_estimate(client, db_engine):
    assert client.get("/api/dishes/options").status_code == 401
    headers = signup(client)
    options = client.get("/api/dishes/options", headers=headers)
    assert options.status_code == 200, options.text
    assert {item["code"] for item in options.json()["cooking_notes"]} >= {"deep_fried"}

    profile = client.put(
        "/api/profiles/me",
        headers=headers,
        json={
            "data": {
                "allergies": ["milk"],
                "limits": [
                    {
                        "nutrient": "sodium_mg",
                        "maximum": 1500,
                        "scope": "daily",
                        "source": "Clinician",
                    }
                ],
            }
        },
    ).json()
    with Session(db_engine) as session:
        seed(session, "A001", "Rice", "100g_edible_portion", {"sodium_mg": 100})
        seed(session, "B001", "Lentils", "100g_edible_portion", {"sodium_mg": 20})
        session.commit()

    created = client.post(
        "/api/dishes/assess",
        headers=headers,
        json={
            "profile_id": profile["id"],
            "profile_version": profile["version"],
            "name": "Rice and lentil bowl",
            "ingredients": [
                {"text": "Rice", "reference_code": "A001", "grams": 100},
                {"text": "Lentils", "grams": 100},
            ],
            "cooking_notes": ["deep_fried"],
            "declarations_confirmed": True,
            "portion_g": 200,
        },
    )
    assert created.status_code == 201, created.text
    payload = created.json()
    assert payload["dish"]["estimate"]["available"] is True
    assert payload["dish"]["estimate"]["nutrients"]["sodium_mg"] == 60
    assert any(
        item["code"] == "cooking_deep_fried" for item in payload["assessment"]["considerations"]
    )
    assert payload["assessment"]["status"] == "no_matching_concern_found"
    # The dish block is persisted, so history/detail keep working.
    detail = client.get(f"/api/assessments/{payload['id']}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["result"]["dish"]["estimate"]["available"] is True

    bad_note = client.post(
        "/api/dishes/assess",
        headers=headers,
        json={
            "profile_id": profile["id"],
            "profile_version": profile["version"],
            "name": "Bowl",
            "ingredients": [{"text": "Rice", "reference_code": "A001", "grams": 100}],
            "cooking_notes": ["not_a_note"],
        },
    )
    assert bad_note.status_code == 422


def test_recommendations_are_not_offered_for_dishes(client, db_engine):
    headers = signup(client)
    profile = client.put("/api/profiles/me", headers=headers, json={"data": {}}).json()
    with Session(db_engine) as session:
        seed(session, "A001", "Rice", "100g_edible_portion", {"sodium_mg": 100})
        session.commit()
    created = client.post(
        "/api/dishes/assess",
        headers=headers,
        json={
            "profile_id": profile["id"],
            "profile_version": profile["version"],
            "name": "Plain rice",
            "ingredients": [{"text": "Rice", "reference_code": "A001", "grams": 200}],
            "declarations_confirmed": True,
        },
    )
    assert created.status_code == 201, created.text
    response = client.post(
        "/api/recommendations",
        headers=headers,
        json={"assessment_id": created.json()["id"]},
    )
    assert response.status_code == 422


def test_stale_profile_version_is_branchable(client):
    headers = signup(client)
    profile = client.put("/api/profiles/me", headers=headers, json={"data": {}}).json()
    client.put(
        "/api/profiles/me",
        headers=headers,
        json={
            "expected_version": profile["version"],
            # A byte-identical PUT is now an idempotent retry, so the profile must genuinely
            # change to advance its version and make the dish request stale.
            "data": {**profile["data"], "ingredient_exclusions": ["sugar alcohol"]},
        },
    )
    response = client.post(
        "/api/dishes/assess",
        headers=headers,
        json={
            "profile_id": profile["id"],
            "profile_version": profile["version"],
            "name": "Bowl",
            "ingredients": [{"text": "Rice"}],
        },
    )
    assert response.status_code == 409
    assert response.json()["code"] == "profile_version_stale"


def test_unconfirmed_dish_blockers_speak_about_the_meal_check_not_a_pack(client, db_engine):
    headers = signup(client)
    profile = client.put(
        "/api/profiles/me", headers=headers, json={"data": {"allergies": ["milk"]}}
    ).json()
    with Session(db_engine) as session:
        seed(session, "A001", "Rice", "100g_edible_portion", {"sodium_mg": 100})
        session.commit()
    created = client.post(
        "/api/dishes/assess",
        headers=headers,
        json={
            "profile_id": profile["id"],
            "profile_version": profile["version"],
            "name": "Unconfirmed rice bowl",
            "ingredients": [{"text": "Rice", "reference_code": "A001", "grams": 100}],
        },
    )
    assert created.status_code == 201, created.text
    findings = created.json()["assessment"]["unresolved"]
    by_code = {item["code"]: item for item in findings}
    assert by_code["ingredients_not_confirmed"]["next_step"].startswith("Tick the ingredient-list")
    advisory = by_code["advisories_not_confirmed"]
    assert advisory["title"] == "No packaged advisory panel"
    assert "Ask the cook" in advisory["next_step"]
    # Pack-photographing instructions must never be given for a cooked dish.
    assert not any(
        "photograph the ingredient panel" in (item.get("next_step") or "") for item in findings
    )


def test_exclusion_list_names_each_ingredient_once_and_never_a_weighed_one(db_engine):
    with Session(db_engine) as session:
        seed(session, "A001", "Rice", "100g_edible_portion", {"sodium_mg": 5})
        session.commit()
        dish = build_dish(
            session,
            dish_request(
                ingredients=[
                    {"text": "Rice", "reference_code": "A001", "grams": 100},
                    {"text": "Rice", "reference_code": "A001"},
                    {"text": "Salt", "grams": 2},
                ]
            ),
        )
    estimate = dish["block"]["estimate"]
    listed = [item["input_text"] for item in estimate["excluded"]]
    assert listed.count("Salt") == 1, "an unmatched ingredient is listed once"
    assert "Rice" in listed, "a matched but unweighed ingredient is left out and named"
    assert estimate["matched_count"] == 1
    assert estimate["matched_grams"] == 100
