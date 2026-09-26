"""Personal intake engine: baselines, deterministic rules and the proposal it produces.

This module is pure. It never reads the database and never writes to a profile: it takes a
``ProfileData`` and a list of health-report dictionaries and returns a plan shaped like the
frozen ``IntakePlan``. Recording a limit remains the job of ``PUT /api/profiles/me``.

Honesty rules that the code enforces, not just documents:
  * only reports whose ``status`` is ``confirmed`` can trigger a proposal; an extracted,
    unconfirmed report is excluded and the plan says how many were held back;
  * ``clinician_only`` rules never carry a numeric target;
  * several rules touching one nutrient merge to the strictest target with every piece of
    evidence retained;
  * every target states its own limitation in ``basis``.
"""

from decimal import ROUND_HALF_UP, Decimal

from app.schemas import ProfileData
from app.services.conditions import condition_info, resolve_conditions

INTAKE_VERSION = "intake-2026-09-26.2"

# --- Nutrient metadata and baselines -----------------------------------------------------
#
# value + unit + label + a real source + a basis sentence. For nutrients with no
# guideline-style number (iron, vitamins) the value is ``None`` and only adequacy framing
# is offered; a food record cannot set those numbers.
#
# Where the label proxy differs from the guideline it cites, the basis says so. The clear
# case is ``sugars_g``: a nutrition label's "total sugars" also counts the milk and fruit
# sugars naturally present, while the WHO guideline is about *free* sugars.

NUTRIENT_META = {
    "sodium_mg": {
        "value": 2000,
        "unit": "mg",
        "label": "Sodium",
        "source": "https://www.who.int/news-room/fact-sheets/detail/salt-reduction",
        "basis": (
            "WHO recommends less than 2000 mg of sodium a day for adults, about 5 g of salt."
        ),
    },
    "sugars_g": {
        "value": 50,
        "unit": "g",
        "label": "Sugars",
        "source": "https://www.who.int/news-room/fact-sheets/detail/healthy-diet",
        "basis": (
            "WHO suggests free sugars below 10% of energy; 50 g approximates that for a "
            "2000 kcal diet. A label's total sugars also includes naturally occurring milk "
            "and fruit sugars, so it is not the same measure as free sugars."
        ),
    },
    "saturated_fat_g": {
        "value": 20,
        "unit": "g",
        "label": "Saturated fat",
        "source": "https://www.who.int/news-room/fact-sheets/detail/healthy-diet",
        "basis": (
            "WHO suggests saturated fat below 10% of energy; 20 g approximates that for a "
            "2000 kcal diet."
        ),
    },
    "fat_g": {
        "value": 66,
        "unit": "g",
        "label": "Total fat",
        "source": "https://www.who.int/news-room/fact-sheets/detail/healthy-diet",
        "basis": (
            "WHO suggests total fat below 30% of energy; 66 g approximates that for a "
            "2000 kcal diet."
        ),
    },
    "carbohydrates_g": {
        "value": 275,
        "unit": "g",
        "label": "Carbohydrate",
        "source": "https://www.who.int/news-room/fact-sheets/detail/healthy-diet",
        "basis": (
            "About 50-55% of energy from carbohydrate for a 2000 kcal reference diet, favouring "
            "whole-grain and high-fibre sources."
        ),
    },
    "protein_g": {
        "value": 56,
        "unit": "g",
        "label": "Protein",
        "source": "https://ods.od.nih.gov/factsheets/Protein-Consumer/",
        "basis": (
            "The US RDA is 0.8 g of protein per kg; 56 g approximates this for a 70 kg adult. "
            "Sex-specific reference values are used when sex is known."
        ),
    },
    "fiber_g": {
        "value": 30,
        "unit": "g",
        "label": "Fibre",
        "source": "https://www.who.int/news-room/fact-sheets/detail/healthy-diet",
        "basis": "WHO suggests at least 30 g of fibre a day for adults from whole foods.",
    },
    "potassium_mg": {
        "value": 3500,
        "unit": "mg",
        "label": "Potassium",
        "source": "https://www.who.int/news-room/fact-sheets/detail/salt-reduction",
        "basis": (
            "WHO suggests at least 3510 mg of potassium a day from food for adults; 3500 mg "
            "is used as the prototype reference."
        ),
    },
    "phosphorus_mg": {
        "value": 700,
        "unit": "mg",
        "label": "Phosphorus",
        "source": "https://ods.od.nih.gov/factsheets/Phosphorus-Consumer/",
        "basis": (
            "The US RDA is 700 mg of phosphorus a day for adults. Phosphate additives are "
            "absorbed differently from food phosphate."
        ),
    },
    "energy_kcal": {
        "value": 2000,
        "unit": "kcal",
        "label": "Energy",
        "source": "https://www.who.int/news-room/fact-sheets/detail/healthy-diet",
        "basis": (
            "2000 kcal is a reference adult diet; individual energy needs vary with body size "
            "and activity."
        ),
    },
    # Adequacy-only nutrients: no guideline number is offered here.
    "iron": {
        "value": None,
        "unit": "mg",
        "label": "Iron",
        "source": "https://ods.od.nih.gov/factsheets/Iron-Consumer/",
        "basis": "Iron needs are individual and a food record cannot set an iron number.",
    },
    "vitamin_b12": {
        "value": None,
        "unit": "\u00b5g",
        "label": "Vitamin B12",
        "source": "https://ods.od.nih.gov/factsheets/VitaminB12-Consumer/",
        "basis": "B12 adequacy is judged from blood levels, not from a single food record.",
    },
    "vitamin_d": {
        "value": None,
        "unit": "\u00b5g",
        "label": "Vitamin D",
        "source": "https://ods.od.nih.gov/factsheets/VitaminD-Consumer/",
        "basis": "Vitamin D adequacy is judged from blood levels and clinical advice.",
    },
    "iodine": {
        "value": None,
        "unit": "\u00b5g",
        "label": "Iodine",
        "source": "https://ods.od.nih.gov/factsheets/Iodine-Consumer/",
        "basis": "Iodine adequacy depends on diet, salt use and clinical advice.",
    },
    "calcium": {
        "value": None,
        "unit": "mg",
        "label": "Calcium",
        "source": "https://ods.od.nih.gov/factsheets/Calcium-Consumer/",
        "basis": "Calcium adequacy depends on dietary sources and clinical advice.",
    },
    "folate": {
        "value": None,
        "unit": "\u00b5g",
        "label": "Folate",
        "source": "https://ods.od.nih.gov/factsheets/Folate-Consumer/",
        "basis": "Folate adequacy depends on diet, fortification and clinical advice.",
    },
}

# --- Human-scale conversions -------------------------------------------------------------
#
# Targets are proposed in the units a label or a lab uses. People cook and pour in different
# units, so the same number is also stated in the unit a person can picture: sodium as grams
# of salt (salt is about 40% sodium, so salt = sodium x 2.5, and 1000 mg = 1 g), sugars in
# teaspoons (1 tsp of sugar is about 4 g), saturated fat as a share of a 2000 kcal reference
# day (9 kcal per gram of fat). These are conversions of the same number, not new advice.

SALT_PER_SODIUM = 2.5
SUGAR_GRAMS_PER_TEASPOON = 4
KCAL_PER_GRAM_FAT = 9
REFERENCE_ENERGY_KCAL = 2000

