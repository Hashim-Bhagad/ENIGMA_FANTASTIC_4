"""Contracts PostgreSQL enforces that in-memory SQLite cannot.

Row locking, JSONB operator semantics, ``String(n)`` length validation, unique
constraints, and ``timestamptz`` round-tripping. The whole module skips with a
clear reason unless ``TEST_DATABASE_URL`` points at a scratch ``*_test`` database
(see ``tests/conftest.py``).
"""

import threading
from datetime import UTC, datetime

import pytest
from sqlalchemy import select, text, update
from sqlalchemy.exc import DataError, IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.api.accounts import save_profile
from app.catalog import store_product
from app.errors import ApiError
from app.models import Product, Profile, ReferenceFood, User
from app.schemas import FoodObservation, ProfileData, ProfileWrite
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


def product(**overrides):
    fields = {
        "name": "Fixture product",
        "source_kind": "demo",
        "source_id": "fixture",
        "observation": {},
        "raw": {},
    }
    fields.update(overrides)
    return Product(**fields)


def test_select_for_update_blocks_a_competing_writer(postgres_engine):
    with Session(postgres_engine) as session:
        owner = User(email="lock-owner@example.com", password_hash="hashed")
        session.add(owner)
        session.flush()
        profile = Profile(owner_id=owner.id, version=1, data={"allergies": []})
        session.add(profile)
        session.commit()
        profile_id = profile.id

    holder = postgres_engine.connect()
    contender = postgres_engine.connect()
    try:
        holder.begin()
        locked = holder.execute(
            text("SELECT id FROM profiles WHERE id = :id FOR UPDATE"), {"id": profile_id}
        ).scalar_one()
        assert locked == profile_id

        with pytest.raises(OperationalError) as blocked:
            with contender.begin():
                contender.execute(text("SET LOCAL lock_timeout = '250ms'"))
                contender.execute(
                    text("SELECT id FROM profiles WHERE id = :id FOR UPDATE"), {"id": profile_id}
                )
        assert "lock timeout" in str(blocked.value)
    finally:
        contender.close()
        holder.close()


def test_concurrent_stale_profile_write_conflicts(postgres_engine):
    with Session(postgres_engine) as session:
        owner = User(email="race-owner@example.com", password_hash="hashed")
        session.add(owner)
        session.flush()
        session.add(Profile(owner_id=owner.id, version=1, data={"allergies": []}))
        session.commit()
        owner_id = owner.id

    barrier = threading.Barrier(2, timeout=10)
    outcomes: dict[str, int] = {}

    def guarded_write(label: str):
        with Session(postgres_engine) as session:
            profile = session.scalar(select(Profile).where(Profile.owner_id == owner_id))
            barrier.wait()
            # Same guard as PUT /api/profiles/me: only one writer may advance a version.
            updated = session.execute(
                update(Profile)
                .where(Profile.id == profile.id, Profile.version == profile.version)
                .values(version=Profile.version + 1, data={"allergies": ["milk"]})
            )
            session.commit()
            outcomes[label] = updated.rowcount

    threads = [threading.Thread(target=guarded_write, args=(label,)) for label in ("a", "b")]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=15)
    assert not any(thread.is_alive() for thread in threads), "guarded writers did not finish"
    assert sorted(outcomes.values()) == [0, 1], outcomes

    with Session(postgres_engine) as session:
        stored = session.scalar(select(Profile).where(Profile.owner_id == owner_id))
        assert stored.version == 2


def test_stale_session_profile_write_is_rejected_with_conflict(client, postgres_engine):
    headers = signup(client)
    created = client.put(
        "/api/profiles/me", headers=headers, json={"data": {"allergies": ["milk"]}}
    )
    assert created.status_code == 200, created.text
    assert created.json()["version"] == 1

    with Session(postgres_engine, expire_on_commit=False) as stale:
        owner = stale.scalar(select(User).where(User.email == "first@example.com"))
        loaded = stale.scalar(select(Profile).where(Profile.owner_id == owner.id))
        assert loaded.version == 1

        advanced = client.put(
            "/api/profiles/me",
            headers=headers,
            json={"expected_version": 1, "data": {"allergies": ["eggs"]}},
        )
        assert advanced.status_code == 200, advanced.text
        assert advanced.json()["version"] == 2

        # This session still holds version 1; the guarded write must lose. The
        # payload differs from the stored one, so it is not an idempotent retry.
        with pytest.raises(ApiError) as conflict:
            save_profile(
                ProfileWrite(expected_version=1, data=ProfileData(allergies=["soy"])),
                owner,
                stale,
            )
    assert conflict.value.status_code == 409
    assert conflict.value.code == "profile_version_stale"


def test_jsonb_brand_search_matches_and_escapes_wildcards(client, postgres_engine):
    headers = signup(client)
    fixtures = [
        ("haldiram", "Snack haldiram", {"brands": "Haldiram"}),
        ("literal", "Snack literal", {"brands": "100% Pure"}),
        ("other", "Snack other", {"brands": "100x Pure"}),
    ]
    with Session(postgres_engine) as session:
        for source_id, name, raw in fixtures:
            food = FoodObservation.model_validate({**FOOD, "name": name})
            store_product(session, food, source_id, raw)
        session.commit()

    brand = client.get("/api/products", params={"q": "haldiram"}, headers=headers)
    assert brand.status_code == 200, brand.text
    assert [item["food"]["name"] for item in brand.json()["products"]] == ["Snack haldiram"]

    escaped = client.get("/api/products", params={"q": "100%"}, headers=headers)
    assert escaped.status_code == 200, escaped.text
    assert [item["food"]["name"] for item in escaped.json()["products"]] == ["Snack literal"]


def test_string_lengths_are_enforced(postgres_engine):
    with Session(postgres_engine) as session:
        session.add(ReferenceFood(code="C" * 21, name="Too long", data={}, source={}))
        with pytest.raises(DataError):
            session.commit()
        session.rollback()

    with Session(postgres_engine) as session:
        session.add(product(source_id="long-barcode", barcode="1" * 15))
        with pytest.raises(DataError):
            session.commit()
        session.rollback()


def test_unique_constraints_are_enforced(postgres_engine):
    with Session(postgres_engine) as session:
        session.add_all(
            [
                User(email="duplicate@example.com", password_hash="first"),
                User(email="duplicate@example.com", password_hash="second"),
            ]
        )
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

    with Session(postgres_engine) as session:
        session.add_all([product(source_id="shared"), product(source_id="shared")])
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()


def test_datetime_with_timezone_round_trips(postgres_engine):
    moment = datetime(2026, 1, 2, 3, 4, 5, 123456, tzinfo=UTC)
    with Session(postgres_engine) as session:
        session.add(product(source_id="tz-round-trip", updated_at=moment))
        session.commit()

    with Session(postgres_engine) as session:
        stored = session.scalar(select(Product).where(Product.source_id == "tz-round-trip"))
        assert stored.updated_at.tzinfo is not None
        assert stored.updated_at == moment
