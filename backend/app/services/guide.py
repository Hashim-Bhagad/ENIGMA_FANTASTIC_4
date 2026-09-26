from app.schemas import ProfileData

PACKS = {
    "diabetes": {
        "message": "Review total carbohydrate and portion, including starch. No universal per-product carbohydrate cutoff is activated.",
        "source": "https://www.cdc.gov/diabetes/healthy-eating/carb-counting-manage-blood-sugar.html",
    },
    "hypertension": {
        "message": "Review sodium and your recorded personal limits. A daily target is not automatically a per-product cutoff.",
        "source": "https://www.who.int/news-room/fact-sheets/detail/salt-reduction",
    },
    "ckd": {
        "message": "Kidney-related sodium, potassium, phosphorus, and protein needs vary. Record the restrictions supplied for your circumstances.",
        "source": "https://www.niddk.nih.gov/health-information/kidney-disease/chronic-kidney-disease-ckd/healthy-eating-adults-chronic-kidney-disease",
    },
}


def make_guide(profile: ProfileData):
    return {
        "exclusions": profile.allergies + profile.ingredient_exclusions,
        "recorded_limits": [x.model_dump() for x in profile.limits],
        "comparison_goals": [x.model_dump() for x in profile.goals],
        "condition_information": [
            {"condition": x, **PACKS[x.casefold()]}
            for x in profile.conditions
            if x.casefold() in PACKS
        ],
        "unsupported_conditions": [x for x in profile.conditions if x.casefold() not in PACKS],
        "questions": [
            "Is this the complete ingredient declaration?",
            "Are precautionary allergen statements visible?",
            "Do the nutrient units and portion match this pack?",
        ],
        "coverage": "Prototype awareness content; a selected condition does not activate a complete clinical diet.",
    }