# nutrient -> conversion rows.
#   ``label``/``unit`` shape the structured ``IntakeEquivalent`` row the UI renders;
#   ``factor`` multiplies a value in the nutrient's own unit;
#   ``decimals`` and ``phrase`` shape the sentence a person reads;
#   ``in_display`` is False when the row only restates the same unit (fibre and protein in
#   grams), so the sentence stays short while the structured row is still offered.
CONVERSIONS = {
    "sodium_mg": [
        {
            "label": "grams of salt",
            "unit": "g",
            "factor": SALT_PER_SODIUM / 1000,
            "decimals": 1,
            "phrase": "g salt",
            "in_display": True,
        }
    ],
    "sugars_g": [
        {
            "label": "teaspoons of sugar",
            "unit": "tsp",
            "factor": 1 / SUGAR_GRAMS_PER_TEASPOON,
            "decimals": 0,
            "phrase": "teaspoons",
            "in_display": True,
        }
    ],
    "saturated_fat_g": [
        {
            "label": "% of a 2000 kcal day",
            "unit": "%",
            "factor": KCAL_PER_GRAM_FAT * 100 / REFERENCE_ENERGY_KCAL,
            "decimals": 1,
            "phrase": "% of a 2000 kcal day",
            "in_display": True,
        }
    ],
    "fiber_g": [
        {
            "label": "grams of fibre",
            "unit": "g",
            "factor": 1.0,
            "decimals": 0,
            "phrase": "g fibre",
            "in_display": False,
        }
    ],
    "protein_g": [
        {
            "label": "grams of protein",
            "unit": "g",
            "factor": 1.0,
            "decimals": 0,
            "phrase": "g protein",
            "in_display": False,
        }
    ],
}

# Sex-specific reference values. When sex is unspecified the higher (wider) value is used
# and the target says so, rather than silently assuming one sex.
SEX_VALUES = {
    "protein_g": {"female": 46, "male": 56},
    "fiber_g": {"female": 25, "male": 38},
}

# Age-band reference values. Unspecified age uses the base value and says the wider
# reference was kept.
AGE_VALUES = {
    "energy_kcal": {"60_74": 1900, "75_plus": 1800},
}

# Low reference thresholds for lab values whose usual range differs by sex. ``below_ref``
# comparators read this table; ``unspecified`` uses the lower bound of the union so the
# widened range is stated rather than guessed.
LOW_REFERENCE = {
    "hemoglobin_g_dl": {"female": 12.0, "male": 13.5},
}

WIDE_SEX_NOTE = "widened range used because sex is unspecified"
WIDE_AGE_NOTE = "widened range used because age band is unspecified"


def resolve_baseline(nutrient: str, sex: str, age_band: str) -> tuple[float | None, list[str]]:
    """Return the baseline value for one nutrient plus any 'widened range' notes."""
    meta = NUTRIENT_META[nutrient]
    value = meta["value"]
    notes: list[str] = []
    if nutrient in SEX_VALUES:
        table = SEX_VALUES[nutrient]
        if sex in table:
            value = table[sex]
        else:
            value = max(table.values())
            notes.append(WIDE_SEX_NOTE)
    if nutrient in AGE_VALUES:
        table = AGE_VALUES[nutrient]
        if age_band in table:
            value = table[age_band]
        elif age_band == "unspecified":
            value = max([meta["value"] or 0, *table.values()])
            notes.append(WIDE_AGE_NOTE)
    return value, notes


def low_reference(key: str, sex: str) -> tuple[float | None, str | None]:
    """The low threshold for a lab key, with a widened-range note when sex is unknown."""
    table = LOW_REFERENCE.get(key)
    if not table:
        return None, None
    if sex in table:
        return table[sex], None
    return min(table.values()), WIDE_SEX_NOTE


# --- Human-scale helpers -----------------------------------------------------------------


def _round_half_up(value: float, decimals: int) -> float:
    """Round for display: .5 always goes up, with no binary-float surprises."""
    quantum = Decimal(1).scaleb(-decimals)
    return float(Decimal(str(value)).quantize(quantum, rounding=ROUND_HALF_UP))


def _format_value(value: float | None) -> str:
    """A compact, human number: 1500, 3.75, 6.25."""
    if value is None:
        return ""
    return f"{value:g}"


def equivalents_for(nutrient: str, value: float | None) -> list[dict]:
    """Structured human-scale rows for one number (sodium -> grams of salt).

    Pure and reusable for any value, so a baseline reference converts exactly like a
    proposal: 2000 mg of sodium is 5 g of salt, 50 g of sugars is 12.5 teaspoons.
    """
    if value is None:
        return []
    return [
        {
            "label": row["label"],
            "value": round(value * row["factor"], 6),
            "unit": row["unit"],
        }
        for row in CONVERSIONS.get(nutrient, [])
    ]


def _display_phrases(nutrient: str, value: float) -> list[str]:
    """The conversion rows that read naturally in a sentence, e.g. '3.8 g salt'."""
    return [
        f"{_format_value(_round_half_up(value * row['factor'], row['decimals']))} {row['phrase']}"
        for row in CONVERSIONS.get(nutrient, [])
        if row["in_display"]
    ]


def display_value(nutrient: str, value: float) -> str:
    """'1500 mg sodium = 3.8 g salt' in one line a person can read aloud."""
    meta = NUTRIENT_META[nutrient]
    text = f"{_format_value(value)} {meta['unit']} {meta['label'].lower()}"
    phrases = _display_phrases(nutrient, value)
    if phrases:
        text = f"{text} \u2248 " + "; ".join(phrases)
    return text


def _evidence_key(item: dict) -> tuple:
    return (item["kind"], item["label"], item.get("report_id"), item.get("value"))


def _dedupe_evidence(items: list[dict]) -> list[dict]:
    """Keep first occurrences only: one report value counts once per list."""
    seen: set[tuple] = set()
    rows: list[dict] = []
    for item in items:
        key = _evidence_key(item)
        if key not in seen:
            seen.add(key)
            rows.append(item)
    return rows


# --- Comparators -------------------------------------------------------------------------


def compare(op: str, actual: float, threshold: float) -> bool:
    """Deterministic comparator. Boundaries are inclusive for ``>=``/``<=`` as written."""
    if op == ">=":
        return actual >= threshold
    if op == ">":
        return actual > threshold
    if op == "<=":
        return actual <= threshold
    if op == "<":
        return actual < threshold
    raise ValueError(f"unsupported comparator {op!r}")


# --- Rules -------------------------------------------------------------------------------
#
# Each rule: id/version, a trigger (condition slugs OR lab comparators, OR-combined), an
# effect (nutrient + direction + proposed value), a basis, confidence, whether a clinician
# must set the value, questions, and a note reused in the confirmation source.
# ``clinician_only`` rules carry ``proposed_value: None`` by construction.

