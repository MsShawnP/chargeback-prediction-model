"""Tests for the reason-code harmonization engine (U3)."""

from pathlib import Path

import pandas as pd
import pytest

from src.harmonization.reason_codes import (
    ARCHETYPES,
    DEDUCTION_TYPE_TO_ARCHETYPE,
    REASON_TO_ARCHETYPE,
    UnmappedCodeError,
    harmonize_chargebacks,
    harmonize_deduction_type,
    harmonize_deductions,
    harmonize_reason,
)

FIXTURES = Path(__file__).parent.parent / "fixtures"


# ---------------------------------------------------------------------------
# reason code → archetype
# ---------------------------------------------------------------------------


def test_reason_label_fine_maps_to_data_compliance_error():
    assert harmonize_reason("label_fine") == "data_compliance_error"


def test_reason_damaged_maps_to_logistics_overage():
    assert harmonize_reason("damaged") == "logistics_overage"


def test_reason_pricing_error_maps_to_pricing_discrepancy():
    assert harmonize_reason("pricing_error") == "pricing_discrepancy"


def test_reason_late_delivery_maps_to_asn_timing_infraction():
    assert harmonize_reason("late_delivery") == "asn_timing_infraction"


def test_reason_short_ship_maps_to_logistics_overage():
    assert harmonize_reason("short_ship") == "logistics_overage"


def test_unknown_reason_code_raises_unmapped_code_error():
    with pytest.raises(UnmappedCodeError) as exc_info:
        harmonize_reason("not_a_real_code")
    assert "not_a_real_code" in str(exc_info.value)


# ---------------------------------------------------------------------------
# deduction_type → archetype
# ---------------------------------------------------------------------------


def test_deduction_type_label_fine_maps_to_data_compliance_error():
    assert harmonize_deduction_type("label_fine") == "data_compliance_error"


def test_deduction_type_short_ship_maps_to_logistics_overage():
    assert harmonize_deduction_type("short_ship") == "logistics_overage"


def test_deduction_type_slotting_maps_to_legitimate():
    assert harmonize_deduction_type("slotting") == "legitimate"


def test_deduction_type_pricing_error_maps_to_pricing_discrepancy():
    assert harmonize_deduction_type("pricing_error") == "pricing_discrepancy"


def test_deduction_type_damaged_maps_to_logistics_overage():
    assert harmonize_deduction_type("damaged") == "logistics_overage"


def test_deduction_type_spoilage_maps_to_logistics_overage():
    assert harmonize_deduction_type("spoilage") == "logistics_overage"


def test_deduction_type_late_delivery_maps_to_asn_timing_infraction():
    assert harmonize_deduction_type("late_delivery") == "asn_timing_infraction"


def test_deduction_type_pallet_fine_maps_to_logistics_overage():
    assert harmonize_deduction_type("pallet_fine") == "logistics_overage"


def test_deduction_type_promo_billback_maps_to_legitimate():
    assert harmonize_deduction_type("promo_billback") == "legitimate"


def test_unknown_deduction_type_raises_unmapped_code_error():
    with pytest.raises(UnmappedCodeError) as exc_info:
        harmonize_deduction_type("mystery_code")
    assert "mystery_code" in str(exc_info.value)


# ---------------------------------------------------------------------------
# all known codes produce valid archetypes (completeness guard)
# ---------------------------------------------------------------------------


def test_all_reason_codes_map_to_a_known_archetype():
    for code, archetype in REASON_TO_ARCHETYPE.items():
        assert archetype in ARCHETYPES, f"{code!r} → unknown archetype {archetype!r}"


def test_all_deduction_types_map_to_a_known_archetype():
    for code, archetype in DEDUCTION_TYPE_TO_ARCHETYPE.items():
        assert archetype in ARCHETYPES, f"{code!r} → unknown archetype {archetype!r}"


# ---------------------------------------------------------------------------
# determinism
# ---------------------------------------------------------------------------


def test_harmonize_reason_is_deterministic():
    assert harmonize_reason("label_fine") == harmonize_reason("label_fine")


def test_harmonize_deduction_type_is_deterministic():
    assert harmonize_deduction_type("slotting") == harmonize_deduction_type("slotting")


# ---------------------------------------------------------------------------
# DataFrame enrichment
# ---------------------------------------------------------------------------


def test_harmonize_chargebacks_adds_root_cause_archetype_column():
    df = pd.read_csv(FIXTURES / "sample_chargebacks.csv")
    result = harmonize_chargebacks(df)
    assert "root_cause_archetype" in result.columns


def test_harmonize_chargebacks_preserves_all_rows():
    df = pd.read_csv(FIXTURES / "sample_chargebacks.csv")
    result = harmonize_chargebacks(df)
    assert len(result) == len(df)


def test_harmonize_chargebacks_all_known_codes_produce_non_null_archetype():
    df = pd.read_csv(FIXTURES / "sample_chargebacks.csv")
    result = harmonize_chargebacks(df)
    assert result["root_cause_archetype"].notna().all()


def test_harmonize_chargebacks_unknown_code_produces_none_not_error():
    df = pd.DataFrame({"reason": ["label_fine", "unknown_code"]})
    result = harmonize_chargebacks(df)
    assert result.loc[0, "root_cause_archetype"] == "data_compliance_error"
    assert result.loc[1, "root_cause_archetype"] is None


def test_harmonize_chargebacks_does_not_mutate_input():
    df = pd.read_csv(FIXTURES / "sample_chargebacks.csv")
    original_cols = set(df.columns)
    harmonize_chargebacks(df)
    assert set(df.columns) == original_cols


def test_harmonize_deductions_correct_archetypes():
    df = pd.DataFrame({
        "deduction_type": ["label_fine", "slotting", "pallet_fine", "promo_billback"]
    })
    result = harmonize_deductions(df)
    assert "root_cause_archetype" in result.columns
    assert list(result["root_cause_archetype"]) == [
        "data_compliance_error", "legitimate", "logistics_overage", "legitimate"
    ]


def test_harmonize_deductions_unknown_code_produces_none_not_error():
    df = pd.DataFrame({"deduction_type": ["slotting", "not_real"]})
    result = harmonize_deductions(df)
    assert result.loc[0, "root_cause_archetype"] == "legitimate"
    assert result.loc[1, "root_cause_archetype"] is None
