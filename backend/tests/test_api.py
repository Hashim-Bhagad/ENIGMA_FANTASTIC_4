from datetime import UTC, datetime, timedelta

import jwt
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.catalog import store_product
from app.config import get_settings
from app.integrations.off import ProviderError
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
    edit = client.put(
        "/api/profiles/me", headers=headers, json={"expected_version": 1, "data": saved["data"]}
    )
    assert edit.json()["version"] == 2
    stale = client.put(
        "/api/profiles/me", headers=headers, json={"expected_version": 1, "data": saved["data"]}
    )
    assert stale.status_code == 409
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
        "/api/profiles/me", headers=headers, json={"expected_version": 1, "data": profile["data"]}
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
    with Session(db_engine) as session:
        food = FoodObservation.model_validate({**FOOD, "barcode": "8904004400052"})
        store_product(session, food, "barcode-fixture", {"brands": "Haldiram"})
        session.commit()
    barcode = client.get("/api/products/search", params={"q": "8904004400052"})
    assert barcode.status_code == 200, barcode.text
    assert barcode.json()["query_type"] == "barcode"
    assert barcode.json()["lookup_source"] == "saved_snapshot"
    brand = client.get("/api/products/search", params={"q": "haldiram"})
    assert len(brand.json()["products"]) == 1
    assert client.get("/api/products/search", params={"q": "  "}).status_code == 422


def test_live_search_failure_retains_saved_results(client, db_engine):
    with Session(db_engine) as session:
        store_product(session, FoodObservation.model_validate(FOOD), "fixture", {})
        session.commit()

    class Unavailable:
        async def search(self, *args):
            raise ProviderError("Unavailable")

    client.app.state.off = Unavailable()
    result = client.get("/api/products/search", params={"q": "crackers", "include_live": True})
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
    assert client.get("/health/ready").status_code == 503
    with db_engine.begin() as connection:
        connection.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32))"))
    try:
        assert client.get("/health/ready").status_code == 503
        with db_engine.begin() as connection:
            connection.execute(text("INSERT INTO alembic_version VALUES ('older_revision')"))
        assert client.get("/health/ready").status_code == 503
        with db_engine.begin() as connection:
            connection.execute(text("UPDATE alembic_version SET version_num = '0001_initial'"))
        assert client.get("/health/ready").json()["migrations"] == "current"
    finally:
        with db_engine.begin() as connection:
            connection.execute(text("DROP TABLE alembic_version"))


def test_product_search_escapes_literal_wildcards_and_backslash(client, db_engine):
    with Session(db_engine) as session:
        for source_id, name in [("literal", r"100\% crackers"), ("other", "100x crackers")]:
            store_product(
                session, FoodObservation.model_validate({**FOOD, "name": name}), source_id, {}
            )
        session.commit()
    for route in ("/api/products", "/api/products/search"):
        result = client.get(route, params={"q": r"100\%"})
        assert result.status_code == 200
        assert [item["food"]["name"] for item in result.json()["products"]] == [r"100\% crackers"]
    assert client.get("/api/products/search/live", params={"q": "  "}).status_code == 422


def test_food_and_lookup_share_supported_barcode_lengths(client):
    import pytest
    from pydantic import ValidationError

    for barcode in ("123456789", "12345678901", "١٢٣٤٥٦٧٨"):
        assert client.get("/api/products/barcode/" + barcode).status_code == 422
        with pytest.raises(ValidationError):
            FoodObservation.model_validate({**FOOD, "barcode": barcode})
    for barcode in ("12345678", "123456789012", "1234567890123", "12345678901234"):
        assert FoodObservation.model_validate({**FOOD, "barcode": barcode}).barcode == barcode


def test_barcode_refresh_keeps_operator_reviewed_label_and_reports_source(client, db_engine):
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
    result = client.get("/api/products/barcode/8904004400052", params={"refresh": True})
    assert result.status_code == 200
    assert result.json()["lookup_source"] == "reviewed_snapshot"
    assert result.json()["food"]["ingredients_text"] == FOOD["ingredients_text"]
    assert result.json()["food"]["ingredients_complete"] is True
