"""Tests for the prevention roadmap pipeline (U6 — roadmap side)."""

import pandas as pd
import pytest

from src.pipeline.roadmap import (
    ARCHETYPE_FIX_DESCRIPTIONS,
    PREVENTABILITY_FRACTIONS,
    compute_prevention_roadmap,
)


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def historical_chargebacks():
    """Synthetic historical chargebacks with root_cause_archetype from U3 harmonization."""
    return pd.DataFrame(
        {
            "chargeback_id": list(range(10)),
            "root_cause_archetype": [
                "data_compliance_error",
                "data_compliance_error",
                "logistics_overage",
                "logistics_overage",
                "logistics_overage",
                "asn_timing_infraction",
                "pricing_discrepancy",
                "legitimate",
                "legitimate",
                "data_compliance_error",
            ],
            "amount": [
                150_000.0,
                90_000.0,
                120_000.0,
                80_000.0,
                40_000.0,
                60_000.0,
                50_000.0,
                70_000.0,
                30_000.0,
                10_000.0,
            ],
        }
    )


# ---------------------------------------------------------------------------
# compute_prevention_roadmap — structure
# ---------------------------------------------------------------------------


def test_roadmap_has_one_row_per_archetype(historical_chargebacks):
    result = compute_prevention_roadmap(historical_chargebacks)
    assert result["root_cause_archetype"].nunique() == len(result)
    assert result["root_cause_archetype"].duplicated().sum() == 0


def test_roadmap_sorted_by_prevention_value_descending(historical_chargebacks):
    result = compute_prevention_roadmap(historical_chargebacks)
    values = result["prevention_value"].tolist()
    assert values == sorted(values, reverse=True)


def test_roadmap_prevention_values_sum_lte_total_historical_loss(historical_chargebacks):
    total_loss = historical_chargebacks["amount"].sum()
    result = compute_prevention_roadmap(historical_chargebacks)
    total_preventable = result["prevention_value"].sum()
    assert total_preventable <= total_loss + 1e-6, (
        f"prevention_value sum {total_preventable:.2f} exceeds total loss {total_loss:.2f}"
    )


def test_roadmap_has_fix_description_for_every_row(historical_chargebacks):
    result = compute_prevention_roadmap(historical_chargebacks)
    assert result["fix_description"].notna().all()
    assert (result["fix_description"].str.len() > 0).all()


def test_roadmap_columns_are_complete(historical_chargebacks):
    result = compute_prevention_roadmap(historical_chargebacks)
    for col in (
        "root_cause_archetype",
        "historical_loss",
        "preventability_fraction",
        "prevention_value",
        "fix_description",
    ):
        assert col in result.columns, f"Missing column: {col}"


def test_roadmap_historical_loss_matches_grouped_sum(historical_chargebacks):
    result = compute_prevention_roadmap(historical_chargebacks)
    expected = (
        historical_chargebacks.groupby("root_cause_archetype")["amount"]
        .sum()
        .to_dict()
    )
    for _, row in result.iterrows():
        archetype = row["root_cause_archetype"]
        assert abs(row["historical_loss"] - expected[archetype]) < 1e-6


def test_roadmap_prevention_value_equals_loss_times_fraction(historical_chargebacks):
    result = compute_prevention_roadmap(historical_chargebacks)
    for _, row in result.iterrows():
        expected = row["historical_loss"] * row["preventability_fraction"]
        assert abs(row["prevention_value"] - expected) < 1e-6


# ---------------------------------------------------------------------------
# compute_prevention_roadmap — edge cases
# ---------------------------------------------------------------------------


def test_roadmap_empty_input_returns_empty_dataframe():
    empty = pd.DataFrame(columns=["root_cause_archetype", "amount"])
    result = compute_prevention_roadmap(empty)
    assert len(result) == 0


def test_roadmap_null_archetypes_excluded():
    df = pd.DataFrame(
        {
            "root_cause_archetype": ["data_compliance_error", None, "logistics_overage"],
            "amount": [100_000.0, 50_000.0, 80_000.0],
        }
    )
    result = compute_prevention_roadmap(df)
    assert result["root_cause_archetype"].notna().all()
    assert len(result) == 2


def test_roadmap_unknown_archetype_gets_zero_preventability():
    df = pd.DataFrame(
        {
            "root_cause_archetype": ["not_a_real_archetype"],
            "amount": [10_000.0],
        }
    )
    result = compute_prevention_roadmap(df)
    assert result.iloc[0]["preventability_fraction"] == 0.0
    assert result.iloc[0]["prevention_value"] == 0.0


def test_roadmap_single_archetype():
    df = pd.DataFrame(
        {"root_cause_archetype": ["logistics_overage"], "amount": [300_000.0]}
    )
    result = compute_prevention_roadmap(df)
    assert len(result) == 1
    assert abs(result.iloc[0]["prevention_value"] - 210_000.0) < 1e-6


# ---------------------------------------------------------------------------
# PREVENTABILITY_FRACTIONS constants
# ---------------------------------------------------------------------------


def test_preventability_fractions_all_between_0_and_1():
    for archetype, fraction in PREVENTABILITY_FRACTIONS.items():
        assert 0.0 <= fraction <= 1.0, (
            f"{archetype!r} has invalid fraction {fraction}"
        )


def test_preventability_fractions_data_archetypes_above_logistics():
    """Data quality archetypes must be at least as preventable as logistics."""
    assert PREVENTABILITY_FRACTIONS["data_compliance_error"] >= PREVENTABILITY_FRACTIONS["logistics_overage"]
    assert PREVENTABILITY_FRACTIONS["item_setup_gap"] >= PREVENTABILITY_FRACTIONS["logistics_overage"]


def test_legitimate_archetype_has_lowest_preventability():
    """Legitimate fees should have the lowest preventability fraction."""
    legitimate_frac = PREVENTABILITY_FRACTIONS["legitimate"]
    other_fracs = [v for k, v in PREVENTABILITY_FRACTIONS.items() if k != "legitimate"]
    assert all(legitimate_frac <= f for f in other_fracs)


def test_fix_descriptions_defined_for_all_preventability_archetypes():
    for archetype in PREVENTABILITY_FRACTIONS:
        assert archetype in ARCHETYPE_FIX_DESCRIPTIONS, (
            f"No fix description for archetype {archetype!r}"
        )
