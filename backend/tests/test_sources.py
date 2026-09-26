import csv
import io

from sqlalchemy.orm import Session

from app.catalog import store_off, store_product
from app.importers import normalize_ifct
from app.integrations.off import normalize_apify_off, normalize_off


def test_off_sodium_normalized_grams_are_converted_to_mg():
    record = {
        "code": "3017620422003",
        "product_name": "Test",
        "nutrition_data_per": "100g",
        "nutriments": {"sodium_100g": 0.0428, "sugars_100g": 0},
    }
    result = normalize_off(record)
    assert result.nutrients["sodium_mg"] == 42.8
    assert result.nutrients["sugars_g"] == 0
    assert result.nutrients["fiber_g"] is None
    assert not result.advisories_complete


def test_observed_bhujia_outlier_is_quarantined_not_reinterpreted_as_mg():
    result = normalize_off(
        {
            "code": "8904004400052",
            "nutrition_data_per": "100g",
            "nutriments": {"sodium_100g": 788, "carbohydrates_100g": 37.36},
        }
    )
    assert result.nutrients["sodium_mg"] is None
    assert result.nutrients["carbohydrates_g"] == 37.36
    assert any("quarantined" in x for x in result.source.warnings)


def test_flattened_apify_units_are_not_assumed():
    result = normalize_apify_off(
        {"product_name": "Test", "barcode": "8904004400052", "sodium_100g": 788},
        "h5n0pJBId8vHhHMNT",
    )
    assert result.nutrients["sodium_mg"] is None
    assert result.basis is None


def test_ifct_uses_its_representation_metadata_and_preserves_missing_values():
    units = {
        r["code"]: r
        for r in csv.DictReader(
            io.StringIO(
                "code,factor,unit\nna,1000,mg\np,1000,mg\nk,1000,mg\nenerc,1,kJ\nprotcnt,1,g\nchoavldf,1,g\nfatce,1,g\nfibtg,1,g\n"
            )
        )
    }
    result = normalize_ifct(
        {"code": "A001", "name": "Amaranth", "na": "0.0027", "enerc": "1490", "p": "", "k": "NaN"},
        units,
    )
    assert result["nutrients"]["sodium_mg"] == 2.7
    assert round(result["nutrients"]["energy_kcal"], 2) == 356.12
    assert result["nutrients"]["phosphorus_mg"] is None
    assert result["nutrients"]["potassium_mg"] is None
    assert "sugars_g" not in result["nutrients"]


def test_off_allergen_tags_do_not_turn_may_contain_into_declared_ingredients():
    from app.schemas import ProfileData
    from app.services.assessment import assess

    food = normalize_off(
        {
            "code": "8904004400052",
            "ingredients_text": "Gram flour; May contain milk",
            "allergens_tags": ["en:milk", "en:soybeans"],
        }
    )
    result = assess(ProfileData(allergies=["milk", "soy"]), food)
    assert food.declared_allergens == []
    assert {c["kind"] for c in result["conflicts"]} == {
        "precautionary_advisory",
        "source_reported_allergen",
    }


def test_off_specific_categories_enable_only_allow_listed_like_for_like_matching():
    result = normalize_off(
        {
            "code": "12345678",
            "categories_tags": ["en:appetizers", "en:crackers-appetizers"],
            "nutrition_data_per": "100g",
        }
    )
    assert result.category == "crackers_appetizers"
    assert result.basis == "100g"


def test_off_unknown_or_conflicting_categories_stay_uncategorized():
    unsupported = normalize_off({"code": "12345678", "categories_tags": ["en:snacks"]})
    conflicting = normalize_off(
        {
            "code": "12345678",
            "categories_tags": ["en:crackers-appetizers", "en:biscuits"],
        }
    )
    assert unsupported.category is None
    assert conflicting.category is None
    assert any("manual curation" in warning for warning in unsupported.source.warnings)
    assert any("conflict" in warning for warning in conflicting.source.warnings)


def test_off_category_curation_wins_and_barcode_shape_matches_client_contract():
    curated = normalize_off(
        {"code": "123456789", "categories_tags": ["en:crackers-appetizers"]},
        category="cracker snacks",
    )
    assert curated.category == "cracker snacks"
    assert curated.barcode is None
    assert any("barcode" in warning for warning in curated.source.warnings)


def test_off_category_tag_does_not_fill_missing_nutrients():
    result = normalize_off({"code": "12345678", "categories_tags": ["en:crackers-appetizers"]})
    assert result.category == "crackers_appetizers"
    assert result.basis is None
    assert all(value is None for value in result.nutrients.values())


def test_catalog_keeps_raw_categories_and_manual_category_curation(db_engine):
    raw = {
        "code": "12345678",
        "product_name": "Source title",
        "categories_tags": ["en:appetizers", "en:crackers-appetizers"],
    }
    with Session(db_engine) as session:
        first = store_off(session, raw)
        session.commit()
        assert first.category == "crackers_appetizers"
        assert first.raw["categories_tags"] == raw["categories_tags"]

        first.category = "curated_cracker_product"
        session.commit()
        updated = store_off(session, {**raw, "product_name": "Updated source title"})
        session.commit()
        assert updated.category == "curated_cracker_product"
        assert updated.observation["category"] == "curated_cracker_product"
        assert updated.raw["categories_tags"] == raw["categories_tags"]


def test_catalog_refreshes_inferred_category_when_off_tags_change(db_engine):
    with Session(db_engine) as session:
        store_off(
            session,
            {
                "code": "12345678",
                "product_name": "Source title",
                "categories_tags": ["en:crackers-appetizers"],
            },
        )
        session.commit()
        refreshed = store_off(
            session,
            {
                "code": "12345678",
                "product_name": "Updated title",
                "categories_tags": ["en:breakfast-cereals"],
            },
        )
        session.commit()
        assert refreshed.category == "breakfast_cereals"
        assert refreshed.raw["categories_tags"] == ["en:breakfast-cereals"]


def test_catalog_preserves_reviewed_manual_observation_on_off_barcode_match(db_engine):
    from app.schemas import FoodObservation

    reviewed = FoodObservation.model_validate(
        {
            "name": "Reviewed cracker",
            "barcode": "12345678",
            "category": "curated_cracker_product",
            "basis": "100g",
            "ingredients_text": "Rice flour, salt",
            "advisories_text": "",
            "ingredients_complete": True,
            "advisories_complete": True,
            "nutrients": {"sodium_mg": 300},
            "source": {"kind": "manual", "reference": "Human checked package"},
        }
    )
    with Session(db_engine) as session:
        product = store_product(session, reviewed, "reviewed-12345678", {"reviewed": True})
        session.commit()
        returned = store_off(
            session,
            {
                "code": "12345678",
                "product_name": "Different community title",
                "categories_tags": ["en:breakfast-cereals"],
                "nutrition_data_per": "100g",
                "nutriments": {"sodium_100g": 0.01},
            },
        )
        assert returned.id == product.id
        assert returned.source_kind == "manual"
        assert returned.category == "curated_cracker_product"
        assert returned.observation["nutrients"]["sodium_mg"] == 300
        assert returned.raw == {"reviewed": True}


def test_catalog_keeps_unmapped_category_unknown_on_refresh(db_engine):
    with Session(db_engine) as session:
        store_off(
            session,
            {"code": "12345678", "categories_tags": ["en:snacks", "en:health"]},
        )
        session.commit()
        refreshed = store_off(
            session,
            {"code": "12345678", "categories_tags": ["en:snacks", "en:health"]},
        )
        session.commit()
        assert refreshed.category is None
