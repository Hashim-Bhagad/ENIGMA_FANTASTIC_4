"""Conservative ingredient-name recognition with auditable source spans.

This is a terminology matcher, not a nutrition calculator or medical equivalence
table. Keep alias updates versioned because they can change assessment output.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

TAXONOMY_VERSION = "ingredient-terms-2026-09-26.5"


@dataclass(frozen=True)
class Term:
    alias: str
    canonical_group: str
    subtype: str
    canonical_identity: str
    wheat_allergen: bool = False
    # An umbrella alias names the whole subtype (e.g. "sugar alcohol") rather than one
    # member, so a user exclusion of it also covers the members of that subtype.
    umbrella: bool = False


def _terms(
    group: str,
    subtype: str,
    aliases: tuple[str, ...],
    *,
    wheat=False,
    identities: dict[str, str] | None = None,
    umbrella: tuple[str, ...] = (),
):
    identities = identities or {}
    return tuple(
        Term(
            x,
            group,
            subtype,
            identities.get(x, f"alias:{x.casefold()}"),
            wheat,
            x in umbrella,
        )
        for x in aliases
    )


# Entries are deliberately specific. In particular, an alias for a flour type
# never claims that its carbohydrate amount or clinical effect is equivalent.
TERMS = (
    *_terms(
        "flour",
        "refined_wheat_flour",
        (
            "all-purpose flour",
            "all purpose flour",
            "plain flour",
            "maida",
            "refined flour",
            "refined wheat flour",
            "white wheat flour",
            "white flour",
            "bread flour",
            "pastry flour",
            "cake flour",
            "wheat maida",
        ),
        wheat=True,
        identities={
            "all-purpose flour": "refined_wheat_flour",
            "all purpose flour": "refined_wheat_flour",
            "plain flour": "refined_wheat_flour",
            "maida": "refined_wheat_flour",
            "refined flour": "refined_wheat_flour",
            "refined wheat flour": "refined_wheat_flour",
            "white wheat flour": "refined_wheat_flour",
            "white flour": "refined_wheat_flour",
            "wheat maida": "refined_wheat_flour",
        },
    ),
    *_terms(
        "flour",
        "whole_wheat_flour",
        (
            "whole wheat flour",
            "whole-wheat flour",
            "wholemeal flour",
            "wholemeal wheat flour",
            "atta",
            "chakki atta",
            "whole wheat atta",
            "whole-wheat atta",
            "whole grain wheat flour",
            "whole-grain wheat flour",
        ),
        wheat=True,
        identities={
            "whole wheat flour": "whole_wheat_flour",
            "whole-wheat flour": "whole_wheat_flour",
            "wholemeal flour": "whole_wheat_flour",
            "wholemeal wheat flour": "whole_wheat_flour",
            "atta": "whole_wheat_flour",
            "chakki atta": "whole_wheat_flour",
            "whole wheat atta": "whole_wheat_flour",
            "whole-wheat atta": "whole_wheat_flour",
            "whole grain wheat flour": "whole_wheat_flour",
            "whole-grain wheat flour": "whole_wheat_flour",
        },
    ),
    *_terms("wheat_ingredients", "wheat_flour_unspecified", ("wheat flour",), wheat=True),
    *_terms(
        "wheat_ingredients",
        "wheat_ingredient_unspecified_form",
        (
            "wheat",
            "durum",
            "semolina",
            "suji",
            "sooji",
            "bulgur",
            "seitan",
            "vital wheat gluten",
            "wheat gluten",
        ),
        wheat=True,
    ),
    *_terms(
        "flour",
        "other_flour",
        (
            "rice flour",
            "rice semolina",
            "chickpea flour",
            "gram flour",
            "besan",
            "corn flour",
            "corn semolina",
            "maize flour",
            "maize semolina",
            "oat flour",
            "almond flour",
            "millet flour",
            "ragi flour",
            "sorghum flour",
            "jowar flour",
            "buckwheat flour",
            "tapioca flour",
            "potato flour",
            "cassava flour",
            "coconut flour",
        ),
        identities={
            "chickpea flour": "chickpea_flour",
            "gram flour": "chickpea_flour",
            "besan": "chickpea_flour",
        },
    ),
    *_terms(
        "sugars",
        "broad_sugar_term",
        ("sugar",),
    ),
    *_terms(
        "sugars",
        "sucrose",
        (
            "table sugar",
            "sucrose",
            "cane sugar",
            "raw cane sugar",
            "raw sugar",
            "white sugar",
            "brown sugar",
            "demerara sugar",
            "demerara",
            "turbinado sugar",
            "turbinado",
            "muscovado sugar",
            "muscovado",
            "sucanat",
            "granulated sugar",
            "caster sugar",
            "confectioners sugar",
            "confectioner's sugar",
            "powdered sugar",
            "icing sugar",
            "coconut sugar",
            "palm sugar",
            "date sugar",
            "beet sugar",
        ),
        identities={
            "table sugar": "sucrose",
            "sucrose": "sucrose",
            "cane sugar": "sucrose",
            "raw cane sugar": "sucrose",
            "raw sugar": "sucrose",
            "white sugar": "sucrose",
            "granulated sugar": "sucrose",
            "caster sugar": "sucrose",
            "confectioners sugar": "sucrose",
            "confectioner's sugar": "sucrose",
            "powdered sugar": "sucrose",
            "icing sugar": "sucrose",
            "demerara sugar": "demerara_sugar",
            "demerara": "demerara_sugar",
            "turbinado sugar": "turbinado_sugar",
            "turbinado": "turbinado_sugar",
            "muscovado sugar": "muscovado_sugar",
            "muscovado": "muscovado_sugar",
        },
    ),
    *_terms(
        "sugars",
        "glucose",
        ("glucose", "dextrose", "corn sugar"),
        identities={"glucose": "glucose", "dextrose": "glucose", "corn sugar": "glucose"},
    ),
    *_terms(
        "sugars",
        "fructose",
        ("fructose", "levulose", "fruit sugar"),
        identities={"fructose": "fructose", "levulose": "fructose", "fruit sugar": "fructose"},
    ),
    *_terms("sugars", "maltose", ("maltose",)),
    *_terms("sugars", "lactose", ("lactose",)),
    *_terms("sugars", "galactose", ("galactose",)),
    *_terms("sugars", "trehalose", ("trehalose",)),
    *_terms(
        "sugars",
        "sugar_product",
        ("jaggery", "khandsari", "shakkar", "misri", "boora", "gur", "panela", "piloncillo"),
    ),
    *_terms("sugars", "invert_sugar", ("invert sugar",)),
    *_terms(
        "sugars",
        "mixed_sugar_syrup",
        (
            "invert sugar syrup",
            "high fructose corn syrup",
            "high-fructose corn syrup",
            "glucose-fructose syrup",
            "fructose-glucose syrup",
        ),
    ),
    *_terms("sugars", "glucose_syrup", ("glucose syrup",)),
    *_terms("sugars", "corn_syrup", ("corn syrup",)),
    *_terms(
        "sugars",
        "rice_syrup",
        ("rice syrup", "brown rice syrup"),
        identities={"rice syrup": "rice_syrup", "brown rice syrup": "rice_syrup"},
    ),
    *_terms(
        "sugars",
        "malt_syrup",
        ("malt syrup", "barley malt syrup"),
        identities={"malt syrup": "malt_syrup", "barley malt syrup": "malt_syrup"},
    ),
    *_terms(
        "sugars",
        "plant_syrup",
        ("agave syrup", "maple syrup", "date syrup", "golden syrup", "cane syrup", "sorghum syrup"),
    ),
    *_terms(
        "sugars",
        "sweetener_source",
        (
            "barley malt extract",
            "malt extract",
            "sugarcane juice",
            "cane juice",
            "cane juice crystals",
            "evaporated cane juice",
            "fruit juice concentrate",
            "molasses",
            "honey",
        ),
        identities={"malt extract": "malt_extract", "barley malt extract": "malt_extract"},
    ),
    *_terms("carbohydrate_ingredients", "maltodextrin", ("maltodextrin",)),
    *_terms(
        "sweeteners",
        "polyol",
        (
            "sugar alcohol",
            "sugar alcohols",
            "polyol",
            "polyols",
            "sorbitol",
            "mannitol",
            "xylitol",
            "maltitol",
            "erythritol",
            "isomalt",
            "lactitol",
            "glycerol",
            "glycerin",
            "hydrogenated starch hydrolysate",
            "hydrogenated starch hydrolysates",
            "polyglycitol syrup",
        ),
        umbrella=("sugar alcohol", "sugar alcohols", "polyol", "polyols"),
    ),
    *_terms(
        "sweeteners",
        "non_nutritive_sweetener",
        (
            "non-nutritive sweetener",
            "non nutritive sweetener",
            "artificial sweetener",
            "aspartame",
            "sucralose",
            "saccharin",
            "acesulfame potassium",
            "acesulfame-k",
            "acesulfame k",
            "steviol glycosides",
            "stevia extract",
            "stevia",
            "thaumatin",
            "neotame",
            "advantame",
            "monk fruit extract",
            "luo han guo",
            "cyclamate",
        ),
        identities={
            "stevia extract": "stevia",
            "stevia": "stevia",
            "steviol glycosides": "stevia",
            "monk fruit extract": "monk_fruit",
            "luo han guo": "monk_fruit",
        },
    ),
)


def _normalize_with_offsets(text: str) -> tuple[str, list[tuple[int, int]]]:
    """NFKC/casefold text while keeping each normalized char's source span."""
    chars: list[str] = []
    spans: list[tuple[int, int]] = []
    for index, original in enumerate(text):
        value = unicodedata.normalize("NFKC", original).casefold()
        for char in value:
            # Normalize compatibility forms but retain hyphens as word boundaries.
            if char.isspace():
                char = " "
            elif char in "‐‑‒–—−":
                char = "-"
            elif char in "‘’‛＇":
                char = "'"
            chars.append(char)
            spans.append((index, index + 1))
    normalized: list[str] = []
    normalized_spans: list[tuple[int, int]] = []
    pending_space: tuple[int, int] | None = None
    for char, span in zip(chars, spans, strict=True):
        if char == " ":
            if normalized:
                pending_space = (pending_space[0], span[1]) if pending_space else span
            continue
        if pending_space:
            normalized.append(" ")
            normalized_spans.append(pending_space)
            pending_space = None
        normalized.append(char)
        normalized_spans.append(span)
    return "".join(normalized), normalized_spans


