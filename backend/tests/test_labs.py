"""Deterministic contract of the lab registry: names, units, ranges and statuses.

Everything here is pure code: a stored status must always be reproducible from the
stored value and range, with no provider involved.
"""

import pytest

from app.services.labs import (
    CANONICAL_KEYS,
    LAB_REGISTRY,
    build_parameters,
    canonicalise,
    classify,
    convert,
    reference_range,
)

# One printed name per family of forms: abbreviations, Indian lab forms and qualifiers.
ALIAS_CASES = [
    ("Hb", "hemoglobin_g_dl"),
    ("HB CONCENTRATION", "hemoglobin_g_dl"),
    ("S. Cholesterol", "total_cholesterol_mg_dl"),
    ("TLC", "wbc_thousand_ul"),
    ("FBS", "fasting_glucose_mg_dl"),
    ("Blood Sugar Random", "random_glucose_mg_dl"),
    ("S. Ferritin", "ferritin_ng_ml"),
    ("25-OH Vitamin D", "vitamin_d_ng_ml"),
    ("Glycated Haemoglobin", "hba1c_percent"),
    ("Serum Creatinine", "creatinine_mg_dl"),
    ("PPBS", "random_glucose_mg_dl"),
    ("Haemoglobin", "hemoglobin_g_dl"),
]

# (canonical key, from unit, to unit, printed value, expected value, tolerance).
CONVERSION_CASES = [
    ("fasting_glucose_mg_dl", "mg/dL", "mmol/L", 90.0, 4.995, 1e-3),
    ("total_cholesterol_mg_dl", "mg/dL", "mmol/L", 200.0, 5.172, 1e-3),
    ("triglycerides_mg_dl", "mg/dL", "mmol/L", 150.0, 1.6936, 1e-3),
    ("creatinine_mg_dl", "mg/dL", "umol/L", 1.0, 88.4, 1e-3),
    ("hemoglobin_g_dl", "g/dL", "g/L", 14.0, 140.0, 1e-6),
    ("vitamin_d_ng_ml", "ng/mL", "nmol/L", 30.0, 75.0, 1e-6),
    ("vitamin_b12_pg_ml", "pg/mL", "pmol/L", 500.0, 369.004, 1e-3),
    ("uric_acid_mg_dl", "mg/dL", "umol/L", 5.0, 297.62, 1e-3),
]


def test_canonical_vocabulary_is_frozen_and_fully_registered():
    assert set(LAB_REGISTRY) == set(CANONICAL_KEYS)
    assert len(CANONICAL_KEYS) == 38
    assert len(set(CANONICAL_KEYS)) == 38
    for key in CANONICAL_KEYS:
        entry = LAB_REGISTRY[key]
        assert set(entry) >= {"label", "unit", "aliases", "bounds", "ranges", "source"}
        assert entry["label"] and entry["unit"]
        low, high = entry["bounds"]
        assert low < high
        assert entry["source"].startswith("https://")


@pytest.mark.parametrize(("printed", "key"), ALIAS_CASES)
def test_printed_names_map_to_their_canonical_key(printed, key):
    assert canonicalise(printed) == key


def test_unknown_names_and_empty_input_stay_unrecognised():
    assert canonicalise("Vitamin E") is None
    assert canonicalise("") is None
    assert canonicalise(None) is None


@pytest.mark.parametrize(
    ("key", "unit", "target", "value", "expected", "tolerance"), CONVERSION_CASES
)
def test_each_conversion_pair_converts_and_round_trips(
    key, unit, target, value, expected, tolerance
):
    converted = convert(value, unit, target, key)
    assert converted == pytest.approx(expected, rel=tolerance)
    assert convert(converted, target, unit, key) == pytest.approx(value, rel=1e-6)


def test_the_same_unit_pair_never_borrows_another_analytes_factors():
    # mg/dL and mmol/L belong to glucose, cholesterol and triglycerides at once, so the
    # key decides: 200 mg/dL of cholesterol is 5.17 mmol/L, not the glucose result.
    assert convert(200.0, "mg/dL", "mmol/L", "total_cholesterol_mg_dl") == pytest.approx(
        5.172, rel=1e-3
    )
    assert convert(200.0, "mg/dL", "mmol/L", "fasting_glucose_mg_dl") == pytest.approx(
        11.0999, rel=1e-3
    )
    # An ambiguous pair with no key is refused rather than guessed.
    assert convert(200.0, "mg/dL", "mmol/L") is None
    # A pair that occurs in exactly one group is still usable without a key.
    assert convert(140.0, "g/L", "g/dL") == pytest.approx(14.0)
    assert convert(5.0, "mg/dL", "mmol/L", "hemoglobin_g_dl") is None


def test_unrelated_or_missing_units_are_never_converted():
    assert convert(5.0, "mg/dL", "ng/mL", "creatinine_mg_dl") is None
    assert convert(5.0, "furlongs", "mg/dL", "creatinine_mg_dl") is None
    assert convert(None, "mg/dL", "mmol/L", "creatinine_mg_dl") is None