RULES = [
    {
        "id": "diabetes_saturated_fat_v1",
        "nutrient": "saturated_fat_g",
        "direction": "lower",
        "proposed_value": 15,
        "conditions": ["type_1_diabetes", "type_2_diabetes"],
        "labs": [{"key": "hba1c_percent", "op": ">=", "value": 6.5}],
        "basis": (
            "Diabetes raises heart risk, so saturated fat is often kept to about 7% of energy; "
            "15 g approximates that for a 2000 kcal diet."
        ),
        "confidence": "established",
        "requires_clinician": False,
        "questions": ["What saturated fat amount fits my heart risk?"],
    },
    {
        "id": "diabetes_sugar_v1",
        "nutrient": "sugars_g",
        "direction": "lower",
        "proposed_value": 25,
        "conditions": ["type_1_diabetes", "type_2_diabetes"],
        "labs": [{"key": "hba1c_percent", "op": ">=", "value": 6.5}],
        "basis": (
            "Free sugars are usually kept below 5% of energy in diabetes care; 25 g "
            "approximates that for a 2000 kcal diet. Confirm the amount with your clinician "
            "because it interacts with medicines and glucose readings."
        ),
        "confidence": "established",
        "requires_clinician": True,
        "questions": ["What daily sugar amount fits my glucose readings and medicines?"],
    },
    {
        "id": "prediabetes_sugar_v1",
        "nutrient": "sugars_g",
        "direction": "lower",
        "proposed_value": 25,
        "conditions": ["prediabetes"],
        "labs": [{"key": "hba1c_percent", "op": ">=", "value": 5.7}],
        "basis": (
            "Prediabetes responds to reducing free sugars; 25 g approximates the 5%-of-energy "
            "suggestion for a 2000 kcal diet."
        ),
        "confidence": "general_wellbeing",
        "requires_clinician": False,
        "questions": ["What sugar amount should I aim for while making changes?"],
    },
    {
        "id": "hypertension_sodium_v1",
        "nutrient": "sodium_mg",
        "direction": "lower",
        "proposed_value": 1500,
        "conditions": ["hypertension"],
        "labs": [{"key": "systolic_bp_mmhg", "op": ">=", "value": 130}],
        "basis": (
            "Sodium reduction lowers blood pressure; 1500 mg is a commonly used stricter "
            "target for raised blood pressure and approximates 3.8 g of salt."
        ),
        "confidence": "established",
        "requires_clinician": False,
        "questions": ["What sodium target fits my blood pressure and medicines?"],
    },
    {
        "id": "ckd_sodium_v1",
        "nutrient": "sodium_mg",
        "direction": "lower",
        "proposed_value": 1500,
        "conditions": ["ckd"],
        "labs": [{"key": "egfr_ml_min", "op": "<", "value": 60}],
        "basis": (
            "In chronic kidney disease, sodium reduction supports blood pressure and fluid "
            "control; 1500 mg is a commonly used stricter target."
        ),
        "confidence": "established",
        "requires_clinician": False,
        "questions": ["What sodium target fits my kidney stage and medicines?"],
    },
    {
        "id": "ckd_potassium_v1",
        "nutrient": "potassium_mg",
        "direction": "lower",
        "proposed_value": None,
        "conditions": ["ckd"],
        "labs": [{"key": "egfr_ml_min", "op": "<", "value": 60}],
        "basis": (
            "Potassium limits in kidney disease depend on blood potassium, medicines and "
            "stage, so a clinician must set any number."
        ),
        "confidence": "clinician_only",
        "requires_clinician": True,
        "questions": ["What potassium amount is safe for my kidney function?"],
    },
    {
        "id": "ckd_phosphorus_v1",
        "nutrient": "phosphorus_mg",
        "direction": "lower",
        "proposed_value": None,
        "conditions": ["ckd"],
        "labs": [{"key": "egfr_ml_min", "op": "<", "value": 60}],
        "basis": (
            "Phosphate control in kidney disease is managed with diet, binders and blood "
            "tests together, so a clinician must set any number."
        ),
        "confidence": "clinician_only",
        "requires_clinician": True,
        "questions": ["What phosphate amount fits my blood tests and binders?"],
    },
    {
        "id": "ckd_protein_v1",
        "nutrient": "protein_g",
        "direction": "lower",
        "proposed_value": None,
        "conditions": ["ckd"],
        "labs": [{"key": "egfr_ml_min", "op": "<", "value": 60}],
        "basis": (
            "Protein intake in kidney disease is individual; too little can worsen nutrition "
            "and too much can stress the kidneys, so a clinician must set any number."
        ),
        "confidence": "clinician_only",
        "requires_clinician": True,
        "questions": ["What protein amount is right for my kidney function?"],
    },
    {
        "id": "hyperkalaemia_potassium_v1",
        "nutrient": "potassium_mg",
        "direction": "lower",
        "proposed_value": None,
        "conditions": ["hyperkalaemia"],
        "labs": [{"key": "potassium_meq_l", "op": ">=", "value": 5.5}],
        "basis": (
            "Blood potassium above the usual range can affect heart rhythm; the safe intake "
            "must come from your clinical team, never from a prototype figure."
        ),
        "confidence": "clinician_only",
        "requires_clinician": True,
        "questions": ["Which foods raise my potassium most, and how much is safe?"],
    },
    {
        "id": "hyperphosphataemia_phosphorus_v1",
        "nutrient": "phosphorus_mg",
        "direction": "lower",
        "proposed_value": None,
        "conditions": ["hyperphosphataemia"],
        "labs": [{"key": "phosphorus_mg_dl", "op": ">=", "value": 4.5}],
        "basis": (
            "Blood phosphate above the usual range needs individual management with diet and "
            "binders, so a clinician must set any number."
        ),
        "confidence": "clinician_only",
        "requires_clinician": True,
        "questions": ["Which foods contribute phosphate most for me?"],
    },
    {
        "id": "dyslipidaemia_saturated_fat_v1",
        "nutrient": "saturated_fat_g",
        "direction": "lower",
        "proposed_value": 15,
        "conditions": ["dyslipidaemia"],
        "labs": [
            {"key": "ldl_cholesterol_mg_dl", "op": ">=", "value": 130},
            {"key": "triglycerides_mg_dl", "op": ">=", "value": 150},
        ],
        "basis": (
            "Raised LDL or triglycerides respond to cutting saturated fat to about 7% of "
            "energy; 15 g approximates that for a 2000 kcal diet."
        ),
        "confidence": "established",
        "requires_clinician": False,
        "questions": ["What saturated fat ceiling fits my risk?"],
    },
    {
        "id": "dyslipidaemia_fiber_v1",
        "nutrient": "fiber_g",
        "direction": "higher",
        "proposed_value": 30,
        "conditions": ["dyslipidaemia"],
        "labs": [
            {"key": "ldl_cholesterol_mg_dl", "op": ">=", "value": 130},
            {"key": "triglycerides_mg_dl", "op": ">=", "value": 150},
        ],
        "basis": (
            "Soluble fibre lowers LDL cholesterol; 30 g a day is the general adult reference "
            "and is usually reached from whole grains, pulses, fruit and vegetables."
        ),
        "confidence": "established",
        "requires_clinician": False,
        "questions": ["How should I reach a higher fibre intake comfortably?"],
    },
    {
        "id": "gout_sugar_v1",
        "nutrient": "sugars_g",
        "direction": "lower",
        "proposed_value": 25,
        "conditions": ["gout"],
        "labs": [{"key": "uric_acid_mg_dl", "op": ">=", "value": 7.0}],
        "basis": (
            "Fructose-sweetened food and drink raise uric acid; 25 g approximates a low free "
            "sugar intake. Purine-rich foods and alcohol also matter and are not measured here."
        ),
        "confidence": "general_wellbeing",
        "requires_clinician": False,
        "questions": ["Which foods trigger my gout, and how should sugary drinks change?"],
    },
    {
        "id": "anaemia_iron_v1",
        "nutrient": "iron",
        "direction": "maintain",
        "proposed_value": None,
        "conditions": ["iron_deficiency_anaemia"],
        "labs": [{"key": "hemoglobin_g_dl", "op": "below_ref", "value": None}],
        "basis": (
            "Iron-rich foods paired with a vitamin C source improve absorption, while tea, "
            "coffee and calcium at the same meal reduce it. A food record cannot set an iron "
            "number, so none is proposed."
        ),
        "confidence": "general_wellbeing",
        "requires_clinician": False,
        "questions": ["What is causing my iron deficiency, and which pairings suit me?"],
    },
    {
        "id": "b12_low_v1",
        "nutrient": "vitamin_b12",
        "direction": "maintain",
        "proposed_value": None,
        "conditions": ["vitamin_b12_deficiency"],
        "labs": [{"key": "vitamin_b12_pg_ml", "op": "<", "value": 200}],
        "basis": (
            "B12 occurs naturally mainly in animal foods, with some fortified products. "
            "Adequacy is judged from blood levels, so no food number is proposed."
        ),
        "confidence": "general_wellbeing",
        "requires_clinician": False,
        "questions": ["What caused my low B12, and how should it be monitored?"],
    },
    {
        "id": "vitamin_d_low_v1",
        "nutrient": "vitamin_d",
        "direction": "maintain",
        "proposed_value": None,
        "conditions": ["vitamin_d_deficiency"],
        "labs": [{"key": "vitamin_d_ng_ml", "op": "<", "value": 20}],
        "basis": (
            "Vitamin D adequacy is judged from blood levels and sun exposure, with "
            "supplementation set by a clinician, so no food number is proposed."
        ),
        "confidence": "general_wellbeing",
        "requires_clinician": False,
        "questions": ["What vitamin D level should I aim for, and how will it be rechecked?"],
    },
    {
        "id": "tsh_high_v1",
        "nutrient": "iodine",
        "direction": "maintain",
        "proposed_value": None,
        "conditions": ["hypothyroidism"],
        "labs": [{"key": "tsh_miu_l", "op": ">", "value": 4.5}],
        "basis": (
            "Iodine is needed to make thyroid hormone, but the dose for any replacement "
            "therapy is clinical; a food record cannot set it, so no number is proposed."
        ),
        "confidence": "general_wellbeing",
        "requires_clinician": False,
        "questions": ["Should my iodine intake change with my thyroid results?"],
    },
    {
        "id": "pcos_sugar_v1",
        "nutrient": "sugars_g",
        "direction": "maintain",
        "proposed_value": None,
        "conditions": ["pcos"],
        "labs": [],
        "basis": (
            "PCOS is often linked to insulin resistance, so free sugars are commonly reduced. "
            "An individual amount depends on your plan, so none is proposed from a prototype."
        ),
        "confidence": "general_wellbeing",
        "requires_clinician": False,
        "questions": ["How does insulin resistance affect what I should eat?"],
    },
    {
        "id": "pcos_saturated_fat_v1",
        "nutrient": "saturated_fat_g",
        "direction": "maintain",
        "proposed_value": None,
        "conditions": ["pcos"],
        "labs": [],
        "basis": (
            "Saturated fat is commonly reduced in PCOS care alongside sugars; the amount is "
            "individual, so none is proposed here."
        ),
        "confidence": "general_wellbeing",
        "requires_clinician": False,
        "questions": ["Which eating pattern would help my PCOS most?"],
    },
]

