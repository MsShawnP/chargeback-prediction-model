"""Tests for scripts/generate_training_data.py."""

import numpy as np
import pandas as pd
import pytest

from scripts.generate_training_data import (
    BASE_RATE,
    compute_chargeback_probabilities,
    reconstruct_retailer_id,
    run,
)


@pytest.fixture
def base_row():
    """One shipment row with no risk factors — should return BASE_RATE."""
    return pd.DataFrame([{
        "gtin14_missing": False,
        "upc_missing": False,
        "case_dims_missing": False,
        "case_weight_missing": False,
        "data_quality_score": 4.0,
        "asn_sent_late": False,
        "days_late": 0.0,
    }])


@pytest.fixture
def high_risk_row():
    """One shipment with every risk factor active."""
    return pd.DataFrame([{
        "gtin14_missing": True,
        "upc_missing": True,
        "case_dims_missing": True,
        "case_weight_missing": True,
        "data_quality_score": 1.0,
        "asn_sent_late": True,
        "days_late": 6.0,
    }])


def test_base_row_probability_equals_base_rate(base_row):
    probs = compute_chargeback_probabilities(base_row)
    assert abs(probs[0] - BASE_RATE) < 1e-9


def test_high_risk_row_probability_is_capped_at_max(high_risk_row):
    probs = compute_chargeback_probabilities(high_risk_row)
    assert probs[0] == pytest.approx(0.85)


def test_gtin14_missing_increases_probability(base_row):
    base_prob = compute_chargeback_probabilities(base_row)[0]
    risky = base_row.copy()
    risky["gtin14_missing"] = True
    risky_prob = compute_chargeback_probabilities(risky)[0]
    assert risky_prob > base_prob * 3  # 4x multiplier → strictly higher


def test_asn_sent_late_increases_probability(base_row):
    base_prob = compute_chargeback_probabilities(base_row)[0]
    risky = base_row.copy()
    risky["asn_sent_late"] = True
    risky_prob = compute_chargeback_probabilities(risky)[0]
    assert risky_prob > base_prob * 3


def test_low_data_quality_score_increases_probability(base_row):
    base_prob = compute_chargeback_probabilities(base_row)[0]
    risky = base_row.copy()
    risky["data_quality_score"] = 1.0
    risky_prob = compute_chargeback_probabilities(risky)[0]
    assert risky_prob > base_prob


def test_all_probabilities_between_0_and_1():
    rng = np.random.default_rng(0)
    n = 500
    df = pd.DataFrame({
        "gtin14_missing": rng.choice([True, False], n),
        "upc_missing": rng.choice([True, False], n),
        "case_dims_missing": rng.choice([True, False], n),
        "case_weight_missing": rng.choice([True, False], n),
        "data_quality_score": rng.integers(1, 5, n).astype(float),
        "asn_sent_late": rng.choice([True, False], n),
        "days_late": rng.uniform(0, 8, n),
    })
    probs = compute_chargeback_probabilities(df)
    assert (probs >= 0).all() and (probs <= 1).all()


def test_chargeback_rate_in_realistic_range():
    rng = np.random.default_rng(0)
    n = 10_000
    df = pd.DataFrame({
        "gtin14_missing": rng.choice([True, False], n, p=[0.15, 0.85]),
        "upc_missing": rng.choice([True, False], n, p=[0.08, 0.92]),
        "case_dims_missing": rng.choice([True, False], n, p=[0.15, 0.85]),
        "case_weight_missing": rng.choice([True, False], n, p=[0.12, 0.88]),
        "data_quality_score": rng.choice([1, 2, 3, 4], n, p=[0.03, 0.07, 0.20, 0.70]).astype(float),
        "asn_sent_late": rng.choice([True, False], n, p=[0.086, 0.914]),
        "days_late": rng.uniform(0, 7, n),
    })
    probs = compute_chargeback_probabilities(df)
    labels = (np.random.default_rng(42).random(n) < probs).astype(int)
    rate = labels.mean()
    assert 0.04 <= rate <= 0.20, f"Chargeback rate {rate:.3f} outside expected 4–20%"