def test_build_parameters_converts_units_and_moves_the_printed_range_with_the_value():
    parameters, warnings = build_parameters(
        [
            {
                "key": "fasting_glucose_mg_dl",
                "label": "Fasting blood glucose",
                "value": 5.0,
                "unit": "mmol/L",
                "reference_low": 3.9,
                "reference_high": 5.6,
                "raw_text": "FBS 5.0 mmol/L 3.9-5.6",
            }
        ]
    )
    assert warnings == []
    (glucose,) = parameters
    assert glucose.unit == "mg/dL"
    assert glucose.value == pytest.approx(90.091, rel=1e-4)
    assert glucose.reference_low == pytest.approx(70.27, rel=1e-3)
    assert glucose.reference_high == pytest.approx(100.9, rel=1e-3)
    assert glucose.reference_source == "document"
    assert glucose.status == "normal"


def test_implausible_value_is_quarantined_with_a_warning_and_no_verdict():
    parameters, warnings = build_parameters(
        [{"key": "hemoglobin_g_dl", "label": "Haemoglobin", "value": 900.0, "unit": "g/dL"}]
    )
    (hemoglobin,) = parameters
    assert hemoglobin.value is None
    assert hemoglobin.status == "unknown"
    assert hemoglobin.reference_low == 12.0 and hemoglobin.reference_high == 16.0
    assert len(warnings) == 1
    assert "plausible range" in warnings[0] and "Haemoglobin" in warnings[0]
    # The warning never echoes the reported value back to the user.
    assert "900" not in warnings[0]


def test_duplicate_reading_keeps_the_first_and_explains_the_drop():
    parameters, warnings = build_parameters(
        [
            {
                "key": "tsh_miu_l",
                "label": "Thyroid stimulating hormone",
                "value": 2.0,
                "unit": "mIU/L",
            },
            {
                "key": "tsh_miu_l",
                "label": "Thyroid stimulating hormone",
                "value": 3.0,
                "unit": "mIU/L",
            },
        ]
    )
    assert [item.value for item in parameters] == [2.0]
    assert warnings == [
        "Thyroid stimulating hormone appeared more than once; only the first reading was kept."
    ]


def test_document_range_wins_over_the_standard_range():
    parameters, _ = build_parameters(
        [
            {
                "key": "fasting_glucose_mg_dl",
                "label": "Fasting blood glucose",
                "value": 110.0,
                "unit": "mg/dL",
                "reference_low": 70.0,
                "reference_high": 120.0,
            }
        ]
    )
    (glucose,) = parameters
    assert (glucose.reference_low, glucose.reference_high) == (70.0, 120.0)
    assert glucose.reference_source == "document"
    assert glucose.status == "normal"  # the standard range (70-100) would have called it high


def test_a_printed_upper_limit_alone_classifies_against_that_limit():
    parameters, _ = build_parameters(
        [
            {
                "key": "ldl_cholesterol_mg_dl",
                "label": "LDL cholesterol",
                "value": 130.0,
                "unit": "mg/dL",
                "reference_high": 100.0,
            }
        ]
    )
    assert parameters[0].status == "high"
    assert parameters[0].reference_source == "document"


def test_sex_and_age_aware_haemoglobin_ranges():
    assert reference_range("hemoglobin_g_dl", "female", "30_44") == (12.0, 15.5, "standard")
    assert reference_range("hemoglobin_g_dl", "male", "30_44") == (13.5, 17.5, "standard")
    assert reference_range("hemoglobin_g_dl", "female", "75_plus") == (11.7, 15.0, "standard")
    assert reference_range("hemoglobin_g_dl", "unspecified", "under_18") == (11.5, 15.5, "standard")
    reading = {"key": "hemoglobin_g_dl", "label": "Haemoglobin", "value": 11.8, "unit": "g/dL"}
    assert classify(reading, "female", "75_plus") == "normal"
    assert classify(reading, "unspecified", "unspecified") == "low"


def test_classification_boundaries_are_inclusive_and_one_sided_ranges_stay_one_sided():
    def reading(value, low, high):
        return {
            "key": "hemoglobin_g_dl",
            "label": "Haemoglobin",
            "value": value,
            "unit": "g/dL",
            "reference_low": low,
            "reference_high": high,
        }

    assert classify(reading(12.0, 12.0, 16.0)) == "normal"
    assert classify(reading(11.99, 12.0, 16.0)) == "low"
    assert classify(reading(16.0, 12.0, 16.0)) == "normal"
    assert classify(reading(16.01, 12.0, 16.0)) == "high"
    # A low-only range can never classify high, and vice versa.
    assert classify(reading(200.0, 12.0, None)) == "normal"
    assert classify(reading(1.0, None, 16.0)) == "normal"
    assert classify(reading(17.0, None, 16.0)) == "high"


def test_missing_value_or_missing_range_is_unknown():
    assert classify({"key": "hemoglobin_g_dl", "value": None}) == "unknown"
    assert reference_range("weight_kg", "female", "30_44") == (None, None, "unknown")
    assert classify({"key": "weight_kg", "value": 62.0, "unit": "kg"}) == "unknown"
    assert reference_range("not_a_key") == (None, None, "unknown")
