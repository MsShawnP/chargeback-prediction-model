"""Tests for the JSON/CSV export pipeline (U7)."""

import json
from pathlib import Path

import pandas as pd
import pytest

from src.pipeline.export import (
    build_chargebacks_by_archetype,
    build_risk_ledger,
    build_simulator_payload,
    build_summary,
    write_json,
)


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def scored_pos():
    return pd.DataFrame(
        {
            "order_id": ["PO1", "PO2", "PO3"],
            "retailer_id": ["RET-1", "RET-2", "RET-1"],
            "sku": ["SKU-A", "SKU-B", "SKU-C"],
            "order_date": pd.to_datetime(["2027-02-01", "2027-02-02", "2027-02-03"]),
            "order_value": [1000.0, 2000.0, 500.0],
            "chargeback_probability": [0.75, 0.20, 0.55],
            "dollar_exposure": [750.0, 400.0, 275.0],
            "risk_tier": ["high", "low", "high"],
            "attribution": [
                "Missing GTIN-14 → data compliance error → 75% probability within 14 days",
                "Prior chargeback history → historical pattern → 20% probability within 14 days",
                "Missing case dimensions → logistics audit → 55% probability within 14 days",
            ],
        }
    )


@pytest.fixture
def shap_df():
    """Synthetic SHAP values aligned with scored_pos (3 rows, 3 features)."""
    return pd.DataFrame(
        {
            "gtin14_missing": [0.42, -0.05, 0.10],
            "asn_sent_late": [0.05, 0.02, -0.01],
            "sku_prior_chargeback_rate": [0.08, 0.15, 0.20],
        }
    )


@pytest.fixture
def prevention_roadmap():
    return pd.DataFrame(
        {
            "root_cause_archetype": ["logistics_overage", "data_compliance_error"],
            "historical_loss": [240_000.0, 150_000.0],
            "preventability_fraction": [0.70, 0.80],
            "prevention_value": [168_000.0, 120_000.0],
            "fix_description": [
                "Audit pick-and-pack procedures",
                "Populate missing barcodes",
            ],
        }
    )


@pytest.fixture
def chargebacks_harmonized():
    return pd.DataFrame(
        {
            "chargeback_id": list(range(8)),
            "root_cause_archetype": [
                "logistics_overage",
                "logistics_overage",
                "data_compliance_error",
                "data_compliance_error",
                "asn_timing_infraction",
                "asn_timing_infraction",
                "legitimate",
                None,  # unmapped — should be excluded
            ],
            "amount": [
                80_000.0, 60_000.0,
                90_000.0, 50_000.0,
                40_000.0, 30_000.0,
                20_000.0, 5_000.0,
            ],
        }
    )


@pytest.fixture
def model_performance():
    return pd.DataFrame(
        {"auc": [0.7821], "precision": [0.65], "recall": [0.72], "n_train": [520], "n_test": [130]}
    )


# ---------------------------------------------------------------------------
# build_risk_ledger
# ---------------------------------------------------------------------------


def test_risk_ledger_has_required_fields(scored_pos):
    result = build_risk_ledger(scored_pos)
    required = {"sku", "retailer", "ship_date", "probability", "dollar_exposure",
                "attribution_string", "risk_tier"}
    for row in result:
        assert required.issubset(row.keys()), f"Missing keys in row: {set(row.keys())}"


def test_risk_ledger_row_count_matches_input(scored_pos):
    assert len(build_risk_ledger(scored_pos)) == len(scored_pos)


def test_risk_ledger_attribution_string_non_null(scored_pos):
    result = build_risk_ledger(scored_pos)
    for row in result:
        assert row["attribution_string"] is not None
        assert len(row["attribution_string"]) > 0


def test_risk_ledger_probability_rounded_to_4dp(scored_pos):
    result = build_risk_ledger(scored_pos)
    for row in result:
        as_str = str(row["probability"])
        decimal_places = len(as_str.split(".")[-1]) if "." in as_str else 0
        assert decimal_places <= 4


def test_risk_ledger_ship_date_falls_back_to_order_date(scored_pos):
    """When ship_date column is absent, order_date is used as proxy."""
    result = build_risk_ledger(scored_pos)
    for row in result:
        assert row["ship_date"] is not None


def test_risk_ledger_uses_ship_date_when_present():
    df = pd.DataFrame(
        {
            "order_id": ["PO1"],
            "retailer_id": ["RET-1"],
            "sku": ["SKU-A"],
            "order_date": pd.to_datetime(["2027-01-01"]),
            "ship_date": pd.to_datetime(["2027-01-10"]),
            "order_value": [500.0],
            "chargeback_probability": [0.5],
            "dollar_exposure": [250.0],
            "risk_tier": ["high"],
            "attribution": ["x → y → 50%"],
        }
    )
    result = build_risk_ledger(df)
    assert "2027-01-10" in result[0]["ship_date"]


def test_risk_ledger_is_valid_json_after_write(scored_pos, tmp_path):
    """Round-trip: build → write → parse — must succeed without error."""
    path = tmp_path / "risk_ledger.json"
    write_json(build_risk_ledger(scored_pos), path)
    with open(path, encoding="utf-8") as f:
        loaded = json.load(f)
    assert isinstance(loaded, list)
    assert len(loaded) == len(scored_pos)


# ---------------------------------------------------------------------------
# build_simulator_payload
# ---------------------------------------------------------------------------


def test_simulator_has_shap_values_dict(scored_pos, shap_df):
    result = build_simulator_payload(scored_pos, shap_df)
    for row in result:
        assert "shap_values" in row
        assert isinstance(row["shap_values"], dict)


