import io
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import jwt
from PIL import Image
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app import rate_limit as rate_limit_module
from app.catalog import store_product
from app.config import Settings, get_settings
from app.integrations.off import ProviderError
from app.models import Assessment, Product
from app.schemas import FoodObservation
from tests.conftest import signup

FOOD = {
    "name": "Test crackers",
    "brand": "Test brand",
    "category": "crackers",
    "basis": "100g",
    "ingredients_text": "Rice flour, salt",
    "advisories_text": "",
    "ingredients_complete": True,
    "advisories_complete": True,
    "nutrients": {"sodium_mg": 800},
    "source": {"kind": "demo", "reference": "Synthetic test"},
}


def save_profile(client, headers):
    response = client.put(
        "/api/profiles/me",
        headers=headers,
        json={
            "data": {
                "allergies": ["milk"],
                "goals": [{"nutrient": "sodium_mg", "direction": "lower"}],
            }
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def assessment(client, headers, profile):
    response = client.post(
        "/api/assessments",
        headers=headers,
        json={"profile_id": profile["id"], "profile_version": profile["version"], "food": FOOD},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_register_login_reload_and_stale_profile_write(client):
    headers = signup(client)
    saved = save_profile(client, headers)
    login = client.post(
        "/api/auth/login", json={"email": "FIRST@example.com", "password": "A-test-password-123"}
    )
    assert login.status_code == 200
    reloaded = client.get(
        "/api/profiles/me", headers={"Authorization": "Bearer " + login.json()["access_token"]}
    )
    assert reloaded.json() == saved
    changed = {**saved["data"], "preferences": "no nuts"}
    edit = client.put(
        "/api/profiles/me", headers=headers, json={"expected_version": 1, "data": changed}
    )
    assert edit.json()["version"] == 2
    # A retry with the same payload must not bump the version again or 409.
    retry = client.put(
        "/api/profiles/me", headers=headers, json={"expected_version": 1, "data": changed}
    )
    assert retry.status_code == 200
    assert retry.json()["version"] == 2
    assert retry.json() == edit.json()
    # A different payload at a stale version is still a conflict.
    stale = client.put(
        "/api/profiles/me", headers=headers, json={"expected_version": 1, "data": saved["data"]}
    )
    assert stale.status_code == 409
    assert stale.json()["code"] == "profile_version_stale"
    wrong = client.post("/api/auth/login", json={"email": "first@example.com", "password": "wrong"})
    assert wrong.status_code == 401


def test_owned_assessment_to_replacements_and_history(client, db_engine):
    headers = signup(client)
    profile = save_profile(client, headers)
    result = assessment(client, headers, profile)
    with Session(db_engine) as session:
        food = FoodObservation.model_validate(
            {**FOOD, "name": "Better crackers", "nutrients": {"sodium_mg": 200}}
        )
        store_product(session, food, "better", {"brands": "Test brand"})
        session.commit()
    response = client.post(
        "/api/recommendations",
        headers=headers,
        json={"assessment_id": result["id"], "preferences": "Mild"},
    )
    assert response.status_code == 201, response.text
    assert len(response.json()["candidates"]) == 1
    assert response.json()["candidates"][0]["comparisons"][0]["difference"] == -600
    assert (
        client.get("/api/assessments", headers=headers).json()["assessments"][0]["id"]
        == result["id"]
    )
    other = signup(client, "other@example.com")
    assert client.get("/api/assessments/" + result["id"], headers=other).status_code == 404
    assert (
        client.post(
            "/api/recommendations", headers=other, json={"assessment_id": result["id"]}
        ).status_code
        == 404
    )
    assert (
        client.get("/api/recommendations/" + response.json()["id"], headers=other).status_code
        == 404
    )
    assert client.get("/api/assessments", headers=other).json()["assessments"] == []


def test_profile_change_requires_reassessment(client):
    headers = signup(client)
    profile = save_profile(client, headers)
    result = assessment(client, headers, profile)
    client.put(
        "/api/profiles/me",
        headers=headers,
        json={
            "expected_version": 1,
            "data": {**profile["data"], "allergies": ["milk", "soy"]},
        },
    )
    assert (
        client.post(
            "/api/recommendations", headers=headers, json={"assessment_id": result["id"]}
        ).status_code
        == 409
    )
    assert (
        client.get("/api/assessments/" + result["id"], headers=headers).json()["profile_version"]
        == 1
    )


def test_expired_and_invalid_tokens(client):
    headers = signup(client)
    user = client.get("/api/auth/me", headers=headers).json()
    expired = jwt.encode(
        {
            "sub": user["id"],
            "iat": datetime.now(UTC) - timedelta(hours=2),
            "exp": datetime.now(UTC) - timedelta(hours=1),
            "aud": "dietary-risk-client",
            "iss": "dietary-risk-api",
        },
        get_settings().jwt_secret.get_secret_value(),
        algorithm="HS256",
    )
    assert (
        client.get("/api/auth/me", headers={"Authorization": "Bearer " + expired}).status_code
        == 401
    )
    assert (
        client.get("/api/auth/me", headers={"Authorization": "Bearer invalid"}).status_code == 401
    )


def test_unified_search_routes_scanned_barcode_and_product_name(client, db_engine):
    headers = signup(client)
    with Session(db_engine) as session:
        food = FoodObservation.model_validate({**FOOD, "barcode": "8904004400052"})
        store_product(session, food, "barcode-fixture", {"brands": "Haldiram"})
        session.commit()
    barcode = client.get("/api/products/search", params={"q": "8904004400052"}, headers=headers)
    assert barcode.status_code == 200, barcode.text
    assert barcode.headers["Cache-Control"] == "no-store"
    assert barcode.json()["query_type"] == "barcode"
    assert barcode.json()["lookup_source"] == "saved_snapshot"
    brand = client.get("/api/products/search", params={"q": "haldiram"}, headers=headers)
    assert len(brand.json()["products"]) == 1
    assert (
        client.get("/api/products/search", params={"q": "  "}, headers=headers).status_code == 422
    )


def test_saved_products_support_offset_and_report_total(client, db_engine):
    headers = signup(client)
    with Session(db_engine) as session:
        for index in range(3):
            store_product(
                session,
                FoodObservation.model_validate({**FOOD, "name": f"Paged cracker {index}"}),
                f"paged-{index}",
                {},
            )
        session.commit()
    first = client.get("/api/products", params={"q": "Paged", "limit": 2}, headers=headers)
    assert first.status_code == 200, first.text
    assert first.json()["total"] == 3
    assert first.json()["offset"] == 0 and first.json()["limit"] == 2
    assert [x["food"]["name"] for x in first.json()["products"]] == [
        "Paged cracker 0",
        "Paged cracker 1",
    ]
    second = client.get(
        "/api/products", params={"q": "Paged", "limit": 2, "offset": 2}, headers=headers
    )
    assert [x["food"]["name"] for x in second.json()["products"]] == ["Paged cracker 2"]


def test_live_search_failure_retains_saved_results(client, db_engine):
    headers = signup(client)
    with Session(db_engine) as session:
        store_product(session, FoodObservation.model_validate(FOOD), "fixture", {})
        session.commit()

    class Unavailable:
        async def search(self, *args):
            raise ProviderError("Unavailable")

    client.app.state.off = Unavailable()
    result = client.get(
        "/api/products/search", params={"q": "crackers", "include_live": True}, headers=headers
    )
    assert result.status_code == 200
    assert result.json()["live_status"] == "unavailable"
    assert len(result.json()["products"]) == 1


def test_unconfigured_label_extraction_returns_manual_entry_path(client):
    import io

    from PIL import Image

    headers = signup(client)
    image = io.BytesIO()
    Image.new("RGB", (10, 10)).save(image, format="PNG")
    response = client.post(
        "/api/labels/extract",
        headers=headers,
        files={"file": ("label.png", image.getvalue(), "image/png")},
    )
    assert response.status_code == 503
    assert "manually" in response.json()["detail"]


def test_readiness_requires_current_nonempty_migration_revision(client, db_engine):
    # The installed revision must equal the packaged head, so read the head from the
    # migration scripts instead of hardcoding a revision that a new migration moves.
    from alembic.script import ScriptDirectory

    migrations = Path(__file__).resolve().parents[1] / "migrations"
    head = next(iter(ScriptDirectory(str(migrations)).get_heads()))
    assert client.get("/health/ready").status_code == 503
    with db_engine.begin() as connection:
        connection.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32))"))
    try:
        assert client.get("/health/ready").status_code == 503
        with db_engine.begin() as connection:
            connection.execute(text("INSERT INTO alembic_version VALUES ('older_revision')"))
        assert client.get("/health/ready").status_code == 503
        with db_engine.begin() as connection:
            connection.execute(
                text("UPDATE alembic_version SET version_num = :head"), {"head": head}
            )
        assert client.get("/health/ready").json()["migrations"] == "current"
    finally:
        with db_engine.begin() as connection:
            connection.execute(text("DROP TABLE alembic_version"))


def test_product_search_escapes_literal_wildcards_and_backslash(client, db_engine):
    headers = signup(client)
    with Session(db_engine) as session:
        for source_id, name in [("literal", r"100\% crackers"), ("other", "100x crackers")]:
            store_product(
                session, FoodObservation.model_validate({**FOOD, "name": name}), source_id, {}
            )
        session.commit()
    for route in ("/api/products", "/api/products/search"):
        result = client.get(route, params={"q": r"100\%"}, headers=headers)
        assert result.status_code == 200
        assert [item["food"]["name"] for item in result.json()["products"]] == [r"100\% crackers"]
    assert (
        client.get("/api/products/search/live", params={"q": "  "}, headers=headers).status_code
        == 422
    )


def test_food_and_lookup_share_supported_barcode_lengths(client):
    import pytest
    from pydantic import ValidationError

    headers = signup(client)
    for barcode in ("123456789", "12345678901", "١٢٣٤٥٦٧٨"):
        assert client.get("/api/products/barcode/" + barcode, headers=headers).status_code == 422
        with pytest.raises(ValidationError):
            FoodObservation.model_validate({**FOOD, "barcode": barcode})
    for barcode in ("12345678", "123456789012", "1234567890123", "12345678901234"):
        assert FoodObservation.model_validate({**FOOD, "barcode": barcode}).barcode == barcode


def test_barcode_refresh_keeps_operator_reviewed_label_and_reports_source(client, db_engine):
    headers = signup(client)
    with Session(db_engine) as session:
        reviewed = FoodObservation.model_validate(
            {
                **FOOD,
                "barcode": "8904004400052",
                "source": {"kind": "manual", "reference": "Synthetic reviewed package"},
            }
        )
        store_product(session, reviewed, "reviewed-cracker", {})
        session.commit()

    class LiveCommunityRecord:
        async def product(self, barcode):
            return {
                "code": barcode,
                "product_name": "Unverified community variant",
                "ingredients_text": "Milk",
            }

    client.app.state.off = LiveCommunityRecord()
    result = client.get(
        "/api/products/barcode/8904004400052", params={"refresh": True}, headers=headers
    )
    assert result.status_code == 200
    assert result.json()["lookup_source"] == "reviewed_snapshot"
    assert result.json()["food"]["ingredients_text"] == FOOD["ingredients_text"]
    assert result.json()["food"]["ingredients_complete"] is True


def test_source_trace_is_saved_with_corrections_and_survives_catalog_changes(client, db_engine):
    headers = signup(client)
    profile = save_profile(client, headers)
    source = {
        "kind": "openfoodfacts",
        "reference": "https://world.openfoodfacts.org/product/3017620422003",
    }
    observation = {**FOOD, "barcode": "3017620422003", "source": source}
    raw = {
        "code": "3017620422003",
        "product_name": FOOD["name"],
        "nutrition_data_per": "100g",
        "nutriments": {"sodium_100g": 0.8},
    }
    with Session(db_engine) as session:
        product = store_product(
            session, FoodObservation.model_validate(observation), raw["code"], raw
        )
        session.commit()
        product_id = product.id
    assert client.get(f"/api/products/{product_id}/provenance", headers=headers).status_code == 200
    submitted = {
        **observation,
        "nutrients": {"sodium_mg": 450},
        "source": {**source, "edited_fields": ["sodium_mg"]},
    }
    response = client.post(
        "/api/assessments",
        headers=headers,
        json={
            "profile_id": profile["id"],
            "profile_version": profile["version"],
            "food": submitted,
        },
    )
    assert response.status_code == 201
    saved = response.json()
    assert saved["food"]["nutrients"]["sodium_mg"] == 450
    assert saved["profile_snapshot"]["allergies"] == ["milk"]
    assert saved["result"]["source_trace"]["edited_fields"] == ["sodium_mg"]
    sodium = next(
        item for item in saved["result"]["source_trace"]["fields"] if item["field"] == "sodium_mg"
    )
    assert sodium["source_value"] == 0.8 and sodium["value"] == 800
    with Session(db_engine) as session:
        updated = {**observation, "nutrients": {"sodium_mg": 100}}
        store_product(
            session,
            FoodObservation.model_validate(updated),
            raw["code"],
            {**raw, "nutriments": {"sodium_100g": 0.1}},
        )
        session.commit()
    reloaded = client.get(f"/api/assessments/{saved['id']}", headers=headers).json()
    assert reloaded["result"]["source_trace"] == saved["result"]["source_trace"]


def test_every_api_route_requires_authentication(client):
    import io

    from PIL import Image

    assessment_body = {
        "profile_id": str(uuid4()),
        "profile_version": 1,
        "food": {**FOOD, "source": {"kind": "demo", "reference": "auth probe"}},
    }
    routes = [
        ("get", "/api/products", {}),
        ("get", "/api/products/search", {"params": {"q": "crackers"}}),
        ("get", "/api/products/search/live", {"params": {"q": "crackers"}}),
        ("get", "/api/products/barcode/12345678", {}),
        ("get", "/api/products/unknown-id", {}),
        ("get", "/api/products/unknown-id/provenance", {}),
        ("get", "/api/reference-foods", {"params": {"q": "rice"}}),
        ("get", "/api/auth/me", {}),
        ("get", "/api/profiles/me", {}),
        ("put", "/api/profiles/me", {"json": {"data": {}}}),
        (
            "post",
            "/api/profiles/guide",
            {"json": {"profile_id": str(uuid4()), "profile_version": 1}},
        ),
        ("post", "/api/assessments", {"json": assessment_body}),
        ("get", "/api/assessments", {}),
        ("get", "/api/assessments/unknown-id", {}),
        ("post", "/api/recommendations", {"json": {"assessment_id": str(uuid4())}}),
        ("get", "/api/recommendations/unknown-id", {}),
        ("get", "/api/dishes/options", {}),
        (
            "post",
            "/api/dishes/assess",
            {
                "json": {
                    "profile_id": str(uuid4()),
                    "profile_version": 1,
                    "name": "Probe dish",
                    "ingredients": [{"text": "rice"}],
                }
            },
        ),
    ]
    for method, path, kwargs in routes:
        response = getattr(client, method)(path, **kwargs)
        assert response.status_code == 401, (method, path, response.status_code)
    image = io.BytesIO()
    Image.new("RGB", (10, 10)).save(image, format="PNG")
    extract = client.post(
        "/api/labels/extract", files={"file": ("label.png", image.getvalue(), "image/png")}
    )
    assert extract.status_code == 401
    # Register and login stay open; only token-protected routes are gated.
    assert (
        client.post(
            "/api/auth/register", json={"email": "open@example.com", "password": "too-short"}
        ).status_code
        != 401
    )


def test_auth_rate_limit_returns_429_with_retry_after(client, monkeypatch):
    monkeypatch.setattr(
        rate_limit_module, "get_settings", lambda: Settings(rate_limit_auth_per_minute=2)
    )
    for index in range(2):
        response = client.post(
            "/api/auth/register",
            json={"email": f"throttle{index}@example.com", "password": "A-test-password-123"},
        )
        assert response.status_code == 201, response.text
    throttled = client.post(
        "/api/auth/register",
        json={"email": "throttle-blocked@example.com", "password": "A-test-password-123"},
    )
    assert throttled.status_code == 429, throttled.text
    assert throttled.json()["code"] == "rate_limited"
    assert int(throttled.headers["Retry-After"]) >= 1


def test_request_body_cap_returns_413(client):
    # Sized from the configured ceiling so raising the limit does not silently turn this
    # into a route-validation test (it did: the payload used to fit after the cap moved).
    oversized = get_settings().max_body_bytes + 1024
    response = client.post(
        "/api/auth/register",
        json={"email": "huge@example.com", "password": "x" * oversized},
    )
    assert response.status_code == 413, response.text
    assert response.json()["code"] == "payload_too_large"


def test_legacy_assessment_rows_are_served_through_the_current_contract(client, db_engine):
    """Records written before findings had codes must not 500 the history endpoint."""
    headers = signup(client)
    profile = client.put("/api/profiles/me", headers=headers, json={"data": {}}).json()
    owner_id = client.get("/api/auth/me", headers=headers).json()["id"]
    legacy_result = {
        # The pre-contract shape: no status_reason, findings without code/title/detail.
        "rule_version": "prototype-2026-09-26.4",
        "ingredient_taxonomy_version": "ingredient-terms-2026-09-26.5",
        "status": "needs_information",
        "conflicts": [],
        "unresolved": [{"field": "ingredients", "message": "Old wording without a code."}],
        "considerations": [],
        "ingredient_findings": [],
        "source_warnings": [],
        "coverage": "Old coverage sentence.",
    }
    with db_engine.begin() as connection:
        connection.execute(
            Assessment.__table__.insert(),
            [
                {
                    "id": "legacy-1",
                    "owner_id": owner_id,
                    "profile_id": profile["id"],
                    "profile_version": profile["version"],
                    "profile_snapshot": profile["data"],
                    "food_snapshot": {
                        "name": "Legacy snack",
                        "source": {"kind": "demo", "reference": "x"},
                    },
                    "result": legacy_result,
                }
            ],
        )

    history = client.get("/api/assessments", headers=headers)
    assert history.status_code == 200, history.text
    stored = next(item for item in history.json()["assessments"] if item["id"] == "legacy-1")
    assert stored["result"]["status_reason"], "a legacy result needs a stated reason"
    finding = stored["result"]["unresolved"][0]
    assert finding["code"] == "legacy_field" or finding["code"].startswith("legacy_")
    assert finding["group"] == "unresolved"
    assert finding["title"] and finding["detail"]
    assert finding["message"] == "Old wording without a code.", "the stored wording is unchanged"

    detail = client.get("/api/assessments/legacy-1", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["result"]["unresolved"][0]["group"] == "unresolved"


class _FakeExtractor:
    """Stand-in for the vision adapter: returns a fixed observation, no provider call."""

    def __init__(self, food=None):
        self.food = food

    async def extract_label(self, content, mime_type):
        from app.schemas import FoodObservation

        return FoodObservation.model_validate(
            self.food
            or {
                "name": "Model guessed name",
                "basis": "100g",
                "ingredients_text": "Refined wheat flour (maida), sugar, milk solids, salt",
                "advisories_text": "May contain peanuts",
                "nutrients": {"sodium_mg": 780, "sugars_g": 9.4},
                "source": {"kind": "label_extraction", "reference": "Photo of the pack"},
            }
        )


def _label_photo():
    image = io.BytesIO()
    Image.new("RGB", (12, 12)).save(image, format="PNG")
    return image.getvalue()


def test_label_fallback_attaches_the_barcode_and_saves_the_pack(client, db_engine):
    """The documented fallback: no catalog record → photograph the pack → it is findable by barcode."""
    headers = signup(client)
    client.app.state.models = _FakeExtractor()

    response = client.post(
        "/api/labels/extract",
        headers=headers,
        files={"file": ("label.png", _label_photo(), "image/png")},
        data={"barcode": "8901234567890", "name": "NUTRI-CRUNCH CRACKERS"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["saved"] is True and body["product_id"]
    assert body["food"]["barcode"] == "8901234567890"
    # A user-supplied name wins over the model's guess; the extracted evidence is untouched.
    assert body["food"]["name"] == "NUTRI-CRUNCH CRACKERS"
    assert "maida" in body["food"]["ingredients_text"]

    lookup = client.get("/api/products/barcode/8901234567890", headers=headers)
    assert lookup.status_code == 200, lookup.text
    stored = lookup.json()
    assert stored["lookup_source"] == "saved_snapshot"
    assert stored["food"]["source"]["kind"] == "label_extraction"
    assert stored["food"]["nutrients"]["sodium_mg"] == 780

    # Re-uploading the same photo updates one record instead of duplicating it.
    again = client.post(
        "/api/labels/extract",
        headers=headers,
        files={"file": ("label.png", _label_photo(), "image/png")},
        data={"barcode": "8901234567890"},
    )
    assert again.status_code == 200
    with Session(db_engine) as session:
        rows = session.scalars(select(Product).where(Product.barcode == "8901234567890")).all()
    assert len(rows) == 1, "the same photo must not create a second catalog row"


def test_label_fallback_rejects_a_malformed_barcode_and_never_saves(client, db_engine):
    headers = signup(client)
    client.app.state.models = _FakeExtractor()
    response = client.post(
        "/api/labels/extract",
        headers=headers,
        files={"file": ("label.png", _label_photo(), "image/png")},
        data={"barcode": "12345"},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"
    with Session(db_engine) as session:
        assert session.scalars(select(Product)).all() == []


def test_label_extraction_without_a_barcode_stays_unsaved(client):
    headers = signup(client)
    client.app.state.models = _FakeExtractor()
    response = client.post(
        "/api/labels/extract",
        headers=headers,
        files={"file": ("label.png", _label_photo(), "image/png")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["saved"] is False and body["product_id"] is None
    assert body["food"]["barcode"] is None