RULE_BY_ID = {rule["id"]: rule for rule in RULES}


# --- Avoid rules -------------------------------------------------------------------------
#
# The counterpart to RULES: what to steer around once a value or a condition has fired.
# Each entry carries the same trigger shapes as RULES (``conditions`` OR-combined with
# ``labs``), a severity that says how strong the advice is — ``avoid`` (leave it out),
# ``limit`` (cut back), ``ask`` (decide with the kitchen or a clinician, no number) — and
# concrete foods with the reason each is listed. The table is the only source of these
# lists: nothing is invented for a food the table does not name, and a food that is absent
# is not declared safe.
#
# Copy rules: no diagnosis, no doses, no claim that a listed food is the only risk, and a
# group appears only when its own trigger matched. ``ask`` groups are the honest answer for
# potassium, phosphate, B12, vitamin D and thyroid questions, where a number must come from
# a clinician.

AVOID_RULES = [
    {
        "id": "avoid_glycaemia_sugars_v1",
        "title": "Sugary drinks, sweets and refined-flour foods",
        "detail": (
            "Raised glucose or HbA1c responds to cutting free sugars and refined carbohydrate. "
            "Drinks are listed first because liquid sugar reaches the blood quickly and is "
            "easy to miss when counting."
        ),
        "severity": "limit",
        "conditions": [
            "type_1_diabetes",
            "type_2_diabetes",
            "prediabetes",
            "gestational_diabetes",
        ],
        "labs": [
            {"key": "hba1c_percent", "op": ">=", "value": 6.5},
            {"key": "fasting_glucose_mg_dl", "op": ">=", "value": 126},
            {"key": "random_glucose_mg_dl", "op": ">=", "value": 200},
        ],
        "items": [
            {
                "label": "Sugar-sweetened drinks",
                "examples": [
                    "soft drinks",
                    "packaged fruit drinks",
                    "sweetened iced tea",
                    "energy drinks",
                ],
                "reason": "Liquid free sugars raise blood glucose quickly and add no fibre.",
                "linked_nutrients": ["sugars_g"],
            },
            {
                "label": "Sweets and desserts",
                "examples": [
                    "mithai",
                    "cakes and pastries",
                    "biscuits",
                    "ice cream",
                    "sweet spreads",
                ],
                "reason": "Concentrated free sugars with little fibre to slow them down.",
                "linked_nutrients": ["sugars_g"],
            },
            {
                "label": "Refined-flour (maida) items",
                "examples": [
                    "white bread",
                    "naan and bhatura",
                    "samosa and puffs",
                    "instant noodles",
                    "rusks",
                ],
                "reason": (
                    "Refined flour digests quickly and lifts glucose more than whole grains do."
                ),
                "linked_nutrients": ["carbohydrates_g", "fiber_g"],
            },
            {
                "label": "Fruit juice and sweetened juice drinks",
                "examples": [
                    "packaged fruit juice",
                    "juice concentrates",
                    "large glasses of fresh juice",
                ],
                "reason": "Juice delivers fruit sugar without the fibre of the whole fruit.",
                "linked_nutrients": ["sugars_g"],
            },
        ],
        "confidence": "established",
        "sources": [
            "https://www.who.int/news-room/fact-sheets/detail/healthy-diet",
            "https://www.nhs.uk/conditions/type-2-diabetes/food-and-keeping-active/",
            "https://www.niddk.nih.gov/health-information/diabetes/overview/diet-eating-physical-activity",
        ],
    },
    {
        "id": "avoid_trans_fat_v1",
        "title": "Trans fats from vanaspati and bakery shortening",
        "detail": (
            "Raised LDL or triglycerides respond strongly to removing industrial trans fat. "
            "WHO calls for trans fat below 1% of energy, so these are the first items to drop "
            "rather than reduce."
        ),
        "severity": "avoid",
        "conditions": ["dyslipidaemia", "coronary_artery_disease", "stroke"],
        "labs": [
            {"key": "ldl_cholesterol_mg_dl", "op": ">=", "value": 130},
            {"key": "triglycerides_mg_dl", "op": ">=", "value": 150},
        ],
        "items": [
            {
                "label": "Vanaspati, dalda and bakery shortening",
                "examples": [
                    "vanaspati ghee",
                    "puff pastry and khari",
                    "bakery biscuits",
                    "cream-filled cakes",
                    "reheated frying oil",
                ],
                "reason": (
                    "Partially hydrogenated fats are the main source of industrial trans fat, "
                    "which raises LDL cholesterol."
                ),
                "linked_nutrients": ["saturated_fat_g", "fat_g"],
            }
        ],
        "confidence": "established",
        "sources": [
            "https://www.who.int/news-room/fact-sheets/detail/trans-fat",
            "https://www.heart.org/en/healthy-living/healthy-eating/eat-smart/fats/trans-fat",
        ],
    },
    {
        "id": "limit_saturated_fat_foods_v1",
        "title": "Deep-fried snacks and processed meats",
        "detail": (
            "A raised LDL or triglyceride reading is also a reason to reduce saturated fat. "
            "These foods carry both saturated fat and a lot of salt, so reducing them helps "
            "two targets at once."
        ),
        "severity": "limit",
        "conditions": ["dyslipidaemia", "coronary_artery_disease", "type_2_diabetes"],
        "labs": [
            {"key": "ldl_cholesterol_mg_dl", "op": ">=", "value": 130},
            {"key": "triglycerides_mg_dl", "op": ">=", "value": 150},
        ],
        "items": [
            {
                "label": "Deep-fried snacks",
                "examples": ["samosa", "pakora", "vada", "fried chicken", "fried chips"],
                "reason": (
                    "Deep frying adds fat, much of it saturated, and the snack is usually "
                    "salted as well."
                ),
                "linked_nutrients": ["saturated_fat_g", "fat_g", "sodium_mg"],
            },
            {
                "label": "Processed meats",
                "examples": ["sausages", "salami", "bacon", "ham", "canned meats"],
                "reason": "Processed meats are high in saturated fat and salt.",
                "linked_nutrients": ["saturated_fat_g", "sodium_mg"],
            },
            {
                "label": "Butter, ghee and cream-heavy cooking",
                "examples": ["butter on bread", "ghee-rich gravies", "malai dishes"],
                "reason": "These are concentrated saturated fat sources used in everyday cooking.",
                "linked_nutrients": ["saturated_fat_g", "fat_g"],
            },
        ],
        "confidence": "established",
        "sources": [
            "https://www.who.int/news-room/fact-sheets/detail/healthy-diet",
            "https://www.nin.res.in/downloads/DietaryGuidelinesforNINwebsite.pdf",
        ],
    },
    {
        "id": "limit_sodium_high_bp_v1",
        "title": "High-salt foods that push blood pressure up",
        "detail": (
            "A raised blood pressure reading is a reason to cut sodium. Most sodium comes from "
            "packaged and restaurant food rather than the salt shaker, so these items are "
            "usually the biggest contributors."
        ),
        "severity": "limit",
        "conditions": ["hypertension", "heart_failure", "stroke"],
        "labs": [
            {"key": "systolic_bp_mmhg", "op": ">=", "value": 130},
            {"key": "diastolic_bp_mmhg", "op": ">=", "value": 80},
        ],
        "items": [
            {
                "label": "Pickles and papad",
                "examples": ["mango pickle", "lime pickle", "achaar", "papad", "vathal"],
                "reason": "These are preserved with large amounts of salt.",
                "linked_nutrients": ["sodium_mg"],
            },
            {
                "label": "Namkeen and salted snacks",
                "examples": ["bhujia", "chips", "salted nuts", "sev", "mixture"],
                "reason": "Salted snacks pack a lot of sodium into a small portion.",
                "linked_nutrients": ["sodium_mg"],
            },
            {
                "label": "Instant noodles and their taste-maker sachet",
                "examples": [
                    "instant noodles",
                    "the seasoning sachet",
                    "ready soups",
                    "stock cubes",
                ],
                "reason": ("One sachet can carry a large share of a day's sodium on its own."),
                "linked_nutrients": ["sodium_mg"],
            },
            {
                "label": "Processed cheese and cheese spreads",
                "examples": ["cheese slices", "cheese spread", "cheese powder in snacks"],
                "reason": ("Processed cheese is salted and often carries phosphate additives too."),
                "linked_nutrients": ["sodium_mg", "phosphorus_mg"],
            },
            {
                "label": "Soy, chilli and tomato sauces",
                "examples": ["soy sauce", "chilli sauce", "ketchup", "readymade gravies"],
                "reason": "Sauces are concentrated salt sources used in small volumes.",
                "linked_nutrients": ["sodium_mg"],
            },
        ],
        "confidence": "established",
        "sources": [
            "https://www.who.int/news-room/fact-sheets/detail/salt-reduction",
            "https://www.cdc.gov/salt/about/index.html",
            "https://www.nin.res.in/downloads/DietaryGuidelinesforNINwebsite.pdf",
        ],
    },
    {
        "id": "avoid_potassium_chloride_salt_substitute_v1",
        "title": "Salt substitutes that contain potassium chloride",
        "detail": (
            "When kidney function is reduced or blood potassium is raised, 'low sodium' salts "
            "that use potassium chloride can push blood potassium up. Ask your clinician "
            "before using any salt substitute."
        ),
        "severity": "avoid",
        "conditions": ["ckd", "hyperkalaemia"],
        "labs": [
            {"key": "egfr_ml_min", "op": "<", "value": 60},
            {"key": "potassium_meq_l", "op": ">=", "value": 5.0},
        ],
        "items": [
            {
                "label": "Salt substitutes made with potassium chloride",
                "examples": [
                    "'low sodium' salt",
                    "potassium chloride seasoning",
                    "salt-free salt blends",
                ],
                "reason": (
                    "Their potassium is absorbed and can accumulate when the kidneys clear it "
                    "poorly, which is exactly the situation these products are sold for."
                ),
                "linked_nutrients": ["potassium_mg", "sodium_mg"],
            }
        ],
        "confidence": "established",
        "sources": [
            "https://www.kidney.org/kidney-topics/potassium-your-ckd-diet",
            "https://www.niddk.nih.gov/health-information/kidney-disease/chronic-kidney-disease-ckd/eating-nutrition",
        ],
    },
    {
        "id": "ask_high_potassium_foods_v1",
        "title": "High-potassium foods to review with your clinician",
        "detail": (
            "Raised blood potassium or reduced kidney function means potassium sources need "
            "individual advice. This list is for that conversation: potassium is also a "
            "needed nutrient, so it is not a list to cut on your own."
        ),
        "severity": "ask",
        "conditions": ["ckd", "hyperkalaemia"],
        "labs": [
            {"key": "potassium_meq_l", "op": ">=", "value": 5.0},
            {"key": "egfr_ml_min", "op": "<", "value": 60},
        ],
        "items": [
            {
                "label": "Potassium-rich fruits and juices",
                "examples": [
                    "bananas",
                    "oranges and orange juice",
                    "coconut water",
                    "dried fruits",
                ],
                "reason": "These are concentrated potassium sources.",
                "linked_nutrients": ["potassium_mg"],
            },
            {
                "label": "Potassium-rich vegetables and pulses",
                "examples": ["potatoes", "tomatoes", "spinach", "rajma and chana", "sambar"],
                "reason": (
                    "Plant foods carry potassium, and portion size and cooking method change "
                    "how much you get."
                ),
                "linked_nutrients": ["potassium_mg"],
            },
        ],
        "confidence": "clinician_only",
        "sources": [
            "https://www.kidney.org/kidney-topics/potassium-your-ckd-diet",
            "https://www.niddk.nih.gov/-/media/Files/Health-Information/Health-Professionals/Kidney-Disease/PotassiumTipsforPeopleCKD_EN.pdf",
        ],
    },
    {
        "id": "ask_phosphate_additives_v1",
        "title": "Phosphate additives to review with your clinician",
        "detail": (
            "Raised blood phosphate or reduced kidney function makes added phosphate worth "
            "reviewing. Additives are absorbed far more completely than the phosphate "
            "naturally present in food, so they are the usual first question."
        ),
        "severity": "ask",
        "conditions": ["ckd", "hyperphosphataemia"],
        "labs": [
            {"key": "phosphorus_mg_dl", "op": ">=", "value": 4.5},
            {"key": "egfr_ml_min", "op": "<", "value": 60},
        ],
        "items": [
            {
                "label": "Cola drinks",
                "examples": ["cola", "diet cola", "cola-based mixers"],
                "reason": "Cola drinks contain phosphoric acid as an additive.",
                "linked_nutrients": ["phosphorus_mg"],
            },
            {
                "label": "Processed cheese",
                "examples": ["cheese slices", "cheese spread", "cheese powder in snacks"],
                "reason": "Emulsifying salts used in processed cheese add phosphate.",
                "linked_nutrients": ["phosphorus_mg", "sodium_mg"],
            },
            {
                "label": "Packaged baked goods with phosphate additives",
                "examples": [
                    "cake mixes",
                    "instant puddings",
                    "packaged biscuits",
                    "self-raising flour blends",
                ],
                "reason": (
                    "Phosphate-based raising and stabilising agents add phosphate that is "
                    "absorbed rather than passed through."
                ),
                "linked_nutrients": ["phosphorus_mg"],
            },
        ],
        "confidence": "clinician_only",
        "sources": [
            "https://www.kidney.org/kidney-topics/phosphorus-and-your-ckd-diet",
            "https://www.niddk.nih.gov/health-information/kidney-disease/chronic-kidney-disease-ckd/eating-nutrition",
        ],
    },
    {
        "id": "avoid_gout_alcohol_organ_meats_v1",
        "title": "Alcohol and organ meats",
        "detail": (
            "Raised uric acid or gout responds to cutting the strongest purine and alcohol "
            "sources. Beer and organ meats carry the largest effect, so they are listed as "
            "avoid rather than limit."
        ),
        "severity": "avoid",
        "conditions": ["gout"],
        "labs": [{"key": "uric_acid_mg_dl", "op": ">=", "value": 7.0}],
        "items": [
            {
                "label": "Organ meats",
                "examples": ["liver", "kidney", "brain", "sweetbreads"],
                "reason": "Organ meats are the most purine-dense foods.",
                "linked_nutrients": [],
            },
            {
                "label": "Beer and other alcohol",
                "examples": ["beer", "spirits", "wine", "cocktails"],
                "reason": ("Alcohol raises uric acid and beer adds purines from yeast as well."),
                "linked_nutrients": [],
            },
        ],
        "confidence": "established",
        "sources": [
            "https://www.mayoclinic.org/healthy-lifestyle/nutrition-and-healthy-eating/in-depth/gout-diet/art-20048524",
            "https://www.hopkinsmedicine.org/health/expert-qa/gout-diet-what-to-eat-and-what-to-avoid",
        ],
    },
    {
        "id": "limit_gout_purines_fructose_v1",
        "title": "Red meat, shellfish and fructose-sweetened drinks",
        "detail": (
            "These raise uric acid less than alcohol or organ meats but still matter when the "
            "level is high. Reduce them steadily rather than all at once."
        ),
        "severity": "limit",
        "conditions": ["gout"],
        "labs": [{"key": "uric_acid_mg_dl", "op": ">=", "value": 7.0}],
        "items": [
            {
                "label": "Red meat",
                "examples": ["beef", "mutton", "pork", "game meats"],
                "reason": "Red meat is a moderate purine source.",
                "linked_nutrients": ["protein_g"],
            },
            {
                "label": "Shellfish",
                "examples": ["prawns", "crab", "mussels", "shellfish curries"],
                "reason": "Shellfish is a moderate-to-high purine source.",
                "linked_nutrients": ["protein_g"],
            },
            {
                "label": "Fructose-sweetened drinks",
                "examples": ["soft drinks", "sweetened fruit drinks", "packaged iced tea"],
                "reason": "Fructose raises uric acid production in the body.",
                "linked_nutrients": ["sugars_g"],
            },
        ],
        "confidence": "established",
        "sources": [
            "https://www.mayoclinic.org/healthy-lifestyle/nutrition-and-healthy-eating/in-depth/gout-diet/art-20048524",
            "https://www.hopkinsmedicine.org/health/expert-qa/gout-diet-what-to-eat-and-what-to-avoid",
        ],
    },
    {
        "id": "limit_anaemia_absorption_blockers_v1",
        "title": "Tea, coffee and calcium at the same meal",
        "detail": (
            "A low haemoglobin value with iron deficiency means iron absorption matters. These "
            "are not foods to remove, only to keep away from iron-rich meals."
        ),
        "severity": "limit",
        "conditions": ["iron_deficiency_anaemia"],
        "labs": [{"key": "hemoglobin_g_dl", "op": "below_ref", "value": None}],
        "items": [
            {
                "label": "Tea and coffee with meals",
                "examples": [
                    "strong tea with meals",
                    "coffee with meals",
                    "tea right after eating",
                ],
                "reason": (
                    "Polyphenols in tea and coffee reduce how much iron is absorbed from the "
                    "same meal."
                ),
                "linked_nutrients": ["iron"],
            },
            {
                "label": "Calcium supplements with iron-rich meals",
                "examples": ["calcium tablets at mealtime", "calcium-fortified drinks with meals"],
                "reason": "Calcium competes with iron for absorption at the same meal.",
                "linked_nutrients": ["iron", "calcium"],
            },
        ],
        "confidence": "general_wellbeing",
        "sources": [
            "https://www.nhs.uk/conditions/iron-deficiency-anaemia/",
            "https://ods.od.nih.gov/factsheets/Iron-Consumer/",
        ],
    },
    {
        "id": "ask_b12_fortified_foods_v1",
        "title": "Fortified foods and B12 treatment",
        "detail": (
            "There is no food to avoid for a low B12 result. The real question is how the "
            "deficiency will be corrected, which is decided by your clinician."
        ),
        "severity": "ask",
        "conditions": ["vitamin_b12_deficiency"],
        "labs": [{"key": "vitamin_b12_pg_ml", "op": "<", "value": 200}],
        "items": [
            {
                "label": "Fortified foods",
                "examples": [
                    "fortified breakfast cereals",
                    "fortified plant milks",
                    "nutritional yeast",
                ],
                "reason": (
                    "Fortified foods can help but may not be enough for a deficiency; ask what "
                    "fits your level."
                ),
                "linked_nutrients": ["vitamin_b12"],
            },
            {
                "label": "B12 injections or tablets",
                "examples": ["prescribed B12 injections", "prescribed oral B12"],
                "reason": (
                    "Treatment is prescribed and monitored, so do not self-dose or buy "
                    "high-dose products."
                ),
                "linked_nutrients": ["vitamin_b12"],
            },
        ],
        "confidence": "clinician_only",
        "sources": [
            "https://www.nhs.uk/conditions/vitamin-b12-or-folate-deficiency-anaemia/",
            "https://ods.od.nih.gov/factsheets/VitaminB12-Consumer/",
        ],
    },
    {
        "id": "ask_vitamin_d_supplement_v1",
        "title": "Vitamin D supplement dose",
        "detail": (
            "A low vitamin D level is treated with a dose your clinician sets. There is no "
            "food to avoid, and taking a large dose on your own can be harmful."
        ),
        "severity": "ask",
        "conditions": ["vitamin_d_deficiency", "osteoporosis"],
        "labs": [{"key": "vitamin_d_ng_ml", "op": "<", "value": 20}],
        "items": [
            {
                "label": "Vitamin D supplement dose",
                "examples": ["a daily vitamin D supplement", "a prescribed loading course"],
                "reason": (
                    "The dose and duration depend on your blood level and are set by your "
                    "clinician; large doses taken without advice can be harmful."
                ),
                "linked_nutrients": ["vitamin_d", "calcium"],
            },
            {
                "label": "Sun exposure and food sources",
                "examples": ["short daily sun exposure", "fortified foods", "oily fish"],
                "reason": (
                    "Food and sun rarely correct a deficiency alone, so ask how they fit with "
                    "your treatment."
                ),
                "linked_nutrients": ["vitamin_d"],
            },
        ],
        "confidence": "clinician_only",
        "sources": [
            "https://www.nhs.uk/conditions/vitamins-and-minerals/vitamin-d/",
            "https://ods.od.nih.gov/factsheets/VitaminD-Consumer/",
        ],
    },
    {
        "id": "ask_hypothyroidism_iodine_v1",
        "title": "Iodine and selenium sources",
        "detail": (
            "A raised TSH with treated hypothyroidism raises questions about iodine and "
            "selenium. This app does not claim that avoiding so-called goitrogenic vegetables "
            "helps, and it does not suggest iodine supplements."
        ),
        "severity": "ask",
        "conditions": ["hypothyroidism"],
        "labs": [{"key": "tsh_miu_l", "op": ">", "value": 4.5}],
        "items": [
            {
                "label": "Iodine-rich foods and supplements",
                "examples": ["iodised salt", "seaweed and kelp", "iodine supplements"],
                "reason": (
                    "Both too little and too much iodine can affect the thyroid, so ask what "
                    "fits your treatment."
                ),
                "linked_nutrients": ["iodine"],
            },
            {
                "label": "Selenium sources",
                "examples": ["Brazil nuts", "seafood", "eggs"],
                "reason": (
                    "Selenium is involved in thyroid hormone handling, but supplements are not "
                    "a substitute for your prescribed treatment."
                ),
                "linked_nutrients": [],
            },
        ],
        "confidence": "clinician_only",
        "sources": [
            "https://www.nhs.uk/conditions/underactive-thyroid-hypothyroidism/",
            "https://ods.od.nih.gov/factsheets/Iodine-Consumer/",
        ],
    },
]

