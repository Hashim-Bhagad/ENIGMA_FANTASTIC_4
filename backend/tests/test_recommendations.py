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


def test_unknown_goal_nutrient_is_never_treated_as_zero():
    profile = ProfileData(goals=[{"nutrient": "sodium_mg", "direction": "lower"}])
    result = select_replacements(
        profile,
        food(),
        [("missing-sodium", food("Unknown sodium", nutrients={"sodium_mg": None}))],
    )
    assert result["candidates"] == []
    assert [item["product_id"] for item in result["needs_review"]] == ["missing-sodium"]
    assert result["excluded"] == []


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
    # The allergen candidate fails a real rule; the incomplete one is unknown-data only.
    assert {item["product_id"] for item in result["excluded"]} == {"allergen"}
    assert [item["product_id"] for item in result["needs_review"]] == ["incomplete"]
    assert result["needs_review"][0]["verified"] is False
    assert result["needs_review"][0]["review_reasons"]


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


def test_needs_review_tier_never_contains_a_conflict_and_never_overlaps_candidates():
    profile = ProfileData(
        allergies=["milk"], goals=[{"nutrient": "sodium_mg", "direction": "lower"}]
    )
    result = select_replacements(
        profile,
        food(),
        [
            ("verified", food("Verified", nutrients={"sodium_mg": 300})),
            ("conflict", food("Has milk", ingredients_text="Rice, milk powder")),
            ("unknown", food("Community", advisories_complete=False, nutrients={"sodium_mg": 200})),
        ],
    )
    candidate_ids = [item["product_id"] for item in result["candidates"]]
    review_ids = [item["product_id"] for item in result["needs_review"]]
    assert candidate_ids == ["verified"]
    assert review_ids == ["unknown"]
    assert not set(candidate_ids) & set(review_ids)
    for item in result["needs_review"]:
        assert item["verified"] is False
        assert item["assessment"]["conflicts"] == []
        assert item["review_reasons"]
    assert len(result["needs_review"]) <= 5
    assert all(item["verified"] is True for item in result["candidates"])
    assert all(item["review_reasons"] == [] for item in result["candidates"])


def test_needs_review_candidates_are_ordered_separately_from_candidates():
    profile = ProfileData(
        allergies=["milk"], goals=[{"nutrient": "sodium_mg", "direction": "lower"}]
    )
    result = select_replacements(
        profile,
        food(),
        [
            ("zzz-unknown", food("Zeta", advisories_complete=False, nutrients={"sodium_mg": 50})),
            ("aaa-unknown", food("Alpha", advisories_complete=False, nutrients={"sodium_mg": 50})),
            ("good", food("Good", nutrients={"sodium_mg": 300})),
        ],
    )
    # Review tier is deterministic (product_id) and kept out of the candidate ordering.
    assert [item["product_id"] for item in result["needs_review"]] == [
        "aaa-unknown",
        "zzz-unknown",
    ]
    assert [item["product_id"] for item in result["candidates"]] == ["good"]


def test_message_states_unverified_tier_is_unconfirmed_and_no_check_relaxed():
    profile = ProfileData(
        allergies=["milk"], goals=[{"nutrient": "sodium_mg", "direction": "lower"}]
    )
    result = select_replacements(
        profile,
        food(ingredients_text="Rice, milk powder"),
        [
            (
                "unknown",
                food(
                    "Community",
                    advisories_complete=False,
                    nutrients={"sodium_mg": 100},
                ),
            ),
            ("good", food("Clean", nutrients={"sodium_mg": 300})),
        ],
    )
    assert [item["product_id"] for item in result["needs_review"]] == ["unknown"]
    assert "unconfirmed" in result["message"].lower()
    assert "no check was relaxed" in result["message"].lower()
