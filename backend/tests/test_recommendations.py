from app.schemas import FoodObservation, ProfileData
from app.services.recommendations import select_replacements


def food(name="Original", **changes):
    return FoodObservation.model_validate(
        {
            "name": name,
            "category": "crackers",
            "basis": "100g",
            "ingredients_text": "Rice flour, salt",
            "advisories_text": "",
            "ingredients_complete": True,
            "advisories_complete": True,
            "nutrients": {"sodium_mg": 800, "carbohydrates_g": 60},
            "source": {"kind": "demo", "reference": "Synthetic test fixture"},
            **changes,
        }
    )


def test_recommendations_require_same_confirmed_category():
    profile = ProfileData(goals=[{"nutrient": "sodium_mg", "direction": "lower"}])
    result = select_replacements(
        profile,
        food(),
        [
            ("good", food("Lower sodium", nutrients={"sodium_mg": 300})),
            (
                "other-category",
                food("Chips", category="potato_chips", nutrients={"sodium_mg": 100}),
            ),
            (
                "unknown-category",
                food("Uncategorized", category=None, nutrients={"sodium_mg": 100}),
            ),
        ],
    )
    assert [candidate["product_id"] for candidate in result["candidates"]] == ["good"]
    assert {item["product_id"] for item in result["excluded"]} == {
        "other-category",
        "unknown-category",
    }
    assert all("category" in item["reason"].lower() for item in result["excluded"])


def test_unknown_goal_nutrient_is_excluded_instead_of_treated_as_zero():
    profile = ProfileData(goals=[{"nutrient": "sodium_mg", "direction": "lower"}])
    result = select_replacements(
        profile,
        food(),
        [("missing-sodium", food("Unknown sodium", nutrients={"sodium_mg": None}))],
    )
    assert result["candidates"] == []
    assert result["excluded"][0]["product_id"] == "missing-sodium"


def test_candidate_must_clear_all_restrictions_and_have_complete_ingredient_checks():
    profile = ProfileData(
        allergies=["milk"], goals=[{"nutrient": "sodium_mg", "direction": "lower"}]
    )
    result = select_replacements(
        profile,
        food(),
        [
            ("eligible", food("Eligible", nutrients={"sodium_mg": 300})),
            (
                "allergen",
                food(
                    "Contains milk",
                    ingredients_text="Rice flour, milk powder",
                    nutrients={"sodium_mg": 200},
                ),
            ),
            (
                "incomplete",
                food("Incomplete", ingredients_complete=False, nutrients={"sodium_mg": 100}),
            ),
        ],
    )
    assert [candidate["product_id"] for candidate in result["candidates"]] == ["eligible"]
    assert {item["product_id"] for item in result["excluded"]} == {"allergen", "incomplete"}


def test_candidate_cannot_improve_one_goal_while_worsening_another():
    profile = ProfileData(
        goals=[
            {"nutrient": "sodium_mg", "direction": "lower"},
            {"nutrient": "carbohydrates_g", "direction": "lower"},
        ]
    )
    result = select_replacements(
        profile,
        food(),
        [
            (
                "worsens-carbohydrates",
                food("Mixed result", nutrients={"sodium_mg": 300, "carbohydrates_g": 70}),
            ),
            (
                "improves-both",
                food("Better on both", nutrients={"sodium_mg": 400, "carbohydrates_g": 50}),
            ),
        ],
    )
    assert [candidate["product_id"] for candidate in result["candidates"]] == ["improves-both"]
    assert result["excluded"][0]["product_id"] == "worsens-carbohydrates"
    assert "Worsens" in result["excluded"][0]["reason"]