AVOID_RULE_BY_ID = {rule["id"]: rule for rule in AVOID_RULES}


# --- Plan construction -------------------------------------------------------------------


def _report_parameters(reports):
    """Yield (report, parameter) for confirmed reports only, plus the excluded count."""
    confirmed: list[tuple[dict, dict]] = []
    excluded = 0
    for report in reports:
        if report.get("status", "confirmed") != "confirmed":
            excluded += 1
            continue
        for parameter in report.get("parameters", []) or []:
            confirmed.append((report, parameter))
    return confirmed, excluded


def _lab_evidence(report: dict, parameter: dict) -> dict:
    label = parameter.get("label") or parameter.get("key") or "Lab parameter"
    value = parameter.get("value")
    unit = parameter.get("unit")
    detail = f"{label} {value}{(' ' + unit) if unit else ''}".strip()
    reference = ""
    if parameter.get("reference_low") is not None or parameter.get("reference_high") is not None:
        reference = (
            f" · reference {parameter.get('reference_low')}-{parameter.get('reference_high')}"
        )
    collected = report.get("collected_on")
    return {
        "kind": "lab",
        "label": label,
        "detail": (
            f"Confirmed report {'of ' + collected if collected else ''}: {detail}{reference}"
        ).strip(),
        "parameter_key": parameter.get("key"),
        "value": value,
        "unit": unit,
        "reference_low": parameter.get("reference_low"),
        "reference_high": parameter.get("reference_high"),
        "measured_on": report.get("collected_on"),
        "report_id": report.get("id"),
    }


