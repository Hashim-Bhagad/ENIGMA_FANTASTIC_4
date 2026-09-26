"""Small reviewed catalog of ingredient swaps, filtered by recorded allergens."""

CATALOG = [
    {"ingredient": "wheat flour", "alternatives": ["certified gluten-free rice flour", "certified gluten-free oat flour"], "avoid": ["wheat"], "reason": "A naturally gluten-free flour option; verify the package for cross-contact and other allergens."},
    {"ingredient": "flour", "alternatives": ["rice flour", "chickpea flour"], "avoid": ["wheat"], "reason": "Useful alternatives for some recipes; texture and binding may change."},
    {"ingredient": "milk", "alternatives": ["unsweetened oat drink", "unsweetened rice drink"], "avoid": ["milk"], "reason": "Dairy-free options for some recipes; check fortification, sugar, and cross-contact on the label."},
    {"ingredient": "butter", "alternatives": ["olive oil", "allergen-checked dairy-free spread"], "avoid": ["milk"], "reason": "Can replace butter in some cooking; baking ratios vary. Check the full label."},
    {"ingredient": "egg", "alternatives": ["flaxseed gel", "unsweetened applesauce"], "avoid": ["eggs"], "reason": "May work as a binder in selected recipes; not suitable for every dish."},
    {"ingredient": "soy sauce", "alternatives": ["coconut aminos", "salt-reduced verified soy-free seasoning"], "avoid": ["soy"], "reason": "Check every ingredient and sodium content; products vary."},
    {"ingredient": "peanut", "alternatives": ["sunflower seed butter", "pumpkin seed butter"], "avoid": ["peanuts", "tree_nuts"], "reason": "Only consider if the person's clinician permits seeds and the facility/cross-contact is acceptable."},
    {"ingredient": "sesame", "alternatives": ["olive oil", "sunflower seed butter"], "avoid": ["sesame"], "reason": "A recipe-dependent flavor or fat replacement; verify seed cross-contact and the full label."},
    {"ingredient": "sweetener", "alternatives": ["unsweetened fruit puree", "date paste"], "avoid": [], "reason": "Recipe-dependent options; these still contain sugars and are not a low-sugar guarantee."},
    {"ingredient": "syrup", "alternatives": ["unsweetened fruit puree", "date paste"], "avoid": [], "reason": "Recipe-dependent options; these still contain sugars and are not a low-sugar guarantee."},
    {"ingredient": "sauce", "alternatives": ["omit the sauce", "serve it separately only after its full label is checked"], "avoid": [], "reason": "A vague sauce name does not identify ingredients. These steps avoid guessing its source."},
    {"ingredient": "seasoning", "alternatives": ["omit the seasoning blend", "use individually named spices after checking each one"], "avoid": [], "reason": "Blend ingredients vary; check the full declaration and cross-contact."},
    {"ingredient": "flavouring", "alternatives": ["omit the flavouring", "ask the manufacturer for its source before choosing a replacement"], "avoid": [], "reason": "The source is unspecified, so no ingredient-level substitute can be confirmed."},
]


def suggest_alternatives(ingredients: list[str], allergies: list[str]) -> list[dict]:
    allergy_set = set(allergies)
    output = []
    for ingredient in ingredients:
        normalized = ingredient.casefold().strip()
        for item in CATALOG:
            if item["ingredient"] in normalized or normalized in item["ingredient"]:
                output.append({**item, "matched_ingredient": ingredient,
                               "profile_allergies_considered": sorted(allergy_set),
                               "review_required": True})
                break
    return output
