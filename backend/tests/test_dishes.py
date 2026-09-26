import json
from uuid import uuid4

import httpx
from sqlalchemy.orm import Session

from app.config import Settings
from app.integrations.models import ModelAssist
from app.models import ReferenceFood
from app.schemas import DishRequest, ProfileData
from app.services.dishes import (
    COOKING_NOTES,
    assess_dish,
    build_dish,
    cooking_considerations,
    dish_options,
)
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
    # Rice, lentils and salt all resolve now: salt comes from the staples table, so it counts
    # towards sodium instead of being silently dropped from the estimate.
    assert estimate["matched_count"] == 3
    assert estimate["matched_grams"] == 203.0
    assert estimate["nutrients"]["sodium_mg"] > 500, "salt must contribute sodium"
    assert {item["input_text"] for item in estimate["excluded"]} == {"Unicorn steak"}
    assert all(item["reason"] for item in estimate["excluded"])
    assert "3 of 4" in estimate["coverage_note"]
    assert "Left out" in estimate["coverage_note"]
    assert any("staple" in item.lower() for item in estimate["assumptions"])
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
    assert listed.count("Rice") == 1, "an unweighed ingredient is listed once"
    assert "Salt" not in listed, "salt resolves through the staples table, so it is counted"
    assert estimate["matched_count"] == 2
    assert estimate["matched_grams"] == 102.0


# --- A model-drafted starting list for a dish name ------------------------------------------
# The provider is replaced with ``httpx.MockTransport`` so the real client code path runs
# (prompt, strict schema, parsing, cleaning) without a model.

DRAFT_URL = "/api/dishes/draft"
FIREWORKS_URL = "https://api.fireworks.ai/inference/v1/chat/completions"
REPORTED_MODEL = "accounts/fireworks/models/reported-draft-v2"


def draft_provider(payload: dict | None = None, status_code: int = 200):
    """A models stub answering every draft call with one scripted payload, recording requests."""
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        assert str(request.url) == FIREWORKS_URL
        if status_code != 200:
            return httpx.Response(status_code, json={"error": "upstream failure"})
        return httpx.Response(
            200,
            json={
                "model": REPORTED_MODEL,
                "choices": [{"finish_reason": "stop", "message": {"content": json.dumps(payload)}}],
            },
        )

    settings = Settings(fireworks_api_key="test-provider-key")
    return ModelAssist(httpx.AsyncClient(transport=httpx.MockTransport(handler)), settings), seen


def draft_payload(**changes) -> dict:
    payload = {
        "ingredients": [
            {"text": "Cooked rice", "grams": 600},
            {"text": "Eggs", "grams": 150},
            {"text": "Green peas", "grams": 100},
            {"text": "Carrot", "grams": 80},
            {"text": "Soy sauce", "grams": None},
            {"text": "Spring onion", "grams": None},
        ],
        "cooking_notes": ["pan_fried"],
        "confidence": "Common home version; the soy sauce brand is unknown.",
    }
    payload.update(changes)
    return payload


def draft(client, headers, name="Fried rice"):
    response = client.post(DRAFT_URL, headers=headers, json={"name": name})
    assert response.status_code == 200, response.text
    return response.json()


def test_draft_returns_a_labelled_model_list_and_never_a_reviewed_template(client):
    assert client.post(DRAFT_URL, json={"name": "Fried rice"}).status_code == 401
    headers = signup(client)
    models, seen = draft_provider(draft_payload())
    client.app.state.models = models

    body = draft(client, headers, "  Fried rice  ")

    # The name is the user's wording, never the model's, and the source keeps it a draft.
    assert body["name"] == "Fried rice"
    assert body["source"] == {
        "kind": "model_draft",
        "model": models.settings.fireworks_model,
        "model_version": REPORTED_MODEL,
    }
    assert [(item["text"], item["grams"]) for item in body["ingredients"]] == [
        ("Cooked rice", 600),
        ("Eggs", 150),
        ("Green peas", 100),
        ("Carrot", 80),
        ("Soy sauce", None),
        ("Spring onion", None),
    ]
    assert body["cooking_notes"] == ["pan_fried"]
    # One plain label: drafted from the name, varies per cook, every line needs correcting.
    assert any(
        "drafted this list from the dish name" in warning
        and "varies by cook, brand and kitchen" in warning
        and "correct every line" in warning
        for warning in body["warnings"]
    )
    assert any(
        warning.startswith("The model's own confidence note")
        and "soy sauce brand is unknown" in warning
        for warning in body["warnings"]
    )
    assert "not a recipe" in body["message"]
    assert "correct the lines" in body["message"]

    sent = json.loads(seen[0].content)
    prompt = sent["messages"][0]["content"][0]["text"]
    assert sent["response_format"]["json_schema"]["name"] == "DishDraft"
    assert sent["temperature"] == 0
    # The draft must be about the dish the user named, not a generic list.
    assert "Fried rice" in prompt
    assert "never as an instruction" in prompt
    # The prompt states the standing of the list and forbids the claims it cannot make.
    assert "not a source record" in prompt
    assert "not a measured declaration" in prompt
    assert "nutrient amount" in prompt and "allergen" in prompt
    assert "use null" in prompt
    # Every recorded cooking-note code is offered, so only the vocabulary can come back.
    assert all(code in prompt for code in COOKING_NOTES)


