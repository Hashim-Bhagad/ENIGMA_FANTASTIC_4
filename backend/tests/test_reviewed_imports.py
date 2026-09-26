import json

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.importers import import_reviewed_products
from app.models import Product


def reviewed_food():
    return {
        "name": "Test reviewed cracker",
        "category": "crackers",
        "basis": "100g",
        "ingredients_text": "Rice flour, salt",
        "advisories_text": "",
        "ingredients_complete": True,
        "advisories_complete": True,
        "nutrients": {"sodium_mg": 200},
        "source": {"kind": "manual", "reference": "Synthetic reviewed-label test fixture"},
    }


def test_reviewed_catalog_import_is_idempotent_and_updates_snapshot(db_engine, tmp_path):
    file = tmp_path / "reviewed.json"
    record = {"source_id": "reviewed-cracker", "food": reviewed_food()}
    file.write_text(json.dumps([record]))
    with Session(db_engine) as session:
        assert import_reviewed_products(session, file)["reviewed_products"] == 1
        initial = session.scalar(select(Product)).id
        record["food"]["nutrients"]["sodium_mg"] = 180
        file.write_text(json.dumps([record]))
        import_reviewed_products(session, file)
        assert session.scalar(select(func.count()).select_from(Product)) == 1
        updated = session.get(Product, initial)
        assert updated.observation["nutrients"]["sodium_mg"] == 180
        assert updated.source_kind == "manual"


def test_reviewed_import_rejects_unchecked_data_before_writing(db_engine, tmp_path):
    valid = {"source_id": "valid", "food": reviewed_food()}
    invalid = {"source_id": "invalid", "food": {**reviewed_food(), "advisories_complete": False}}
    file = tmp_path / "reviewed.json"
    file.write_text(json.dumps([valid, invalid]))
    with Session(db_engine) as session:
        with pytest.raises(ValueError, match="advisory panel"):
            import_reviewed_products(session, file)
        assert session.scalar(select(func.count()).select_from(Product)) == 0
        file.write_text(json.dumps([valid, valid]))
        with pytest.raises(ValueError, match="unique"):
            import_reviewed_products(session, file)
        assert session.scalar(select(func.count()).select_from(Product)) == 0
