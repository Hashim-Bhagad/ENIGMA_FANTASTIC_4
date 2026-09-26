from app.schemas import FoodObservation, ProfileData
from app.services.assessment import assess
from app.services.ingredient_taxonomy import TAXONOMY_VERSION, match_ingredients
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


def test_phrase_matching_does_not_find_egg_in_eggplant_or_milk_in_almond_milk():
    profile = ProfileData(allergies=["eggs", "milk"])
    result = assess(profile, food(ingredients_text="Eggplant, almond milk (water, almonds)"))
    assert result["conflicts"] == []


def test_known_allergen_and_missing_information_are_both_retained():
    result = assess(
        ProfileData(allergies=["milk"]),
        food(ingredients_text="Rice flour, whey powder", advisories_complete=False),
    )
    assert result["conflicts"][0]["restriction"] == "milk"
    assert any(x["field"] == "advisories" for x in result["unresolved"])


def test_advisory_is_not_treated_as_declared_ingredient():
    result = assess(ProfileData(allergies=["peanuts"]), food(advisories_text="May contain peanuts"))
    assert result["conflicts"][0]["kind"] == "precautionary_advisory"


def test_daily_limit_shows_contribution_not_automatic_per_food_failure():
    profile = ProfileData(
        limits=[
            {
                "nutrient": "sodium_mg",
                "maximum": 1500,
                "scope": "daily",
                "source": "Clinician supplied",
            }
        ]
    )
    result = assess(profile, food(), portion=30)
    assert result["conflicts"] == []
    assert result["considerations"][0]["portion_amount"] == 240
    assert result["considerations"][0]["daily_limit_percent"] == 16


def test_replacements_check_every_restriction_and_do_not_fill_unknowns():
    profile = ProfileData(
        allergies=["milk"], goals=[{"nutrient": "sodium_mg", "direction": "lower"}]
    )
    candidates = [
        ("good", food("Good", nutrients={"sodium_mg": 200, "carbohydrates_g": 50})),
        ("milk", food("Milk", ingredients_text="Rice, milk powder", nutrients={"sodium_mg": 100})),
        ("unknown", food("Unknown", advisories_complete=False, nutrients={"sodium_mg": 50})),
        ("liquid", food("Liquid", basis="100ml", nutrients={"sodium_mg": 20})),
    ]
    result = select_replacements(profile, food(), candidates)
    assert [x["product_id"] for x in result["candidates"]] == ["good"]
    assert len(result["excluded"]) == 3


def test_missing_goal_nutrient_is_not_zero():
    profile = ProfileData(goals=[{"nutrient": "sodium_mg", "direction": "lower"}])
    result = select_replacements(profile, food(), [("missing", food(nutrients={}))])
    assert result["candidates"] == []


def test_allergen_removal_can_be_an_improvement_without_a_nutrient_goal():
    profile = ProfileData(allergies=["milk"])
    result = select_replacements(
        profile, food(ingredients_text="Rice, milk powder"), [("good", food())]
    )
    assert result["candidates"][0]["product_id"] == "good"


def test_wheat_flour_synonyms_preserve_refined_and_whole_wheat_subtypes():
    result = assess(
        ProfileData(allergies=["wheat"]),
        food(ingredients_text="Maida, all-purpose flour, whole-wheat atta"),
    )
    assert result["rule_version"].endswith(".4")
    assert result["ingredient_taxonomy_version"] == TAXONOMY_VERSION
    flour = [item for item in result["ingredient_findings"] if item["canonical_group"] == "flour"]
    assert [item["subtype"] for item in flour] == [
        "refined_wheat_flour",
        "refined_wheat_flour",
        "whole_wheat_flour",
    ]
    assert result["conflicts"][0]["restriction"] == "wheat"
    assert not any(item["field"] == "ingredient_interpretation" for item in result["unresolved"])


def test_sugar_aliases_are_grouped_without_claiming_added_sugar_or_nutrition_amounts():
    words = (
        "sucrose, dextrose, glucose syrup, high fructose corn syrup, invert sugar, "
        "cane sugar, brown sugar, jaggery, gur, honey, molasses, agave syrup, "
        "maple syrup, maltose, lactose, fructose, rice syrup, date syrup, "
        "coconut sugar, fruit juice concentrate"
    )
    findings = match_ingredients(words)
    assert len(findings) == 20
    assert {item["canonical_group"] for item in findings} == {"sugars"}
    assert {item["subtype"] for item in findings} >= {
        "sucrose",
        "glucose",
        "fructose",
        "mixed_sugar_syrup",
        "plant_syrup",
        "sweetener_source",
    }
    assert all("raw_evidence" in item and "start" in item and "end" in item for item in findings)
    assert all("added" not in item and "amount" not in item for item in findings)


