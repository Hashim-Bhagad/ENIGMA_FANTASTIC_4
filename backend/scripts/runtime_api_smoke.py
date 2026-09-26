"""Run a synthetic end-to-end API check against an already running local stack.

Usage from the repository root: uv --directory backend run python scripts/runtime_api_smoke.py
This creates two throwaway accounts and one clearly named synthetic product.
It never calls Fireworks, Jev, Open Food Facts, or Apify.
"""

from __future__ import annotations

import json
import os
import secrets
import sys
import urllib.error
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from sqlalchemy import select  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.db import _session_factory  # noqa: E402
from app.models import Product, ReferenceFood  # noqa: E402

BASE_URL = os.environ.get("SMOKE_API_URL", "http://127.0.0.1:8000").rstrip("/")


def request(
    method: str,
    path: str,
    body: dict | None = None,
    token: str | None = None,
    expected_error: int | None = None,
):
    headers = {"Accept": "application/json"}
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(BASE_URL + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=12) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as exc:
        if exc.code == expected_error:
            return exc.code, json.loads(exc.read())
        detail = exc.read().decode(errors="replace")[:500]
        raise RuntimeError(f"{method} {path} returned HTTP {exc.code}: {detail}") from None


def food(name: str, sodium: float, ingredients: str, *, source_id: str) -> dict:
    return {
        "name": name,
        "brand": "Synthetic smoke test",
        "category": "smoke-test-crackers",
        "basis": "100g",
        "ingredients_text": ingredients,
        "advisories_text": "",
        "ingredients_complete": True,
        "advisories_complete": True,
        "nutrients": {"sodium_mg": sodium},
        "source": {"kind": "demo", "reference": f"smoke:{source_id}"},
    }


