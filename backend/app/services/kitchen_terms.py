"""Everyday kitchen wording resolved to a composition source.

Two tables, both deterministic and auditable:

``ALIASES`` maps the words people type (including Indian-English and transliterated names) to
an **IFCT row for the same food** — ``poha`` is ``A011 Rice, flakes``, not an approximation.

``STAPLES`` covers what IFCT simply does not carry (salt, sugar, butter, cream, generic oil).
Those values come from standard composition references, not IFCT, so every staple row states
its source and the dish result says staples were used. Nothing here is invented, and a term
missing from both tables stays unmatched rather than being guessed at.
"""

from __future__ import annotations

from dataclasses import dataclass

KITCHEN_TERMS_VERSION = "kitchen-terms-2026-09-26.1"

STAPLE_SOURCE = "Standard composition reference (USDA FoodData Central / public nutrition tables)"


@dataclass(frozen=True)
class Staple:
    name: str
    nutrients: dict[str, float]
    source: str = STAPLE_SOURCE
    basis: str = "100g"


# Same food, different name. Only true synonyms belong here: mapping "besan" onto a dal row
# would change the water and carbohydrate picture, so it is deliberately absent.
ALIASES: dict[str, str] = {
    # Rice products
    "poha": "A011",
    "flattened rice": "A011",
    "beaten rice": "A011",
    "aval": "A011",
    "chivda base": "A011",
    "murmura": "A012",
    "puffed rice": "A012",
    "kurmura": "A012",
    "mandakki": "A012",
    "rice": "A015",
    "raw rice": "A015",
    "boiled rice": "A014",
    "parboiled rice": "A014",
    "brown rice": "A013",
    # Wheat products
    "atta": "A019",
    "whole wheat flour": "A019",
    "wheat flour": "A019",
    "gehu atta": "A019",
    "maida": "A018",
    "refined wheat flour": "A018",
    "all purpose flour": "A018",
    "plain flour": "A018",
    "rava": "A022",
    "sooji": "A022",
    "sooji rava": "A022",
    "semolina": "A022",
    "dalia": "A021",
    "broken wheat": "A021",
    "bulgur": "A021",
    "vermicelli": "A023",
    "sevai": "A023",
    # Pulses
    "chana dal": "B001",
    "bengal gram dal": "B001",
    "chickpea dal": "B001",
    "kabuli chana": "B002",
    "chole": "B002",
    "chickpeas": "B002",
    "moong dal": "B010",
    "green gram dal": "B010",
    "sabut moong": "B011",
    "whole moong": "B011",
    "masoor dal": "B013",
    "red lentil": "B013",
    "masoor": "B014",
    "toor dal": "B021",
    "arhar dal": "B021",
    "pigeon pea": "B021",
    "peanuts": "H012",
    "peanut": "H012",
    "groundnut": "H012",
    "groundnuts": "H012",
    "moongfali": "H012",
    "shengdana": "H012",
    "sesame": "H011",
    "sesame seeds": "H011",
    "til": "H011",
    "gingelly": "H011",
    # Vegetables and aromatics
    "onion": "G017",
    "pyaz": "G017",
    "tomato": "D075",
    "tamatar": "D075",
    "potato": "F006",
    "aloo": "F006",
    "green chilli": "G001",
    "green chillies": "G001",
    "hari mirch": "G001",
    "chilli": "G001",
    "chillies": "G001",
    "cauliflower": "D036",
    "gobi": "D036",
    "peas": "D061",
    "matar": "D061",
    "carrot": "F002",
    "gajar": "F002",
    "curry leaves": "G010",
    "kadi patta": "G010",
    "coriander leaves": "G009",
    "coriander": "G009",
    "dhania": "G009",
    "coriander seeds": "G024",
    "cumin seeds": "G025",
    "cumin": "G025",
    "jeera": "G025",
    "turmeric": "G033",
    "haldi": "G033",
    "turmeric powder": "G033",
    "mustard seeds": "H013",
    "rai": "H013",
    "sarson": "H013",
    "fenugreek leaves": "C020",
    "methi": "C020",
    "fenugreek seeds": "G026",
    "methi dana": "G026",
    "asafoetida": "G019",
    "hing": "G019",
    "coconut": "H007",
    "nariyal": "H007",
    "dry coconut": "H006",
    "tamarind": "E064",
    "imli": "E064",
    "cashew nuts": "H005",
    "cashews": "H005",
    "kaju": "H005",
    "raisins": "E057",
    "kishmish": "E057",
    "jaggery": "I001",
    "gur": "I001",
    "ghee": "T013",
    "paneer": "L003",
    "milk": "L002",
    "curd": "L002",
    "dahi": "L002",
    "yogurt": "L002",
    "yoghurt": "L002",
    "egg": "M008",
    "eggs": "M008",
    "soya bean": "B024",
    "soybean": "B024",
    "sunflower oil": "T012",
    "coconut oil": "T001",
    "mustard oil": "T006",
    "groundnut oil": "T005",
}

