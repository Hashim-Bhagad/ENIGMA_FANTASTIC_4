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

from app.schemas import ProfileData
from app.services.conditions import condition_info, resolve_conditions

INTAKE_VERSION = "intake-2026-09-26.1"

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
        "report_id": report.get("id"),
    }


def _matched_labs(rule: dict, confirmed_params, sex: str) -> list[tuple[dict, dict, str | None]]:
    """Every (report, parameter, widened-note) that satisfies one lab trigger of the rule."""
    matches = []
    for trigger in rule.get("labs", []):
        key = trigger["key"]
        for report, parameter in confirmed_params:
            if parameter.get("key") != key or parameter.get("value") is None:
                continue
            note = None
            if trigger["op"] == "below_ref":
                threshold, note = low_reference(key, sex)
                if threshold is None:
                    continue
            else:
                threshold = trigger["value"]
            if compare(trigger["op"], float(parameter["value"]), float(threshold)):
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


def _build_target(nutrient, merged_rules, baseline_value, baseline_notes, evidence) -> dict:
    meta = NUTRIENT_META[nutrient]
    clinician = [rule for rule in merged_rules if rule["requires_clinician"]]
    numeric = [rule for rule in merged_rules if rule["proposed_value"] is not None]
    directions = {rule["direction"] for rule in merged_rules}
    if clinician:
        winning = clinician[0]
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
        requires_clinician = False
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
        "report_id": None,
    }
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
            "report_id": None,
        }

    fired: dict[str, dict] = {}
    fired_evidence: dict[str, list[dict]] = {}
    for rule in RULES:
        matched_condition_slugs = [slug for slug in rule["conditions"] if slug in condition_evidence]
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
        existing_keys = {(e["kind"], e["label"], e.get("report_id"), e.get("value")) for e in bucket}
        for item in evidence:
            key = (item["kind"], item["label"], item.get("report_id"), item.get("value"))
            if key not in existing_keys:
                existing_keys.add(key)
                bucket.append(item)

    targets = []
    for nutrient, rules in fired.items():
        baseline_value, notes = resolve_baseline(nutrient, profile.sex, profile.age_band)
        targets.append(
            _build_target(nutrient, rules, baseline_value, notes, fired_evidence[nutrient])
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

    return {
        "version": INTAKE_VERSION,
        "targets": targets,
        "conditions": plans,
        "unrecognised_conditions": unrecognised,
        "reports_used": list(
            dict.fromkeys(
                report.get("id") for report, _ in confirmed_params if report.get("id")
            )
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