def _alias_pattern(alias: str) -> re.Pattern[str]:
    normalized, _ = _normalize_with_offsets(alias)
    return re.compile(r"(?<![\w-])" + re.escape(normalized) + r"(?![\w-])")


_PATTERNS = tuple(
    sorted(
        ((term, _alias_pattern(term.alias)) for term in TERMS),
        key=lambda item: len(item[0].alias),
        reverse=True,
    )
)


def is_negated(text: str, start: int, end: int) -> bool:
    """Ignore explicit absence/marketing claims around a term; retain may-contain."""
    prefix = text[max(0, start - 40) : start]
    suffix = text[end : min(len(text), end + 16)]
    return bool(
        re.search(
            r"(?:\bno(?:\s+added)?|\bnot(?:\s+added)?|\bnot\s+(?:made\s+with|containing|contain)|"
            r"\bdoes\s+not\s+(?:contain|include)|\bdid\s+not\s+contain|\bwithout|"
            r"\bfree\s+(?:from|of))\s+$",
            prefix,
            re.I,
        )
        or re.match(r"\s+(?:-\s*)?free\b", suffix, re.I)
    )


def normalized_view(text: str) -> tuple[str, list[tuple[int, int]]]:
    """Normalized text plus each character's source span.

    Every matcher (ingredient names, allergens, exclusions) must search the same
    normalized view; otherwise a declaration that differs only by compatibility
    forms, non-breaking spaces or dash variants is recognized for one check and
    missed for another.
    """
    return _normalize_with_offsets(text)