# Per 100 g, from standard tables. Used only where IFCT has no row at all. The values are
# complete on purpose: a missing entry would make the whole dish's nutrient "unknown" even when
# the missing amount is genuinely nil (sugar carries no fat, oil carries no sodium).
STAPLES: dict[str, Staple] = {
    "salt": Staple(
        "Salt",
        {
            "sodium_mg": 38758.0,
            "potassium_mg": 8.0,
            "phosphorus_mg": 0.0,
            "carbohydrates_g": 0.0,
            "protein_g": 0.0,
            "fat_g": 0.0,
            "saturated_fat_g": 0.0,
            "sugars_g": 0.0,
            "fiber_g": 0.0,
            "energy_kcal": 0.0,
        },
    ),
    "sugar": Staple(
        "Sugar",
        {
            "sodium_mg": 1.0,
            "potassium_mg": 2.0,
            "phosphorus_mg": 0.0,
            "carbohydrates_g": 99.9,
            "protein_g": 0.0,
            "fat_g": 0.0,
            "saturated_fat_g": 0.0,
            "sugars_g": 99.9,
            "fiber_g": 0.0,
            "energy_kcal": 387.0,
        },
    ),
    "oil": Staple(
        "Cooking oil",
        {
            "sodium_mg": 0.0,
            "potassium_mg": 0.0,
            "phosphorus_mg": 0.0,
            "carbohydrates_g": 0.0,
            "protein_g": 0.0,
            "fat_g": 100.0,
            "saturated_fat_g": 15.0,
            "sugars_g": 0.0,
            "fiber_g": 0.0,
            "energy_kcal": 884.0,
        },
    ),
    "butter": Staple(
        "Butter",
        {
            "sodium_mg": 11.0,
            "potassium_mg": 24.0,
            "phosphorus_mg": 24.0,
            "carbohydrates_g": 0.1,
            "protein_g": 0.9,
            "fat_g": 81.0,
            "saturated_fat_g": 51.0,
            "sugars_g": 0.1,
            "fiber_g": 0.0,
            "energy_kcal": 717.0,
        },
    ),
    "cream": Staple(
        "Cream",
        {
            "sodium_mg": 38.0,
            "potassium_mg": 95.0,
            "phosphorus_mg": 60.0,
            "carbohydrates_g": 3.5,
            "protein_g": 2.5,
            "fat_g": 30.0,
            "saturated_fat_g": 19.0,
            "sugars_g": 3.5,
            "fiber_g": 0.0,
            "energy_kcal": 200.0,
        },
    ),
}

# Every typed wording that should reach a staple row above.
STAPLE_TERMS: dict[str, str] = {
    "salt": "salt",
    "table salt": "salt",
    "namak": "salt",
    "sendha namak": "salt",
    "sugar": "sugar",
    "cheeni": "sugar",
    "chini": "sugar",
    "white sugar": "sugar",
    "refined sugar": "sugar",
    "oil": "oil",
    "cooking oil": "oil",
    "tel": "oil",
    "vegetable oil": "oil",
    "refined oil": "oil",
    "sunflower oil": "oil",
    "neutral oil": "oil",
    "butter": "butter",
    "makhan": "butter",
    "salted butter": "butter",
    "cream": "cream",
    "malai": "cream",
    "fresh cream": "cream",
}
