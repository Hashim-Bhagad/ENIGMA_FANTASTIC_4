"""Deterministic laboratory-parameter registry and maths for uploaded health reports.

The extraction model only *reads* a document; every unit conversion, plausibility
check, reference-range choice and classification happens here in code so a value
can always be recomputed and audited. The canonical ``key`` vocabulary is the
shared contract between the report pipeline and the intake rules.

Reference intervals are starting points drawn from the linked public sources, not
diagnostic thresholds. A value is compared with the range printed on the document
first and only falls back to the ranges below when the document prints none.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.schemas import AgeBand, LabParameter, Sex

LAB_REGISTRY_VERSION = "1.0.0"

# Exactly the frozen canonical vocabulary, in contract order.
CANONICAL_KEYS = (
    "hemoglobin_g_dl",
    "rbc_million_ul",
    "wbc_thousand_ul",
    "platelet_thousand_ul",
    "mcv_fl",
    "ferritin_ng_ml",
    "fasting_glucose_mg_dl",
    "random_glucose_mg_dl",
    "hba1c_percent",
    "total_cholesterol_mg_dl",
    "ldl_cholesterol_mg_dl",
    "hdl_cholesterol_mg_dl",
    "triglycerides_mg_dl",
    "tsh_miu_l",
    "t3_ng_dl",
    "t4_ug_dl",
    "creatinine_mg_dl",
    "egfr_ml_min",
    "urea_mg_dl",
    "uric_acid_mg_dl",
    "sodium_meq_l",
    "potassium_meq_l",
    "phosphorus_mg_dl",
    "calcium_mg_dl",
    "alt_u_l",
    "ast_u_l",
    "bilirubin_total_mg_dl",
    "albumin_g_dl",
    "alp_u_l",
    "vitamin_d_ng_ml",
    "vitamin_b12_pg_ml",
    "folate_ng_ml",
    "crp_mg_l",
    "systolic_bp_mmhg",
    "diastolic_bp_mmhg",
    "weight_kg",
    "height_cm",
    "bmi",
)

# Each entry: label, canonical unit, printed aliases (Indian lab forms included),
# plausible physical bounds, default reference ranges keyed by sex/age selector,
# a public source URL, and the intake slugs this value can inform.
#
# Range selector lookup order (most specific first): "<sex>:<age_band>", "<sex>",
# "unspecified:<age_band>", "<age_band>", "default". A missing side of a range is
# ``None``: a ``low``-only range never classifies high and vice versa.
LAB_REGISTRY: dict[str, dict[str, Any]] = {
    "hemoglobin_g_dl": {
        "label": "Haemoglobin",
        "unit": "g/dL",
        "aliases": [
            "hb",
            "hgb",
            "haemoglobin",
            "hemoglobin",
            "haemoglobin hb",
            "hemoglobin hb",
            "hb concentration",
            "blood haemoglobin",
            "total haemoglobin",
        ],
        "bounds": (2.0, 25.0),
        "ranges": {
            "default": (12.0, 16.0),
            "female": (12.0, 15.5),
            "male": (13.5, 17.5),
            "female:75_plus": (11.7, 15.0),
            "male:75_plus": (13.0, 17.0),
            "under_18": (11.5, 15.5),
        },
        "source": "https://medlineplus.gov/lab-tests/complete-blood-count-cbc/",
        "intake_links": ["iron", "vitamin_b12", "folate", "anaemia"],
    },
    "rbc_million_ul": {
        "label": "Red blood cell count",
        "unit": "million/uL",
        "aliases": ["rbc", "rbcs", "rbc count", "red blood cell count", "red blood cells", "erythrocytes"],
        "bounds": (1.0, 10.0),
        "ranges": {
            "default": (4.0, 6.0),
            "female": (4.1, 5.1),
            "male": (4.5, 5.9),
            "under_18": (4.0, 5.5),
            "75_plus": (3.8, 5.8),
        },
        "source": "https://medlineplus.gov/lab-tests/complete-blood-count-cbc/",
        "intake_links": ["iron", "vitamin_b12", "folate"],
    },
    "wbc_thousand_ul": {
        "label": "White blood cell count",
        "unit": "thousand/uL",
        "aliases": [
            "wbc",
            "wbcs",
            "wbc count",
            "white blood cell count",
            "white blood cells",
            "leucocytes",
            "leukocytes",
            "tlc",
            "total leucocyte count",
            "total leukocyte count",
        ],
        "bounds": (0.1, 100.0),
        "ranges": {"default": (4.0, 11.0)},
        "source": "https://medlineplus.gov/lab-tests/complete-blood-count-cbc/",
        "intake_links": ["inflammation"],
    },
    "platelet_thousand_ul": {
        "label": "Platelet count",
        "unit": "thousand/uL",
        "aliases": ["platelets", "plt", "platelet count", "platelet", "thrombocytes"],
        "bounds": (5.0, 1500.0),
        "ranges": {"default": (150.0, 450.0)},
        "source": "https://medlineplus.gov/lab-tests/complete-blood-count-cbc/",
        "intake_links": ["inflammation"],
    },
    "mcv_fl": {
        "label": "Mean corpuscular volume",
        "unit": "fL",
        "aliases": ["mcv", "mean corpuscular volume", "mean cell volume"],
        "bounds": (30.0, 150.0),
        "ranges": {"default": (80.0, 100.0), "under_18": (75.0, 95.0)},
        "source": "https://medlineplus.gov/lab-tests/complete-blood-count-cbc/",
        "intake_links": ["iron", "vitamin_b12", "folate"],
    },
    "ferritin_ng_ml": {
        "label": "Ferritin",
        "unit": "ng/mL",
        "aliases": ["ferritin", "serum ferritin", "s ferritin", "ferritin serum"],
        "bounds": (0.0, 5000.0),
        "ranges": {"default": (15.0, 400.0), "female": (15.0, 150.0), "male": (30.0, 400.0)},
        "source": "https://medlineplus.gov/lab-tests/ferritin-blood-test/",
        "intake_links": ["iron", "anaemia"],
    },
    "fasting_glucose_mg_dl": {
        "label": "Fasting blood glucose",
        "unit": "mg/dL",
        "aliases": [
            "fbs",
            "fasting blood sugar",
            "fasting blood glucose",
            "blood sugar fasting",
            "glucose fasting",
            "fasting glucose",
            "fasting plasma glucose",
            "fpg",
        ],
        "bounds": (20.0, 800.0),
        "ranges": {"default": (70.0, 100.0), "under_18": (70.0, 100.0)},
        "source": "https://diabetes.org/about-diabetes/diagnosis",
        "intake_links": ["carbohydrates", "added_sugar", "fiber", "diabetes"],
    },
    "random_glucose_mg_dl": {
        "label": "Random blood glucose",
        "unit": "mg/dL",
        "aliases": [
            "rbs",
            "random blood sugar",
            "random blood glucose",
            "blood sugar random",
            "random glucose",
            "postprandial blood sugar",
            "ppbs",
            "pp sugar",
        ],
        "bounds": (20.0, 1500.0),
        "ranges": {"default": (70.0, 140.0)},
        "source": "https://diabetes.org/about-diabetes/diagnosis",
        "intake_links": ["carbohydrates", "added_sugar", "fiber", "diabetes"],
    },
    "hba1c_percent": {
        "label": "HbA1c",
        "unit": "%",
        "aliases": ["hba1c", "hb a1c", "glycated haemoglobin", "glycated hemoglobin", "glycosylated hemoglobin", "a1c"],
        "bounds": (2.0, 25.0),
        "ranges": {"default": (4.0, 5.6)},
        "source": "https://www.cdc.gov/diabetes/diabetes-testing/prediabetes-a1c-test.html",
        "intake_links": ["carbohydrates", "added_sugar", "fiber", "diabetes"],
    },
    "total_cholesterol_mg_dl": {
        "label": "Total cholesterol",
        "unit": "mg/dL",
        "aliases": ["cholesterol", "cholesterol total", "total cholesterol", "serum cholesterol", "s cholesterol"],
        "bounds": (50.0, 800.0),
        "ranges": {"default": (0.0, 200.0)},
        "source": "https://www.cdc.gov/cholesterol/about/index.html",
        "intake_links": ["saturated_fat", "fiber", "cholesterol"],
    },
    "ldl_cholesterol_mg_dl": {
        "label": "LDL cholesterol",
        "unit": "mg/dL",
        "aliases": ["ldl", "ldl cholesterol", "ldl c", "ldl-c", "bad cholesterol", "ldl direct"],
        "bounds": (10.0, 600.0),
        "ranges": {"default": (0.0, 100.0)},
        "source": "https://www.cdc.gov/cholesterol/about/index.html",
        "intake_links": ["saturated_fat", "fiber", "cholesterol"],
    },
    "hdl_cholesterol_mg_dl": {
        "label": "HDL cholesterol",
        "unit": "mg/dL",
        "aliases": ["hdl", "hdl cholesterol", "hdl c", "hdl-c", "good cholesterol"],
        "bounds": (5.0, 150.0),
        "ranges": {"default": (40.0, None), "female": (50.0, None), "male": (40.0, None)},
        "source": "https://www.cdc.gov/cholesterol/about/index.html",
        "intake_links": ["saturated_fat", "fiber", "cholesterol"],
    },
    "triglycerides_mg_dl": {
        "label": "Triglycerides",
        "unit": "mg/dL",
        "aliases": ["triglycerides", "triglyceride", "tgl", "trig", "tg", "serum triglycerides"],
        "bounds": (10.0, 3000.0),
        "ranges": {"default": (0.0, 150.0)},
        "source": "https://www.cdc.gov/cholesterol/about/index.html",
        "intake_links": ["added_sugar", "saturated_fat", "alcohol"],
    },
    "tsh_miu_l": {
        "label": "Thyroid stimulating hormone",
        "unit": "mIU/L",
        "aliases": ["tsh", "thyroid stimulating hormone", "thyrotropin", "s tsh"],
        "bounds": (0.001, 200.0),
        "ranges": {"default": (0.4, 4.0), "under_18": (0.7, 6.4), "75_plus": (0.4, 5.9)},
        "source": "https://www.thyroid.org/thyroid-function-tests/",
        "intake_links": ["iodine", "selenium", "thyroid"],
    },
    "t3_ng_dl": {
        "label": "Triiodothyronine (T3)",
        "unit": "ng/dL",
        "aliases": ["t3", "triiodothyronine", "total t3", "serum t3"],
        "bounds": (10.0, 800.0),
        "ranges": {"default": (80.0, 200.0)},
        "source": "https://www.thyroid.org/thyroid-function-tests/",
        "intake_links": ["iodine", "selenium", "thyroid"],
    },
    "t4_ug_dl": {
        "label": "Thyroxine (T4)",
        "unit": "ug/dL",
        "aliases": ["t4", "thyroxine", "total t4", "serum t4"],
        "bounds": (0.1, 40.0),
        "ranges": {"default": (5.0, 12.0)},
        "source": "https://www.thyroid.org/thyroid-function-tests/",
        "intake_links": ["iodine", "selenium", "thyroid"],
    },
    "creatinine_mg_dl": {
        "label": "Creatinine",
        "unit": "mg/dL",
        "aliases": [
            "creatinine",
            "serum creatinine",
            "s creatinine",
            "s. creatinine",
            "creatinine serum",
            "blood creatinine",
        ],
        "bounds": (0.1, 30.0),
        "ranges": {"default": (0.6, 1.3), "female": (0.6, 1.1), "male": (0.7, 1.3)},
        "source": "https://www.kidney.org/kidney-topics/estimated-glomerular-filtration-rate-egfr",
        "intake_links": ["protein", "sodium", "potassium", "phosphorus", "ckd"],
    },
    "egfr_ml_min": {
        "label": "Estimated glomerular filtration rate",
        "unit": "mL/min/1.73m2",
        "aliases": ["egfr", "e gfr", "estimated gfr", "gfr", "egfr ckd epi"],
        "bounds": (1.0, 200.0),
        "ranges": {"default": (90.0, None)},
        "source": "https://www.kidney.org/kidney-topics/estimated-glomerular-filtration-rate-egfr",
        "intake_links": ["protein", "sodium", "potassium", "phosphorus", "ckd"],
    },
    "urea_mg_dl": {
        "label": "Blood urea",
        "unit": "mg/dL",
        "aliases": ["urea", "blood urea", "serum urea", "bun", "blood urea nitrogen", "s urea"],
        "bounds": (2.0, 300.0),
        "ranges": {"default": (15.0, 40.0)},
        "source": "https://medlineplus.gov/lab-tests/blood-urea-nitrogen-bun-test/",
        "intake_links": ["protein", "fluid", "ckd"],
    },
    "uric_acid_mg_dl": {
        "label": "Uric acid",
        "unit": "mg/dL",
        "aliases": ["uric acid", "serum uric acid", "s uric acid", "s. uric acid", "urate"],
        "bounds": (0.5, 25.0),
        "ranges": {"default": (2.4, 7.0), "female": (2.4, 6.0), "male": (3.4, 7.0)},
        "source": "https://medlineplus.gov/lab-tests/uric-acid-test/",
        "intake_links": ["purines", "alcohol", "gout"],
    },
    "sodium_meq_l": {
        "label": "Sodium",
        "unit": "mEq/L",
        "aliases": ["sodium", "na", "serum sodium", "s sodium"],
        "bounds": (90.0, 200.0),
        "ranges": {"default": (135.0, 145.0)},
        "source": "https://medlineplus.gov/lab-tests/electrolyte-panel/",
        "intake_links": ["sodium", "fluid", "hypertension"],
    },
    "potassium_meq_l": {
        "label": "Potassium",
        "unit": "mEq/L",
        "aliases": ["potassium", "k", "serum potassium", "s potassium"],
        "bounds": (1.0, 12.0),
        "ranges": {"default": (3.5, 5.1)},
        "source": "https://medlineplus.gov/lab-tests/electrolyte-panel/",
        "intake_links": ["potassium", "ckd"],
    },
    "phosphorus_mg_dl": {
        "label": "Phosphorus",
        "unit": "mg/dL",
        "aliases": ["phosphorus", "phosphate", "serum phosphate", "inorganic phosphate"],
        "bounds": (0.3, 20.0),
        "ranges": {"default": (2.5, 4.5)},
        "source": "https://medlineplus.gov/lab-tests/electrolyte-panel/",
        "intake_links": ["phosphorus", "ckd"],
    },
    "calcium_mg_dl": {
        "label": "Calcium",
        "unit": "mg/dL",
        "aliases": ["calcium", "serum calcium", "total calcium", "corrected calcium"],
        "bounds": (3.0, 20.0),
        "ranges": {"default": (8.6, 10.3)},
        "source": "https://medlineplus.gov/lab-tests/electrolyte-panel/",
        "intake_links": ["calcium", "vitamin_d"],
    },
    "alt_u_l": {
        "label": "Alanine aminotransferase (ALT/SGPT)",
        "unit": "U/L",
        "aliases": ["alt", "sgpt", "sgot sgpt", "alanine aminotransferase", "alt sgpt", "sgpt alt", "serum alt"],
        "bounds": (0.0, 5000.0),
        "ranges": {"default": (7.0, 56.0)},
        "source": "https://medlineplus.gov/lab-tests/liver-function-tests/",
        "intake_links": ["alcohol", "liver"],
    },
    "ast_u_l": {
        "label": "Aspartate aminotransferase (AST/SGOT)",
        "unit": "U/L",
        "aliases": ["ast", "sgot", "aspartate aminotransferase", "ast sgot", "sgot ast", "serum ast"],
        "bounds": (0.0, 5000.0),
        "ranges": {"default": (10.0, 40.0)},
        "source": "https://medlineplus.gov/lab-tests/liver-function-tests/",
        "intake_links": ["alcohol", "liver"],
    },
    "bilirubin_total_mg_dl": {
        "label": "Total bilirubin",
        "unit": "mg/dL",
        "aliases": ["bilirubin", "total bilirubin", "bilirubin total", "serum bilirubin", "s bilirubin"],
        "bounds": (0.05, 60.0),
        "ranges": {"default": (0.1, 1.2)},
        "source": "https://medlineplus.gov/lab-tests/liver-function-tests/",
        "intake_links": ["liver"],
    },
    "albumin_g_dl": {
        "label": "Albumin",
        "unit": "g/dL",
        "aliases": ["albumin", "serum albumin", "s albumin"],
        "bounds": (0.5, 8.0),
        "ranges": {"default": (3.5, 5.0)},
        "source": "https://medlineplus.gov/lab-tests/liver-function-tests/",
        "intake_links": ["protein", "liver"],
    },
    "alp_u_l": {
        "label": "Alkaline phosphatase",
        "unit": "U/L",
        "aliases": ["alp", "alkaline phosphatase", "s alp", "alk phos"],
        "bounds": (5.0, 3000.0),
        "ranges": {"default": (44.0, 147.0), "under_18": (100.0, 400.0)},
        "source": "https://medlineplus.gov/lab-tests/liver-function-tests/",
        "intake_links": ["liver"],
    },
    "vitamin_d_ng_ml": {
        "label": "Vitamin D (25-OH)",
        "unit": "ng/mL",
        "aliases": [
            "vitamin d",
            "vit d",
            "vit d3",
            "vitamin d3",
            "25 oh vitamin d",
            "25 hydroxy vitamin d",
            "25-oh vitamin d",
            "vitamin d 25 oh",
        ],
        "bounds": (1.0, 400.0),
        "ranges": {"default": (30.0, 100.0)},
        "source": "https://ods.od.nih.gov/factsheets/VitaminD-Consumer/",
        "intake_links": ["vitamin_d", "calcium"],
    },
    "vitamin_b12_pg_ml": {
        "label": "Vitamin B12",
        "unit": "pg/mL",
        "aliases": ["vitamin b12", "vit b12", "b12", "cobalamin", "serum vitamin b12", "cyanocobalamin"],
        "bounds": (10.0, 5000.0),
        "ranges": {"default": (200.0, 900.0), "75_plus": (180.0, 900.0)},
        "source": "https://ods.od.nih.gov/factsheets/VitaminB12-Consumer/",
        "intake_links": ["vitamin_b12", "folate", "anaemia"],
    },
    "folate_ng_ml": {
        "label": "Folate",
        "unit": "ng/mL",
        "aliases": ["folate", "folic acid", "serum folate", "vitamin b9"],
        "bounds": (0.1, 100.0),
        "ranges": {"default": (3.0, 20.0)},
        "source": "https://ods.od.nih.gov/factsheets/Folate-Consumer/",
        "intake_links": ["folate", "anaemia"],
    },
    "crp_mg_l": {
        "label": "C-reactive protein",
        "unit": "mg/L",
        "aliases": ["crp", "c reactive protein", "c-reactive protein", "hs crp", "hscrp", "high sensitivity crp"],
        "bounds": (0.0, 500.0),
        "ranges": {"default": (0.0, 5.0)},
        "source": "https://medlineplus.gov/lab-tests/c-reactive-protein-crp-test/",
        "intake_links": ["inflammation"],
    },
    "systolic_bp_mmhg": {
        "label": "Systolic blood pressure",
        "unit": "mmHg",
        "aliases": ["systolic", "systolic blood pressure", "sbp", "bp systolic", "systolic bp"],
        "bounds": (40.0, 300.0),
        "ranges": {"default": (90.0, 120.0)},
        "source": "https://www.who.int/news-room/fact-sheets/detail/hypertension",
        "intake_links": ["sodium", "potassium", "alcohol", "hypertension"],
    },
    "diastolic_bp_mmhg": {
        "label": "Diastolic blood pressure",
        "unit": "mmHg",
        "aliases": ["diastolic", "diastolic blood pressure", "dbp", "bp diastolic", "diastolic bp"],
        "bounds": (20.0, 200.0),
        "ranges": {"default": (60.0, 80.0)},
        "source": "https://www.who.int/news-room/fact-sheets/detail/hypertension",
        "intake_links": ["sodium", "potassium", "alcohol", "hypertension"],
    },
    "weight_kg": {
        "label": "Weight",
        "unit": "kg",
        "aliases": ["weight", "body weight", "wt", "weight kg"],
        "bounds": (1.0, 500.0),
        "ranges": {},
        "source": "https://www.cdc.gov/bmi/index.html",
        "intake_links": ["energy", "protein"],
    },
    "height_cm": {
        "label": "Height",
        "unit": "cm",
        "aliases": ["height", "body height", "ht", "height cm"],
        "bounds": (30.0, 260.0),
        "ranges": {},
        "source": "https://www.cdc.gov/bmi/index.html",
        "intake_links": ["energy", "protein"],
    },
    "bmi": {
        "label": "Body mass index",
        "unit": "kg/m2",
        "aliases": ["bmi", "body mass index"],
        "bounds": (5.0, 120.0),
        "ranges": {"default": (18.5, 24.9)},
        "source": "https://www.who.int/news-room/fact-sheets/detail/obesity-and-overweight",
        "intake_links": ["energy", "protein"],
    },
}

assert set(LAB_REGISTRY) == set(CANONICAL_KEYS), "registry must cover the canonical vocabulary"

# --- Printed-name canonicalisation -------------------------------------------------------

# Leading qualifiers that carry no meaning once the analyte name is normalised.
_LEADING_QUALIFIERS = ("s", "serum", "plasma", "blood", "total")


def _normalise_name(value: str) -> str:
    text = unicodedata.normalize("NFKD", value).casefold()
    text = text.replace("µ", "u").replace("μ", "u").replace("^", " ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def _build_alias_index() -> dict[str, str]:
    index: dict[str, str] = {}
    for key, entry in LAB_REGISTRY.items():
        for alias in (key, entry["label"], *entry["aliases"]):
            normalised = _normalise_name(alias)
            if normalised:
                index.setdefault(normalised, key)
    return index


_ALIAS_INDEX = _build_alias_index()


def canonicalise(name: str) -> str | None:
    """Map a printed parameter name to its canonical key, or ``None`` when unknown.

    Deterministic: exact normalised match first, then the same match with leading
    ``s``/``serum``/``plasma``/``blood``/``total`` qualifiers removed.
    """
    if not isinstance(name, str):
        return None
    token = _normalise_name(name)
    if not token:
        return None
    match = _ALIAS_INDEX.get(token)
    if match is not None:
        return match
    parts = token.split()
    while len(parts) > 1 and parts[0] in _LEADING_QUALIFIERS:
        parts = parts[1:]
        match = _ALIAS_INDEX.get(" ".join(parts))
        if match is not None:
            return match
    return None


# --- Unit conversion ---------------------------------------------------------------------

# canonical unit -> multiplicative factor to that group's base unit.
_CONVERSIONS: dict[str, dict[str, float]] = {
    "glucose": {"mg/dl": 1.0, "mmol/l": 18.0182},
    "cholesterol": {"mg/dl": 1.0, "mmol/l": 38.67},
    "triglycerides": {"mg/dl": 1.0, "mmol/l": 88.57},
    "creatinine": {"mg/dl": 1.0, "umol/l": 0.011312},
    "haemoglobin": {"g/dl": 1.0, "g/l": 0.1},
    "vitamin_d": {"ng/ml": 1.0, "nmol/l": 0.4},
    "vitamin_b12": {"pg/ml": 1.0, "pmol/l": 1.355},
    "urate": {"mg/dl": 1.0, "umol/l": 0.0168},
}

_UNIT_ALIASES = {
    "mg/dl": "mg/dl",
    "mmol/l": "mmol/l",
    "g/dl": "g/dl",
    "g/l": "g/l",
    "umol/l": "umol/l",
    "ng/ml": "ng/ml",
    "nmol/l": "nmol/l",
    "pg/ml": "pg/ml",
    "pmol/l": "pmol/l",
    "miu/l": "miu/l",
    "meq/l": "meq/l",
    "u/l": "u/l",
}


def _normalise_unit(unit: str | None) -> str | None:
    if not isinstance(unit, str):
        return None
    text = unit.casefold().replace("µ", "u").replace("μ", "u").replace(" ", "")
    return _UNIT_ALIASES.get(text)


def convert(value: float | None, unit: str | None, target_unit: str | None) -> float | None:
    """Convert between the accepted unit pairs; ``None`` when no pair applies.

    Only pairs whose quantity is unambiguous are converted (glucose, cholesterol/
    LDL/HDL, triglycerides, creatinine, haemoglobin, vitamins D and B12, urate).
    """
    if value is None:
        return None
    source = _normalise_unit(unit)
    target = _normalise_unit(target_unit)
    if source is None or target is None:
        return None
    for group in _CONVERSIONS.values():
        if source in group and target in group:
            return value * group[source] / group[target]
    return None


# --- Reference ranges and classification --------------------------------------------------


def reference_range(
    key: str, sex: Sex = "unspecified", age_band: AgeBand = "unspecified"
) -> tuple[float | None, float | None, str]:
    """Default reference interval for ``key`` as ``(low, high, source)``.

    ``source`` is ``"standard"`` when a registry range applies and ``"unknown"``
    otherwise. Most specific selector wins; ``None`` on a side means unbounded.
    """
    entry = LAB_REGISTRY.get(key)
    if entry is None:
        return (None, None, "unknown")
    ranges = entry.get("ranges") or {}
    for selector in (f"{sex}:{age_band}", sex, f"unspecified:{age_band}", age_band, "default"):
        if selector in ranges:
            low, high = ranges[selector]
            return (low, high, "standard")
    return (None, None, "unknown")


def _get(parameter: LabParameter | Mapping[str, Any], name: str) -> Any:
    if isinstance(parameter, Mapping):
        return parameter.get(name)
    return getattr(parameter, name, None)


def parameter_range(
    parameter: LabParameter | Mapping[str, Any],
    sex: Sex = "unspecified",
    age_band: AgeBand = "unspecified",
) -> tuple[float | None, float | None, str]:
    """The range to classify against: the document's printed range if any, else the standard.

    A document range wins whenever at least one bound is printed, so a report that
    only prints an upper limit is still classified against that limit.
    """
    printed_low = _get(parameter, "reference_low")
    printed_high = _get(parameter, "reference_high")
    if printed_low is not None or printed_high is not None:
        return (printed_low, printed_high, "document")
    return reference_range(_get(parameter, "key") or "", sex, age_band)


def classify(
    parameter: LabParameter | Mapping[str, Any],
    sex: Sex = "unspecified",
    age_band: AgeBand = "unspecified",
) -> str:
    """Return ``low``/``normal``/``high``/``unknown`` for a parameter.

    Unknown when the value is missing or no range is available at all. An exact
    boundary value is normal (inclusive interval).
    """
    value = _get(parameter, "value")
    low, high, _ = parameter_range(parameter, sex, age_band)
    if value is None or (low is None and high is None):
        return "unknown"
    if low is not None and value < low:
        return "low"
    if high is not None and value > high:
        return "high"
    return "normal"


def quarantine(value: float | None, key: str) -> tuple[float | None, str | None]:
    """Null a physically implausible value and explain why.

    Returns ``(value, warning)``. The warning names the parameter and its plausible
    range but never echoes the reported value.
    """
    if value is None:
        return (None, None)
    entry = LAB_REGISTRY.get(key)
    if entry is None:
        return (value, None)
    low, high = entry["bounds"]
    if not isinstance(value, (int, float)) or not (low <= float(value) <= high):
        warning = (
            f"{entry['label']} was outside the plausible range "
            f"({low:g}-{high:g} {entry['unit']}); it was treated as unknown."
        )
        return (None, warning)
    return (float(value), None)


def build_parameters(
    items: list[Mapping[str, Any]],
    sex: Sex = "unspecified",
    age_band: AgeBand = "unspecified",
) -> tuple[list[LabParameter], list[str]]:
    """Turn model-read items into canonical, converted, checked ``LabParameter`` rows.

    Conversion, quarantine and classification are all performed here so the stored
    status is always reproducible from the stored value and range.
    """
    parameters: list[LabParameter] = []
    warnings: list[str] = []
    seen: set[str] = set()
    for item in items:
        key = item.get("key") or "unrecognised"
        entry = LAB_REGISTRY.get(key)
        if entry is None:
            key = "unrecognised"
        if key != "unrecognised":
            if key in seen:
                warnings.append(
                    f"{entry['label']} appeared more than once; only the first reading was kept."
                )
                continue
            seen.add(key)
        label = (item.get("label") or "").strip() or "Unrecognised parameter"
        raw_text = item.get("raw_text")
        value = item.get("value")
        unit = item.get("unit")
        reference_low = item.get("reference_low")
        reference_high = item.get("reference_high")
        if entry and value is not None and unit:
            target = entry["unit"]
            if _normalise_unit(unit) != _normalise_unit(target):
                converted = convert(value, unit, target)
                if converted is None:
                    warnings.append(
                        f"{entry['label']}: unit {unit!r} is not convertible to {target}; "
                        "the printed unit was kept."
                    )
                else:
                    value = converted
                    # Move the printed range with the value so classification stays consistent.
                    if reference_low is not None:
                        reference_low = convert(reference_low, unit, target)
                    if reference_high is not None:
                        reference_high = convert(reference_high, unit, target)
                    unit = target
        value, warning = quarantine(value, key)
        if warning:
            warnings.append(warning)
        candidate = {
            "key": key,
            "label": label[:120],
            "value": value,
            "unit": unit,
            "reference_low": reference_low,
            "reference_high": reference_high,
            "raw_text": raw_text,
        }
        low, high, source = parameter_range(candidate, sex, age_band)
        candidate["reference_low"] = low
        candidate["reference_high"] = high
        candidate["reference_source"] = source
        candidate["status"] = classify(candidate, sex, age_band)
        parameters.append(LabParameter.model_validate(candidate))
    return parameters, warnings


def confirmed_reports(session: Session, owner_id: str, *, limit: int = 20) -> list[dict]:
    """Confirmed ``HealthReport`` rows for one owner, newest first.

    Returns ``[{"id": str, "collected_on": str | None, "parameters": list[dict]}]``
    where each parameter dict follows the frozen ``LabParameter`` shape
    (key, label, value, unit, reference_low, reference_high, reference_source,
    status). Only rows with ``status == "confirmed"`` are returned.

    ``HealthReport.parameters`` stores exactly the confirmed ``LabParameter`` dump,
    so no translation is needed here. The model is imported locally to avoid an
    import cycle (``app.models`` is the schema owner and imports nothing from here).
    """
    from app.models import HealthReport

    rows = session.scalars(
        select(HealthReport)
        .where(HealthReport.owner_id == owner_id, HealthReport.status == "confirmed")
        .order_by(HealthReport.created_at.desc(), HealthReport.id.desc())
        .limit(limit)
    ).all()
    return [
        {
            "id": row.id,
            "collected_on": row.collected_on,
            "parameters": list(row.parameters or []),
        }
        for row in rows
    ]