def test_polyols_and_nonnutritive_sweeteners_remain_distinct_from_sugars():
    findings = match_ingredients("Maltitol, xylitol, sucralose and steviol glycosides")
    assert [(item["canonical_group"], item["subtype"]) for item in findings] == [
        ("sweeteners", "polyol"),
        ("sweeteners", "polyol"),
        ("sweeteners", "non_nutritive_sweetener"),
        ("sweeteners", "non_nutritive_sweetener"),
    ]


def test_unicode_normalization_offsets_and_longest_phrase_are_auditable():
    text = "ＦＬＯＵＲ: all‑purpose flour; glucose-fructose syrup"
    findings = match_ingredients(text)
    assert [item["subtype"] for item in findings] == [
        "refined_wheat_flour",
        "mixed_sugar_syrup",
    ]
    for item in findings:
        assert text[item["start"] : item["end"]] == item["raw_evidence"]
    assert findings[0]["raw_evidence"] == "all‑purpose flour"
    assert findings[1]["raw_evidence"] == "glucose-fructose syrup"


def test_generic_flour_and_unclassified_sweetener_stay_ambiguous():
    result = assess(
        ProfileData(allergies=["wheat"]),
        food(ingredients_text="Flour, sweetener, rice flour"),
    )
    unresolved = next(x for x in result["unresolved"] if x["field"] == "ingredient_interpretation")
    assert unresolved["evidence"] == ["Flour", "sweetener"]
    assert [x["subtype"] for x in result["ingredient_findings"]] == ["other_flour"]


def test_word_boundaries_do_not_match_substrings_or_advisory_text_as_ingredients():
    result = assess(
        ProfileData(allergies=["wheat"], ingredient_exclusions=["sugar"]),
        food(ingredients_text="Rice flour, may contain wheat; sugar-free claim"),
    )
    assert not any(x["kind"] == "declared_allergen" for x in result["conflicts"])
    assert not any(x["kind"] == "ingredient_exclusion" for x in result["conflicts"])


def test_sugar_exclusion_matches_sugar_aliases_but_not_polyols_or_other_carbohydrates():
    profile = ProfileData(ingredient_exclusions=["sugar"])
    sugar = assess(profile, food(ingredients_text="Sucrose, glucose syrup, honey"))
    assert next(x for x in sugar["conflicts"] if x["kind"] == "ingredient_exclusion")[
        "evidence"
    ] == ["Sucrose", "glucose syrup", "honey"]
    assert (
        "broad sugar-family"
        in next(x for x in sugar["conflicts"] if x["kind"] == "ingredient_exclusion")["message"]
    )
    for term in ("maltitol", "sucralose", "maltodextrin"):
        result = assess(profile, food(ingredients_text=term))
        assert not any(x["kind"] == "ingredient_exclusion" for x in result["conflicts"])


def test_specific_sugar_alias_exclusion_does_not_expand_to_the_whole_sugar_family():
    profile = ProfileData(ingredient_exclusions=["dextrose"])
    glucose = assess(profile, food(ingredients_text="Glucose, maltodextrin"))
    assert next(x for x in glucose["conflicts"] if x["kind"] == "ingredient_exclusion")[
        "evidence"
    ] == ["Glucose"]
    assert (
        "clinical equivalence"
        in next(x for x in glucose["conflicts"] if x["kind"] == "ingredient_exclusion")["message"]
    )
    other_sugar = assess(profile, food(ingredients_text="Sucrose, honey"))
    assert not any(x["kind"] == "ingredient_exclusion" for x in other_sugar["conflicts"])


def test_refined_flour_exclusions_match_synonyms_without_collapsing_atta_subtype():
    for exclusion, ingredient in (
        ("maida", "all-purpose flour"),
        ("all-purpose flour", "maida"),
        ("atta", "whole-wheat flour"),
    ):
        result = assess(
            ProfileData(ingredient_exclusions=[exclusion]),
            food(ingredients_text=ingredient),
        )
        assert any(x["kind"] == "ingredient_exclusion" for x in result["conflicts"])
    for exclusion, ingredient in (("maida", "atta"), ("atta", "maida")):
        result = assess(
            ProfileData(ingredient_exclusions=[exclusion]),
            food(ingredients_text=ingredient),
        )
        assert not any(x["kind"] == "ingredient_exclusion" for x in result["conflicts"])