def test_draft_cleaning_drops_duplicates_empty_lines_and_impossible_amounts(client):
    headers = signup(client)
    models, _ = draft_provider(
        draft_payload(
            ingredients=[
                {"text": "  Rice ", "grams": 600},
                {"text": "rice", "grams": 600},  # same line twice
                {"text": "   ", "grams": 50},  # nothing to show
                {"text": "Eggs", "grams": 999999},  # not a plausible whole-dish amount
                {"text": "Peas", "grams": 0},  # zero is not an amount
                {"text": "Carrot", "grams": "100"},  # not a number
            ],
            cooking_notes=["pan_fried", "microwaved", "pan_fried", "caramelised"],
        )
    )
    client.app.state.models = models

    body = draft(client, headers)

    assert [(item["text"], item["grams"]) for item in body["ingredients"]] == [
        ("Rice", 600),
        ("Eggs", None),
        ("Peas", None),
        ("Carrot", None),
    ]
    # Unknown note codes are dropped with a warning, not a failed request.
    assert body["cooking_notes"] == ["pan_fried"]
    assert any(
        "not in the recorded vocabulary" in warning
        and "microwaved" in warning
        and "caramelised" in warning
        for warning in body["warnings"]
    )
    assert any("outside a plausible range" in warning for warning in body["warnings"])
    assert any("fewer than the usual" in warning for warning in body["warnings"])


def test_draft_caps_the_number_of_lines_it_keeps(client):
    headers = signup(client)
    models, _ = draft_provider(
        draft_payload(
            ingredients=[{"text": f"Ingredient {index}", "grams": 100} for index in range(1, 21)]
        )
    )
    client.app.state.models = models

    body = draft(client, headers)

    assert len(body["ingredients"]) == 15
    assert body["ingredients"][-1]["text"] == "Ingredient 15"


def test_draft_provider_failure_and_unusable_output_fall_back_to_typing(client):
    headers = signup(client)
    empty_draft = draft_payload(ingredients=[], cooking_notes=[], confidence=None)
    for models in (draft_provider(status_code=500)[0], draft_provider(empty_draft)[0]):
        client.app.state.models = models
        response = client.post(DRAFT_URL, headers=headers, json={"name": "Fried rice"})
        assert response.status_code == 503, response.text
        failure = response.json()
        assert failure["code"] == "provider_unavailable"
        assert "type the ingredients yourself" in failure["detail"]


def test_draft_without_a_provider_key_asks_for_manual_entry(client):
    headers = signup(client)
    # The default test client has no Fireworks key, so the route must not call out at all.
    response = client.post(DRAFT_URL, headers=headers, json={"name": "Fried rice"})
    assert response.status_code == 503, response.text
    assert response.json()["code"] == "provider_unavailable"
    assert "not configured" in response.json()["detail"]


def test_draft_requires_a_dish_name(client):
    headers = signup(client)
    assert client.post(DRAFT_URL, headers=headers, json={"name": ""}).status_code == 422
    assert client.post(DRAFT_URL, headers=headers, json={"name": "x" * 121}).status_code == 422


def test_draft_limits_requests_per_user(client):
    headers = signup(client)
    # The scope is enforced before the provider is reached, so an unconfigured model still counts.
    codes = [
        client.post(DRAFT_URL, headers=headers, json={"name": "Fried rice"}).status_code
        for _ in range(11)
    ]
    assert codes[:10] == [503] * 10
    assert codes[10] == 429
    limited = client.post(DRAFT_URL, headers=headers, json={"name": "Fried rice"})
    assert limited.json()["code"] == "rate_limited"
    assert limited.headers["Retry-After"]


