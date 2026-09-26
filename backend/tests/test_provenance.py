from datetime import UTC, datetime

from app.integrations.off import normalize_off
from app.models import Product
from app.services.provenance import product_provenance


def snapshot(raw):
    food = normalize_off(raw)
    return Product(
        id="test-product",
        name=food.name,
        barcode=food.barcode,
        source_kind="openfoodfacts",
        source_id="test",
        observation=food.model_dump(mode="json"),
        raw=raw,
        updated_at=datetime.now(UTC),
    )


def test_trace_preserves_raw_sodium_conversion_and_does_not_substitute_salt():
    raw = {
        "code": "3017620422003",
        "product_name": "Test source",
        "nutrition_data_per": "100g",
        "nutriments": {"sodium_100g": 0.0428, "salt_100g": 0.107, "sugars_100g": 0},
    }
    trace = product_provenance(snapshot(raw))
    sodium = next(item for item in trace["fields"] if item["field"] == "sodium_mg")
    assert sodium["source_value"] == 0.0428
    assert sodium["source_unit"] == "g"
    assert sodium["value"] == 42.8
    assert sodium["unit"] == "mg"
    assert sodium["source_field"] == "nutriments.sodium_100g"
    assert trace["source_salt"]["used_by_backend"] is False
    assert trace["source_salt"]["source_value"] == 0.107
    sugar = next(item for item in trace["fields"] if item["field"] == "sugars_g")
    assert sugar["status"] == "available" and sugar["value"] == 0
    assert len(trace["raw_snapshot_sha256"]) == 64


def test_trace_explains_missing_basis_missing_values_and_quarantined_amounts():
    for raw, field, status in [
        (
            {"nutrition_data_per": "serving", "nutriments": {"sodium_100g": 0.5}},
            "sodium_mg",
            "unknown_basis",
        ),
        ({"nutrition_data_per": "100g", "nutriments": {"salt_100g": 1}}, "sodium_mg", "missing"),
        (
            {"nutrition_data_per": "100g", "nutriments": {"sodium_100g": 788}},
            "sodium_mg",
            "unusable",
        ),
    ]:
        product = snapshot({"code": "3017620422003", "product_name": "Test source", **raw})
        entry = next(
            item for item in product_provenance(product)["fields"] if item["field"] == field
        )
        assert entry["status"] == status
        assert entry["value"] is None and entry["reason"]