def test_simulator_shap_values_has_one_key_per_feature(scored_pos, shap_df):
    result = build_simulator_payload(scored_pos, shap_df)
    expected_keys = set(shap_df.columns)
    for row in result:
        assert set(row["shap_values"].keys()) == expected_keys


def test_simulator_row_count_matches_input(scored_pos, shap_df):
    assert len(build_simulator_payload(scored_pos, shap_df)) == len(scored_pos)


def test_simulator_raises_when_rows_misaligned(scored_pos, shap_df):
    extra_row = pd.concat([shap_df, shap_df.iloc[:1]], ignore_index=True)
    with pytest.raises(ValueError, match="must be aligned"):
        build_simulator_payload(scored_pos, extra_row)


def test_simulator_includes_risk_ledger_fields(scored_pos, shap_df):
    result = build_simulator_payload(scored_pos, shap_df)
    ledger_keys = {"sku", "retailer", "probability", "dollar_exposure", "risk_tier"}
    for row in result:
        assert ledger_keys.issubset(row.keys())


# ---------------------------------------------------------------------------
# build_summary
# ---------------------------------------------------------------------------


def test_summary_has_required_keys(
    scored_pos, prevention_roadmap, chargebacks_harmonized, model_performance
):
    result = build_summary(
        scored_pos, prevention_roadmap, chargebacks_harmonized, model_performance
    )
    for key in (
        "total_chargeback_amount",
        "total_preventable",
        "preventable_pct",
        "root_cause_counts",
        "model_auc",
    ):
        assert key in result, f"Missing key: {key}"


def test_summary_total_preventable_lte_total_chargeback(
    scored_pos, prevention_roadmap, chargebacks_harmonized, model_performance
):
    result = build_summary(
        scored_pos, prevention_roadmap, chargebacks_harmonized, model_performance
    )
    assert result["total_preventable"] <= result["total_chargeback_amount"] + 1e-6


def test_summary_preventable_pct_in_0_1_range(
    scored_pos, prevention_roadmap, chargebacks_harmonized, model_performance
):
    result = build_summary(
        scored_pos, prevention_roadmap, chargebacks_harmonized, model_performance
    )
    assert 0.0 <= result["preventable_pct"] <= 1.0


def test_summary_root_cause_counts_excludes_null_archetypes(
    scored_pos, prevention_roadmap, chargebacks_harmonized, model_performance
):
    result = build_summary(
        scored_pos, prevention_roadmap, chargebacks_harmonized, model_performance
    )
    # The None archetype should not appear in root_cause_counts
    assert None not in result["root_cause_counts"]
    assert "None" not in result["root_cause_counts"]


def test_summary_model_auc_matches_performance_csv(
    scored_pos, prevention_roadmap, chargebacks_harmonized, model_performance
):
    result = build_summary(
        scored_pos, prevention_roadmap, chargebacks_harmonized, model_performance
    )
    assert abs(result["model_auc"] - 0.7821) < 1e-4


# ---------------------------------------------------------------------------
# build_chargebacks_by_archetype
# ---------------------------------------------------------------------------


def test_chargebacks_by_archetype_one_row_per_archetype(chargebacks_harmonized):
    result = build_chargebacks_by_archetype(chargebacks_harmonized)
    assert result["root_cause_archetype"].nunique() == len(result)


def test_chargebacks_by_archetype_excludes_null(chargebacks_harmonized):
    result = build_chargebacks_by_archetype(chargebacks_harmonized)
    assert result["root_cause_archetype"].notna().all()


def test_chargebacks_by_archetype_sorted_descending(chargebacks_harmonized):
    result = build_chargebacks_by_archetype(chargebacks_harmonized)
    amounts = result["total_amount"].tolist()
    assert amounts == sorted(amounts, reverse=True)


def test_chargebacks_by_archetype_empty_input():
    empty = pd.DataFrame(columns=["root_cause_archetype", "amount"])
    result = build_chargebacks_by_archetype(empty)
    assert len(result) == 0


# ---------------------------------------------------------------------------
# write_json — I/O
# ---------------------------------------------------------------------------


def test_write_json_creates_file(tmp_path):
    path = tmp_path / "out.json"
    write_json({"key": "value"}, path)
    assert path.exists()


def test_write_json_produces_valid_json(tmp_path):
    data = [{"a": 1}, {"a": 2}]
    path = tmp_path / "list.json"
    write_json(data, path)
    with open(path, encoding="utf-8") as f:
        loaded = json.load(f)
    assert loaded == data


def test_write_json_creates_parent_dirs(tmp_path):
    path = tmp_path / "nested" / "deep" / "out.json"
    write_json({"x": 1}, path)
    assert path.exists()


# ---------------------------------------------------------------------------
# Determinism — running twice produces identical output
# ---------------------------------------------------------------------------


def test_risk_ledger_is_deterministic(scored_pos):
    r1 = build_risk_ledger(scored_pos)
    r2 = build_risk_ledger(scored_pos)
    assert r1 == r2


def test_simulator_is_deterministic(scored_pos, shap_df):
    r1 = build_simulator_payload(scored_pos, shap_df)
    r2 = build_simulator_payload(scored_pos, shap_df)
    assert r1 == r2


def test_summary_is_deterministic(
    scored_pos, prevention_roadmap, chargebacks_harmonized, model_performance
):
    r1 = build_summary(scored_pos, prevention_roadmap, chargebacks_harmonized, model_performance)
    r2 = build_summary(scored_pos, prevention_roadmap, chargebacks_harmonized, model_performance)
    assert r1 == r2