def test_negated_ingredient_claims_are_not_reported_as_declared_ingredients():
    source = "No added sugar, not added sugar, sugar-free, wheat-free rice flour"
    result = assess(
        ProfileData(ingredient_exclusions=["sugar"], allergies=["wheat"]),
        food(ingredients_text=source),
    )
    assert result["ingredient_findings"] == [
        {
            "canonical_group": "flour",
            "subtype": "other_flour",
            "canonical_identity": "alias:rice flour",
            "matched_term": "rice flour",
            "raw_evidence": "rice flour",
            "start": source.index("rice flour"),
            "end": source.index("rice flour") + len("rice flour"),
            "wheat_allergen": False,
        }
    ]
    assert not any(
        x["kind"] in {"ingredient_exclusion", "declared_allergen"} for x in result["conflicts"]
    )

    milk_free = assess(
        ProfileData(allergies=["milk"]),
        food(ingredients_text="Milk-free dark chocolate (cocoa, sugar)"),
    )
    assert not any(x["kind"] == "declared_allergen" for x in milk_free["conflicts"])


def test_wheat_exclusion_is_broad_but_attached_allergen_advisory_keeps_its_kind():
    excluded = assess(
        ProfileData(ingredient_exclusions=["wheat"]),
        food(ingredients_text="Maida, may contain wheat"),
    )
    assert next(x for x in excluded["conflicts"] if x["kind"] == "ingredient_exclusion")[
        "evidence"
    ] == ["Maida"]
    allergy = assess(
        ProfileData(allergies=["wheat"]),
        food(ingredients_text="Rice flour, may contain wheat"),
    )
    assert [x["kind"] for x in allergy["conflicts"]] == ["precautionary_advisory"]


def test_wheat_semolina_alias_respects_explicit_nonwheat_grain_compounds():
    wheat = assess(ProfileData(allergies=["wheat"]), food(ingredients_text="Semolina"))
    assert any(x["kind"] == "declared_allergen" for x in wheat["conflicts"])
    for ingredient in ("Rice semolina", "Corn semolina", "Maize semolina"):
        result = assess(ProfileData(allergies=["wheat"]), food(ingredients_text=ingredient))
        assert not any(x["kind"] == "declared_allergen" for x in result["conflicts"])


def test_specific_exclusions_only_match_explicit_alias_identity_groups():
    true_aliases = (
        ("maida", "all-purpose flour"),
        ("atta", "wholemeal flour"),
        ("dextrose", "glucose"),
        ("sucrose", "table sugar"),
        ("chickpea flour", "besan"),
        ("stevia", "steviol glycosides"),
    )
    for exclusion, ingredient in true_aliases:
        result = assess(
            ProfileData(ingredient_exclusions=[exclusion]),
            food(ingredients_text=ingredient),
        )
        assert any(x["kind"] == "ingredient_exclusion" for x in result["conflicts"]), (
            exclusion,
            ingredient,
        )

    distinct_terms = (
        ("rice flour", "besan"),
        ("xylitol", "sorbitol"),
        ("sucralose", "aspartame"),
        ("honey", "molasses"),
        ("honey", "malt extract"),
        ("maple syrup", "agave syrup"),
        ("maple syrup", "date syrup"),
    )
    for exclusion, ingredient in distinct_terms:
        result = assess(
            ProfileData(ingredient_exclusions=[exclusion]),
            food(ingredients_text=ingredient),
        )
        assert not any(x["kind"] == "ingredient_exclusion" for x in result["conflicts"]), (
            exclusion,
            ingredient,
        )


def test_unqualified_wheat_flour_does_not_match_maida_exclusion_and_stays_uncertain():
    result = assess(
        ProfileData(ingredient_exclusions=["maida"]),
        food(ingredients_text="Wheat flour"),
    )
    assert not any(x["kind"] == "ingredient_exclusion" for x in result["conflicts"])
    assert any(x["field"] == "ingredient_interpretation" for x in result["unresolved"])
    assert (
        next(
            item for item in result["ingredient_findings"] if item["raw_evidence"] == "Wheat flour"
        )["subtype"]
        == "wheat_flour_unspecified"
    )