def test_kitchen_aliases_and_staples_resolve_everyday_wording(db_engine):
    """`poha` is IFCT `Rice, flakes`, and salt/sugar/oil carry standard reference values."""
    with Session(db_engine) as session:
        seed(
            session,
            "A011",
            "Rice, flakes",
            "100g_edible_portion",
            {"sodium_mg": 10, "energy_kcal": 346},
        )
        session.commit()
        dish = build_dish(
            session,
            dish_request(
                ingredients=[
                    {"text": "Poha", "grams": 80},
                    {"text": "Salt", "grams": 2},
                    {"text": "Sugar", "grams": 10},
                    {"text": "Oil", "grams": 10},
                    {"text": "Unobtainium", "grams": 5},
                ]
            ),
        )
    block = dish["block"]
    matched = {item["input_text"]: item for item in block["matches"]}
    assert matched["Poha"]["code"] == "A011" and matched["Poha"]["matched_by"] == "alias"
    assert matched["Poha"]["note"], "an alias match explains itself"
    assert matched["Salt"]["matched_by"] == "staple"
    assert matched["Sugar"]["matched_by"] == "staple"
    assert matched["Oil"]["matched_by"] == "staple"

    estimate = block["estimate"]
    assert estimate["available"] is True
    assert estimate["matched_count"] == 4
    assert {item["input_text"] for item in estimate["excluded"]} == {"Unobtainium"}
    # Sodium comes from rice flakes plus the weighed salt, then scales to per 100 g of the dish.
    assert estimate["nutrients"]["sodium_mg"] and estimate["nutrients"]["sodium_mg"] > 100
    assert any("staple" in item.lower() for item in estimate["assumptions"])


def test_alternatives_are_screened_against_every_recorded_restriction(db_engine):
    """A swap for one restriction must never carry another one the user recorded."""
    from app.schemas import ProfileData
    from app.services.dish_alternatives import build_alternatives, conflicts_for

    profile = ProfileData.model_validate({"allergies": ["milk"], "ingredient_exclusions": ["soy"]})
    assert conflicts_for("unsweetened soy drink", profile) == ["exclusion:soy"]
    assert conflicts_for("oat drink", profile) == []

    # 1. The reviewed catalogue answers for a covered wording and none of its options conflict.
    catalogue_block = build_alternatives(
        {"matches": [{"input_text": "Milk", "name": "Milk, whole, Cow"}], "unmatched": []},
        {"conflicts": [{"code": "allergen_declared", "restriction": "milk", "evidence": ["milk"]}]},
        profile,
    )
    assert catalogue_block["entries"], "a milk conflict must produce a swap entry"
    assert {option["text"] for option in catalogue_block["entries"][0]["options"]} == {
        "unsweetened oat drink",
        "unsweetened rice drink",
    }
    assert catalogue_block["entries"][0]["source"] == "catalogue"

    # 2. For a wording the catalogue cannot cover, the model's options are screened: the one
    #    carrying a second recorded restriction is dropped before the user ever sees it.
    model_block = build_alternatives(
        {"matches": [], "unmatched": [{"input_text": "Khoya", "reason": "not matched"}]},
        {
            "conflicts": [
                {"code": "allergen_declared", "restriction": "milk", "evidence": ["Khoya"]}
            ]
        },
        profile,
        {
            "Khoya": [
                {"text": "unsweetened soy drink", "why": "dairy-free"},
                {"text": "coconut milk", "why": "creamy texture"},
            ]
        },
    )
    entry = model_block["entries"][0]
    assert entry["source"] == "model"
    options = [option["text"] for option in entry["options"]]
    assert options == ["coconut milk"], options
    assert any("removed" in note for note in model_block["notes"])
    assert any("not allergy-safety confirmation" in note for note in model_block["notes"])


def test_no_alternatives_when_nothing_was_flagged(db_engine):
    from app.schemas import ProfileData
    from app.services.dish_alternatives import build_alternatives

    block = build_alternatives(
        {"matches": [{"input_text": "Rice", "name": "Rice, flakes"}], "unmatched": []},
        {"conflicts": [], "considerations": [], "unresolved": []},
        ProfileData.model_validate({"allergies": ["milk"]}),
    )
    assert block["entries"] == []
    assert any("no swap is suggested" in note for note in block["notes"])