def _trigger_matches(trigger: dict, parameter: dict, sex: str) -> tuple[bool, str | None]:
    """Resolve one lab trigger to a concrete comparison.

    ``below_ref`` reads the sex-aware low-reference table, so a haemoglobin of 11.5 g/dL
    fires for a female profile (low 12.0) and not for a value at or above the threshold;
    when sex is unspecified the widened low bound is used and the note says so.
    """
    if trigger["op"] == "below_ref":
        threshold, note = low_reference(trigger["key"], sex)
        if threshold is None:
            return False, None
        return compare("<", float(parameter["value"]), float(threshold)), note
    return compare(trigger["op"], float(parameter["value"]), float(trigger["value"])), None


def _matched_labs(rule: dict, confirmed_params, sex: str) -> list[tuple[dict, dict, str | None]]:
    """Every (report, parameter, widened-note) that satisfies one lab trigger of the rule."""
    matches = []
    for trigger in rule.get("labs", []):
        key = trigger["key"]
        for report, parameter in confirmed_params:
            if parameter.get("key") != key or parameter.get("value") is None:
                continue
            matched, note = _trigger_matches(trigger, parameter, sex)
            if matched:
                matches.append((report, parameter, note))
    return matches


def _suggested_source(rule: dict, lab_evidence, condition_labels) -> str:
    parts: list[str] = []
    if lab_evidence:
        first = lab_evidence[0]
        stamp = first["detail"]
        # Keep the value/units; the kind prefix is dropped for a compact source string.
        stamp = stamp.replace("Confirmed report of ", "").replace("Confirmed report:", "").strip()
        stamp = stamp.split(" · reference")[0].strip()
        parts.append(f"Report {stamp}")
    elif condition_labels:
        parts.append(f"Profile condition {condition_labels[0]}")
    parts.append(f"rule {rule['id']}")
    parts.append("confirmed by you")
    text = " \u00b7 ".join(parts)
    return text[:200]