def main() -> None:
    run_id = uuid.uuid4().hex[:12]
    email = f"runtime-smoke-{run_id}@example.com"
    session_factory = _session_factory(get_settings().database_url)
    # Remove fixtures from earlier runs: they compete for the same top-5 candidate
    # slots and make a repeated run non-deterministic.
    with session_factory() as session:
        for stale in session.scalars(select(Product).where(Product.source_kind == "demo")):
            if isinstance(stale.raw, dict) and stale.raw.get("purpose") == "runtime smoke check":
                session.delete(stale)
        session.commit()
    candidate_food = food(
        f"Smoke Test Lower Sodium {run_id}", 100, "rice flour, oil", source_id=run_id
    )
    product_id = str(uuid.uuid4())
    with session_factory() as session:
        session.add(
            Product(
                id=product_id,
                barcode=None,
                name=candidate_food["name"],
                category=candidate_food["category"],
                source_kind="demo",
                source_id=f"smoke-{run_id}",
                observation=candidate_food,
                raw={"synthetic": True, "purpose": "runtime smoke check"},
            )
        )
        session.commit()

    status, registration = request(
        "POST",
        "/api/auth/register",
        {"email": email, "password": secrets.token_urlsafe(18)},
    )
    assert status == 201
    token = registration["access_token"]
    owner = registration["user"]["id"]
    assert request("GET", "/api/auth/me", token=token)[1]["id"] == owner

    # Product routes now require a bearer token.
    status, provenance = request("GET", f"/api/products/{product_id}/provenance", token=token)
    assert status == 200 and provenance["source"]["kind"] == "demo"
    sodium_trace = next(item for item in provenance["fields"] if item["field"] == "sodium_mg")
    assert sodium_trace["value"] == 100 and sodium_trace["unit"] == "mg"

    profile_payload = {
        "expected_version": None,
        "data": {
            "conditions": [],
            "allergies": ["wheat"],
            "ingredient_exclusions": [],
            "limits": [],
            "goals": [{"nutrient": "sodium_mg", "direction": "lower"}],
            "preferences": "",
        },
    }
    status, profile = request("PUT", "/api/profiles/me", profile_payload, token)
    assert status == 200 and profile["version"] == 1

    original = food(f"Smoke Test Wheat Cracker {run_id}", 500, "maida, oil", source_id=run_id)
    status, assessment = request(
        "POST",
        "/api/assessments",
        {
            "profile_id": profile["id"],
            "profile_version": profile["version"],
            "food": original,
            "portion": 30,
        },
        token,
    )
    assert status == 201
    assert assessment["result"]["conflicts"], "maida should trigger the wheat restriction"
    assert any(
        item["raw_evidence"] == "maida" and item.get("wheat_allergen")
        for item in assessment["result"]["ingredient_findings"]
    ), "the assessment must preserve evidence for its canonical ingredient match"

    status, recommendation = request(
        "POST",
        "/api/recommendations",
        {"assessment_id": assessment["id"]},
        token,
    )
    assert status == 201
    assert any(x["product_id"] == product_id for x in recommendation["candidates"])
    assert "needs_review" in recommendation, "the two-tier replacement contract must be present"
    candidate_ids = {x["product_id"] for x in recommendation["candidates"]}
    review_ids = {x["product_id"] for x in recommendation["needs_review"]}
    assert not candidate_ids & review_ids, "verified and unverified tiers must never overlap"
    assert all(x["verified"] for x in recommendation["candidates"])
    assert all(not x["verified"] and x["review_reasons"] for x in recommendation["needs_review"]), (
        "unverified candidates must explain what is missing"
    )
    status, history = request("GET", "/api/assessments", token=token)
    assert status == 200 and any(x["id"] == assessment["id"] for x in history["assessments"])
    status, saved_recommendation = request(
        "GET", f"/api/recommendations/{recommendation['id']}", token=token
    )
    assert status == 200 and saved_recommendation["assessment_id"] == assessment["id"]

    # Cooked-meal check: a reference match yields an estimate, and preparation notes explain
    # what cooking hides. IFCT may not be imported locally, so the estimate is optional.
    with session_factory() as session:
        reference = session.scalar(select(ReferenceFood).order_by(ReferenceFood.code))
    ingredients = [{"text": "Rice", "grams": 150}]
    if reference is not None:
        ingredients = [{"text": reference.name, "reference_code": reference.code, "grams": 150}]
    status, dish = request(
        "POST",
        "/api/dishes/assess",
        {
            "profile_id": profile["id"],
            "profile_version": profile["version"],
            "name": f"Smoke dish {run_id}",
            "ingredients": ingredients,
            "cooking_notes": ["deep_fried"],
            "declarations_confirmed": True,
            "portion_g": 250,
        },
        token,
    )
    assert status == 201
    assert dish["dish"]["estimate"]["available"] is (reference is not None)
    assert dish["assessment"]["status_reason"]
    assert any(
        item["code"] == "cooking_deep_fried" and item["next_step"]
        for item in dish["assessment"]["considerations"]
    ), "preparation notes must produce explained considerations"
    assert request("GET", "/api/dishes/options", token=token)[0] == 200

    other = request(
        "POST",
        "/api/auth/register",
        {
            "email": f"runtime-smoke-other-{run_id}@example.com",
            "password": secrets.token_urlsafe(18),
        },
    )[1]
    other_status, _ = request(
        "GET",
        f"/api/assessments/{assessment['id']}",
        token=other["access_token"],
        expected_error=404,
    )
    assert other_status == 404, "another account must not read the assessment"
    assert (
        request(
            "GET",
            f"/api/recommendations/{recommendation['id']}",
            token=other["access_token"],
            expected_error=404,
        )[0]
        == 404
    ), "another account must not read the replacement run"

    status, updated = request(
        "PUT",
        "/api/profiles/me",
        {
            **profile_payload,
            "expected_version": profile["version"],
            "data": {**profile_payload["data"], "preferences": "Smoke test preference change"},
        },
        token,
    )
    assert status == 200 and updated["version"] == profile["version"] + 1
    assert (
        request(
            "POST",
            "/api/recommendations",
            {"assessment_id": assessment["id"]},
            token,
            expected_error=409,
        )[0]
        == 409
    ), "a changed profile must require a new assessment"

    print(
        json.dumps(
            {
                "result": "passed",
                "api": BASE_URL,
                "account": "generated throwaway account",
                "checks": [
                    "register and JWT-authenticated identity",
                    "save versioned profile",
                    "saved product source trace",
                    "maida-to-wheat assessment",
                    "canonical ingredient evidence preserved",
                    "eligible synthetic replacement request and persisted detail",
                    "two-tier replacement contract (verified vs needs_review never overlap)",
                    "cooked-meal check with preparation notes and optional reference estimate",
                    "assessment history",
                    "cross-account assessment ownership returns 404",
                    "cross-account recommendation ownership returns 404",
                    "stale profile requires reassessment",
                ],
                "synthetic_product_id": product_id,
                "assessment_id": assessment["id"],
                "recommendation_id": recommendation["id"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