def match_ingredients(text: str | None) -> list[dict]:
    """Return longest non-overlapping known phrases, including raw evidence spans."""
    if not text:
        return []
    normalized, offsets = _normalize_with_offsets(text)
    occupied: list[tuple[int, int]] = []
    matches: list[dict] = []
    for term, pattern in _PATTERNS:
        for found in pattern.finditer(normalized):
            start, end = found.span()
            if any(start < used_end and end > used_start for used_start, used_end in occupied):
                continue
            occupied.append((start, end))
            source_start = offsets[start][0]
            source_end = offsets[end - 1][1]
            if is_negated(text, source_start, source_end):
                continue
            matches.append(
                {
                    "canonical_group": term.canonical_group,
                    "subtype": term.subtype,
                    "canonical_identity": term.canonical_identity,
                    "matched_term": term.alias,
                    "raw_evidence": text[source_start:source_end],
                    "start": source_start,
                    "end": source_end,
                    "wheat_allergen": term.wheat_allergen,
                    "umbrella": term.umbrella,
                }
            )
    matches.sort(key=lambda item: (item["start"], item["end"]))
    return matches


_BROAD_OR_UNCLEAR = (
    ("flour", re.compile(r"(?<![\w-])(?:multigrain flour|flour)(?![\w-])")),
    ("sweetener", re.compile(r"(?<![\w-])(?:sweetener|syrup)(?![\w-])")),
)


def ambiguous_ingredient_mentions(
    text: str | None, matches: list[dict] | None = None
) -> list[dict]:
    """Find broad terms that do not identify a specific source/type."""
    if not text:
        return []
    matches = matches if matches is not None else match_ingredients(text)
    normalized, offsets = _normalize_with_offsets(text)
    found_terms: list[dict] = []
    for item in matches:
        if item["subtype"] == "wheat_flour_unspecified":
            found_terms.append(
                {
                    "canonical_group": "flour_refinement",
                    "matched_term": "wheat flour",
                    "raw_evidence": item["raw_evidence"],
                    "start": item["start"],
                    "end": item["end"],
                }
            )
    for label, pattern in _BROAD_OR_UNCLEAR:
        for found in pattern.finditer(normalized):
            start, end = found.span()
            source_start = offsets[start][0]
            source_end = offsets[end - 1][1]
            if is_negated(text, source_start, source_end):
                continue
            if any(source_start < item["end"] and source_end > item["start"] for item in matches):
                continue
            found_terms.append(
                {
                    "canonical_group": label,
                    "matched_term": label,
                    "raw_evidence": text[source_start:source_end],
                    "start": source_start,
                    "end": source_end,
                }
            )
    return found_terms