def test_reconstruct_retailer_id_decodes_dummy():
    df = pd.DataFrame([{
        "retailer_RET_WALMART": True,
        "retailer_RET_COSTCO": False,
    }])
    result = reconstruct_retailer_id(df)
    assert result.iloc[0] == "RET-WALMART"


def test_reconstruct_retailer_id_unknown_when_no_dummy_active():
    df = pd.DataFrame([{
        "retailer_RET_WALMART": False,
        "retailer_RET_COSTCO": False,
    }])
    result = reconstruct_retailer_id(df)
    assert result.iloc[0] == "UNKNOWN"


def test_run_produces_parquet_with_synthetic_labels(tmp_path):
    """Integration: run() reads real training_features and writes synthetic file."""
    # Build a minimal synthetic input (mimics training_features.parquet schema)
    rng = np.random.default_rng(1)
    n = 200
    df = pd.DataFrame({
        "shipment_id": [f"RS-{i:06d}" for i in range(n)],
        "order_id": [f"RO-{i:06d}" for i in range(n)],
        "ship_date": pd.date_range("2024-01-01", periods=n, freq="D"),
        "sku": [f"SKU-{i % 10}" for i in range(n)],
        "chargeback": rng.integers(0, 2, n),
        "gtin14_missing": rng.choice([True, False], n, p=[0.2, 0.8]),
        "upc_missing": rng.choice([True, False], n, p=[0.1, 0.9]),
        "case_dims_missing": rng.choice([True, False], n, p=[0.15, 0.85]),
        "case_weight_missing": rng.choice([True, False], n, p=[0.1, 0.9]),
        "data_quality_score": rng.integers(1, 5, n).astype(float),
        "asn_sent_late": rng.choice([True, False], n, p=[0.1, 0.9]),
        "days_late": rng.uniform(0, 7, n),
        "all_labels_scannable": rng.choice([True, False], n),
        "sku_prior_chargeback_rate": rng.uniform(0, 0.3, n),
        "ship_month": rng.integers(1, 13, n),
        "ship_quarter": rng.integers(1, 5, n),
        "retailer_RET_A": rng.choice([True, False], n, p=[0.5, 0.5]),
        "retailer_RET_B": rng.choice([True, False], n, p=[0.5, 0.5]),
        "units_ordered": rng.integers(24, 145, n).astype(float),
    })
    input_path = tmp_path / "training_features.parquet"
    output_path = tmp_path / "training_features_synthetic.parquet"
    df.to_parquet(input_path, index=False)

    run(input_path=input_path, output_path=output_path, seed=42)

    assert output_path.exists()
    result = pd.read_parquet(output_path)
    assert len(result) == n
    assert "chargeback" in result.columns
    assert "sku_prior_chargeback_rate" in result.columns
    assert result["chargeback"].isin([0, 1]).all()


def test_run_is_deterministic(tmp_path):
    """Same input + same seed → identical output."""
    rng = np.random.default_rng(2)
    n = 100
    df = pd.DataFrame({
        "shipment_id": [f"RS-{i}" for i in range(n)],
        "order_id": [f"RO-{i}" for i in range(n)],
        "ship_date": pd.date_range("2024-01-01", periods=n, freq="D"),
        "sku": [f"SKU-{i % 5}" for i in range(n)],
        "chargeback": 0,
        "gtin14_missing": rng.choice([True, False], n),
        "upc_missing": False, "case_dims_missing": False,
        "case_weight_missing": False,
        "data_quality_score": 4.0,
        "asn_sent_late": False, "days_late": 0.0,
        "all_labels_scannable": True,
        "sku_prior_chargeback_rate": 0.0,
        "ship_month": 1, "ship_quarter": 1,
        "retailer_RET_A": rng.choice([True, False], n),
        "retailer_RET_B": False,
        "units_ordered": 48.0,
    })
    input_path = tmp_path / "training_features.parquet"
    df.to_parquet(input_path, index=False)

    out1 = tmp_path / "synth1.parquet"
    out2 = tmp_path / "synth2.parquet"
    run(input_path=input_path, output_path=out1, seed=42)
    run(input_path=input_path, output_path=out2, seed=42)

    r1 = pd.read_parquet(out1)["chargeback"]
    r2 = pd.read_parquet(out2)["chargeback"]
    pd.testing.assert_series_equal(r1, r2)