# The arithmetic a person can check: which measurement, which threshold, which ceiling.

_COMPARATOR_PHRASES = {
    ">=": "is at or above",
    ">": "is above",
    "<=": "is at or below",
    "<": "is below",
}


def _trigger_for(rule: dict, parameter_key: str | None) -> dict | None:
    """The trigger of ``rule`` that reads this lab key, if any."""
    for trigger in rule.get("labs", []):
        if trigger["key"] == parameter_key:
            return trigger
    return None


def _measurement_clause(item: dict, trigger: dict | None, sex: str) -> str:
    """'Systolic blood pressure 138 mmHg is at or above 130 mmHg' from one evidence row."""
    label = item.get("label") or item.get("parameter_key") or "Measurement"
    unit = f" {item['unit']}" if item.get("unit") else ""
    stamped = f"{label} {_format_value(item.get('value'))}{unit}".strip()
    if trigger is None:
        return stamped
    if trigger["op"] == "below_ref":
        threshold, _note = low_reference(trigger["key"], sex)
        if threshold is None:
            return stamped
        return f"{stamped} is below the low reference of {_format_value(threshold)}{unit}"
    phrase = _COMPARATOR_PHRASES.get(trigger["op"])
    if phrase is None:
        return stamped
    return f"{stamped} {phrase} {_format_value(trigger['value'])}{unit}"


def _derivation(
    nutrient: str,
    winning_rule: dict,
    evidence: list[dict],
    condition_labels: list[str],
    proposed: float | None,
    confidence: str,
    sex: str,
) -> str:
    """One sentence naming the measurement, the threshold and the resulting ceiling."""
    meta = NUTRIENT_META[nutrient]
    label = meta["label"].lower()
    lab_items = [item for item in evidence if item["kind"] == "lab"]
    item = next(
        (
            candidate
            for candidate in lab_items
            if _trigger_for(winning_rule, candidate.get("parameter_key")) is not None
        ),
        lab_items[0] if lab_items else None,
    )
    if item is not None:
        clause = _measurement_clause(
            item, _trigger_for(winning_rule, item.get("parameter_key")), sex
        )
    elif condition_labels:
        clause = f"Recorded condition {condition_labels[0]}"
    else:
        clause = f"{meta['label']} reference"

    if confidence == "clinician_only":
        return f"{clause} \u2192 a {label} ceiling must be set by your clinician, not by this app"
    if proposed is None:
        return f"{clause} \u2192 no daily {label} number is proposed here"

    if winning_rule["direction"] == "higher":
        result = f"{label} floor {_format_value(proposed)} {meta['unit']}/day"
    else:
        result = f"{label} ceiling {_format_value(proposed)} {meta['unit']}/day"
    phrases = _display_phrases(nutrient, proposed)
    if phrases:
        result = f"{result} (" + "; ".join(f"\u2248{phrase}" for phrase in phrases) + ")"
    return f"{clause} \u2192 {result}"


def _measured(evidence: list[dict]) -> list[dict]:
    """The raw confirmed report values behind a target, in the order they arrived."""
    return _dedupe_evidence([item for item in evidence if item["kind"] == "lab"])


