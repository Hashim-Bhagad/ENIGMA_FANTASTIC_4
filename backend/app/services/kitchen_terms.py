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

import re
import unicodedata
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
    "black cardamom": "G021",
    "asafoetida powder": "G019",
    # Spices, aromatics and produce that IFCT files under another name
    "capsicum": "D033",
    "bell pepper": "D033",
    "shimla mirch": "D033",
    "garlic": "G011",
    "lehsun": "G011",
    "ginger": "G014",
    "adrak": "G014",
    "lemon": "E033",
    "nimbu": "E033",
    "black pepper": "G031",
    "kali mirch": "G031",
    "pepper": "G031",
    "cloves": "G023",
    "laung": "G023",
    "cardamom": "G021",
    "elaichi": "G021",
    "green cardamom": "G020",
    "dhania seeds": "G024",
    "bay leaf": "G022",
    "tej patta": "G022",
    "cinnamon": "G027",
    "dalchini": "G027",
    "mango powder": "D057",
    "amchur": "D057",
    "dry mango powder": "D057",
    "potatoes": "F006",
    "tomatoes": "D075",
    "onions": "G017",
    "carrots": "F002",
    "green peas": "D061",
    "mint": "G012",
}


def _fold(text: str) -> str:
    """NFKC + casefold + punctuation folding, local to this module (no import cycle)."""
    value = unicodedata.normalize("NFKC", text).casefold()
    value = "".join(ch if ch.isalnum() or ch.isspace() else " " for ch in value)
    return " ".join(value.split())


# --- Recipe phrasing -----------------------------------------------------------------------
# A recipe line is not an ingredient name: it carries a quantity, a unit, preparation words and
# parenthetical asides ("10 medium boiled and peeled potatoes", "1 1/2 cup green peas"). The
# resolver works on the core phrase so the reference table can actually be reached, and the
# typed wording is kept in the result either way.

_QUANTITY = re.compile(
    r"^\s*(?:"
    r"[0-9]+\s*[\u2044/]\s*[0-9]+|"  # 1/2
    r"[0-9]+\s*[-–]\s*[0-9]+|"  # 4-5
    r"[0-9]+(?:\.[0-9]+)?|"  # 3, 1.5
    r"[\u00bc-\u00be\u2150-\u215e]|"  # ¼ ½ ¾
    r"(?:a|an|some|few|half)\b"
    r")+\s*",
    re.IGNORECASE,
)

_UNITS = (
    "cups",
    "cup",
    "teaspoons",
    "teaspoon",
    "tsps",
    "tsp",
    "tablespoons",
    "tablespoon",
    "tbsps",
    "tbsp",
    "grams",
    "gram",
    "gms",
    "gm",
    "g",
    "kgs",
    "kg",
    "mg",
    "ml",
    "l",
    "litre",
    "liter",
    "millilitres",
    "milliliters",
    "inch",
    "inches",
    "pinch",
    "pinches",
    "handful",
    "handfuls",
    "cloves",
    "clove",
    "pods",
    "pod",
    "sprigs",
    "sprig",
    "pieces",
    "piece",
    "slices",
    "slice",
    "medium",
    "large",
    "small",
    "big",
    "sized",
    "size",
    "no",
    "nos",
)

_PREP = (
    "boiled",
    "peeled",
    "chopped",
    "sliced",
    "grated",
    "crushed",
    "minced",
    "diced",
    "cut",
    "fresh",
    "freshly",
    "dried",
    "dry",
    "soft",
    "roasted",
    "fried",
    "ground",
    "whole",
    "washed",
    "cleaned",
    "trimmed",
    "halved",
    "quartered",
    "beaten",
    "melted",
    "softened",
    "optional",
    "as",
    "needed",
    "required",
    "available",
    "taste",
    "plus",
    "much",
    "you",
    "want",
    "to",
    "put",
    "on",
    "and",
    "or",
    "if",
    "any",
    "except",
    "others",
    "that",
    "have",
    "strong",
    "flavour",
    "flavor",
    "preferred",
    "preferably",
    "i",
    "use",
    "using",
    "also",
    "called",
    "very",
    "thinly",
    "finely",
    "roughly",
    "lightly",
)

# A trailing form word ("turmeric powder", "cauliflower florets") can be dropped when the head
# word resolves, because the form does not change which food it is. "seeds" and "leaves" are
# deliberately absent: coriander seeds and coriander leaves are different foods.
_DROP_TAIL = ("powder", "florets", "puree", "extract", "juice")

# A blend hides its own ingredients, so it is never treated as one food.
BLEND_TERMS = (
    "masala",
    "spice mix",
    "spices mix",
    "mixed spices",
    "mixed herbs",
    "seasoning",
    "seasoning mix",
    "flavouring",
    "flavoring",
    "sauce",
    "chutney",
    "pickle",
    "paste",
    "batter",
    "mix",
)


def core_phrase(text: str) -> str:
    """The core ingredient wording: quantity, units, preparation words and asides removed."""
    value = unicodedata.normalize("NFKC", text).casefold()
    value = re.sub(r"\([^)]*\)", " ", value)  # "(or 1/2 teaspoon ginger powder)"
    value = value.split(" or ")[0]
    value = value.replace(",", " ")
    for _ in range(3):  # "1 1/2 cup" and "4 -5" are more than one numeric token
        stripped = _QUANTITY.sub(" ", value)
        if stripped == value:
            break
        value = stripped
    words = []
    for word in value.split():
        cleaned = word.strip("-–")
        if not cleaned or cleaned in _UNITS or cleaned in _PREP:
            continue
        words.append(cleaned)
    phrase = " ".join(words).strip()
    return phrase or _fold(text)


def is_blend(text: str) -> bool:
    """True when the wording names a blend or a prepared mixture rather than one food."""
    value = _fold(text)
    return any(term in value for term in BLEND_TERMS)


def head_phrase(phrase: str) -> str | None:
    """The phrase with a trailing form word removed, when one is present."""
    words = phrase.split()
    if len(words) > 1 and words[-1] in _DROP_TAIL:
        return " ".join(words[:-1])
    return None


def singular_forms(phrase: str) -> list[str]:
    """The phrase plus a simple singular of each word, longest (most specific) first."""
    forms = [phrase]
    words = phrase.split()
    if len(words) == 1 and len(phrase) > 3 and phrase.endswith("es"):
        forms.append(phrase[:-2])
    if len(words) == 1 and len(phrase) > 3 and phrase.endswith("s"):
        forms.append(phrase[:-1])
    for index, word in enumerate(words):
        if len(word) > 3 and word.endswith("es"):
            forms.append(" ".join([*words[:index], word[:-2], *words[index + 1 :]]))
        elif len(word) > 3 and word.endswith("s"):
            forms.append(" ".join([*words[:index], word[:-1], *words[index + 1 :]]))
    return list(dict.fromkeys(forms))


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