def _build_target(nutrient, merged_rules, baseline_value, baseline_notes, evidence, sex) -> dict:
    meta = NUTRIENT_META[nutrient]
    # Only a rule whose confidence is ``clinician_only`` suppresses the number: those are the
    # nutrients a clinician must set (CKD potassium/phosphorus/protein, hyperkalaemia,
    # hyperphosphataemia). ``requires_clinician`` alone is a flag on a real proposal — a
    # diabetes sugar ceiling still shows its value and asks for clinician confirmation.
    clinician_only = [rule for rule in merged_rules if rule["confidence"] == "clinician_only"]
    numeric = [rule for rule in merged_rules if rule["proposed_value"] is not None]
    directions = {rule["direction"] for rule in merged_rules}
    if clinician_only:
        winning = clinician_only[0]
        proposed = None
        requires_clinician = True
        confidence = "clinician_only"
    elif numeric:
        # Strictest target: the lowest ceiling for "lower", the highest floor for "higher".
        if directions == {"higher"}:
            winning = max(numeric, key=lambda r: r["proposed_value"])
        else:
            winning = min(numeric, key=lambda r: r["proposed_value"])
        proposed = winning["proposed_value"]
        requires_clinician = any(rule["requires_clinician"] for rule in merged_rules)
        confidence = winning["confidence"]
    else:
        winning = merged_rules[0]
        proposed = None
        requires_clinician = False
        confidence = winning["confidence"]

    direction = winning["direction"]
    basis_parts = []
    for note in baseline_notes:
        basis_parts.append(note.capitalize())
    basis_parts.extend(rule["basis"] for rule in merged_rules)
    basis_parts.append(
        "This is a proposal, not a recorded limit: no number is stored until you confirm it "
        "and save your profile."
    )
    if len(merged_rules) > 1:
        basis_parts.append(
            "Merged rules on this nutrient: " + ", ".join(rule["id"] for rule in merged_rules) + "."
        )
    if any(rule["requires_clinician"] for rule in merged_rules):
        basis_parts.append("At least one rule requires a clinician to set the value.")
    questions = list(dict.fromkeys(q for rule in merged_rules for q in rule["questions"]))

    condition_labels = []
    for item in evidence:
        if item["kind"] == "condition" and item["label"] not in condition_labels:
            condition_labels.append(item["label"])

    baseline_evidence = {
        "kind": "baseline",
        "label": meta["label"],
        "detail": f"Baseline reference: {meta['basis']}",
        "parameter_key": None,
        "value": baseline_value,
        "unit": meta["unit"],
        "reference_low": None,
        "reference_high": None,
        "measured_on": None,
        "report_id": None,
    }
    # A clinician-only nutrient shows no number at all — not even a converted one — because
    # any figure would read as advice. Other targets state the ceiling in the units people
    # use and print the arithmetic that produced it.
    display = None
    equivalents: list[dict] = []
    if proposed is not None:
        display = display_value(nutrient, proposed)
        equivalents = equivalents_for(nutrient, proposed)
    derivation = _derivation(
        nutrient, winning, evidence, condition_labels, proposed, confidence, sex
    )
    return {
        "nutrient": nutrient,
        "label": meta["label"],
        "unit": meta["unit"],
        "baseline_value": baseline_value,
        "baseline_source": meta["source"],
        "proposed_value": proposed,
        "direction": direction,
        "rule_id": winning["id"],
        "basis": " ".join(basis_parts),
        "confidence": confidence,
        "requires_clinician": requires_clinician,
        "evidence": [baseline_evidence, *evidence],
        "questions": questions[:6],
        "limit_scope": "daily",
        "suggested_limit_source": _suggested_source(
            winning, [e for e in evidence if e["kind"] == "lab"], condition_labels
        ),
        "display_value": display,
        "equivalents": equivalents,
        "derivation": derivation,
        "measured": _measured(evidence),
    }


def build_plan(profile: ProfileData, reports) -> dict:
    """Build the ``IntakePlan`` payload. Pure: no storage access, no profile write."""
    recognised, unrecognised = resolve_conditions(profile.conditions)
    confirmed_params, excluded_reports = _report_parameters(reports)

    condition_evidence: dict[str, dict] = {}
    for slug in recognised:
        info = condition_info(slug)
        if info is None:
            continue
        condition_evidence[slug] = {
            "kind": "condition",
            "label": info["label"],
            "detail": f"Recorded condition: {info['label']} ({info['category']}).",
            "parameter_key": None,
            "value": None,
            "unit": None,
            "reference_low": None,
            "reference_high": None,
            "measured_on": None,
            "report_id": None,
        }

    fired: dict[str, dict] = {}
    fired_evidence: dict[str, list[dict]] = {}
    for rule in RULES:
        matched_condition_slugs = [
            slug for slug in rule["conditions"] if slug in condition_evidence
        ]
        lab_matches = _matched_labs(rule, confirmed_params, profile.sex)
        if not matched_condition_slugs and not lab_matches:
            continue
        nutrient = rule["nutrient"]
        fired.setdefault(nutrient, []).append(rule)

        evidence: list[dict] = []
        for slug in matched_condition_slugs:
            evidence.append(condition_evidence[slug])
        for report, parameter, note in lab_matches:
            item = _lab_evidence(report, parameter)
            if note:
                item["detail"] = f"{item['detail']} · {note}"
            evidence.append(item)
        bucket = fired_evidence.setdefault(nutrient, [])
        bucket_keys = {_evidence_key(existing) for existing in bucket}
        for item in _dedupe_evidence(evidence):
            if _evidence_key(item) not in bucket_keys:
                bucket_keys.add(_evidence_key(item))
                bucket.append(item)

    targets = []
    for nutrient, rules in fired.items():
        baseline_value, notes = resolve_baseline(nutrient, profile.sex, profile.age_band)
        targets.append(
            _build_target(
                nutrient, rules, baseline_value, notes, fired_evidence[nutrient], profile.sex
            )
        )

    # Avoid groups use the same trigger machinery as the targets: a group appears only when
    # its own lab comparator or condition slug matched, and it carries exactly that evidence.
    avoid: list[dict] = []
    for rule in AVOID_RULES:
        matched_condition_slugs = [
            slug for slug in rule["conditions"] if slug in condition_evidence
        ]
        lab_matches = _matched_labs(rule, confirmed_params, profile.sex)
        if not matched_condition_slugs and not lab_matches:
            continue
        evidence: list[dict] = []
        for slug in matched_condition_slugs:
            evidence.append(condition_evidence[slug])
        for report, parameter, note in lab_matches:
            item = _lab_evidence(report, parameter)
            if note:
                item["detail"] = f"{item['detail']} · {note}"
            evidence.append(item)
        avoid.append(
            {
                "id": rule["id"],
                "title": rule["title"],
                "detail": rule["detail"],
                "severity": rule["severity"],
                "items": rule["items"],
                "confidence": rule["confidence"],
                "sources": rule["sources"],
                "evidence": _dedupe_evidence(evidence),
            }
        )

    plans = []
    for slug in recognised:
        info = condition_info(slug)
        if info is not None:
            plans.append(info)

    notes: list[str] = []
    if excluded_reports:
        notes.append(
            f"{excluded_reports} extracted report(s) were held back because they are not "
            "confirmed; confirm a report before its values can drive a proposal."
        )
    if not confirmed_params:
        notes.append(
            "No confirmed health report was available, so only recorded conditions and "
            "general baselines produced these proposals."
        )
    if any(WIDE_SEX_NOTE in target["basis"] for target in targets):
        notes.append("Sex was unspecified, so wider reference ranges were used and are stated.")
    if any(WIDE_AGE_NOTE in target["basis"] for target in targets):
        notes.append("Age band was unspecified, so a wider reference range was kept and stated.")
    if not targets:
        notes.append(
            "No rule matched, so no nutrient target is proposed; recorded limits remain the "
            "only source of your personal numbers."
        )
    if avoid:
        notes.append(
            "The avoid list covers only the foods linked to the confirmed values and recorded "
            "conditions above; a food that is not listed is not a statement that it is safe "
            "for you. Items marked ask are for a conversation with the kitchen or a clinician."
        )

    return {
        "version": INTAKE_VERSION,
        "targets": targets,
        "avoid": avoid,
        "conditions": plans,
        "unrecognised_conditions": unrecognised,
        "reports_used": list(
            dict.fromkeys(report.get("id") for report, _ in confirmed_params if report.get("id"))
        ),
        "notes": notes,
        "coverage": (
            "Proposals only. Recording a limit remains the effect of saving your profile; a "
            "selected condition or a report value never becomes a limit by itself."
        ),
    }


def conditions_context(profile: ProfileData) -> tuple[list[dict], list[str]]:
    """Registry detail for the guide: (resolved ConditionInfo list, unrecognised list)."""
    recognised, unrecognised = resolve_conditions(profile.conditions)
    infos = [info for slug in recognised if (info := condition_info(slug)) is not None]
    return infos, unrecognised
