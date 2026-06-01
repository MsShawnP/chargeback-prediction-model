"""Tests for the forward risk scoring pipeline (U6 — scoring side)."""

import numpy as np
import pandas as pd
import pytest
from sklearn.ensemble import RandomForestClassifier

from src.pipeline.scoring import (
    RISK_TIER_HIGH,
    RISK_TIER_MEDIUM,
    assign_risk_tier,
    attach_prior_chargeback_rate,
    build_compliance_defaults,
    build_feature_matrix,
    build_product_quality_flags,
    compute_dollar_exposure,
    score_pos,
)


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def tiny_model():
    """Minimal trained model for feature-alignment and scoring tests.

    Uses the same feature columns that score_pos produces so the
    build_feature_matrix alignment round-trip can be verified.
    """
    rng = np.random.default_rng(0)
    n = 60
    X = pd.DataFrame(
        {
            "gtin14_missing": (rng.random(n) < 0.4).astype(float),
            "upc_missing": (rng.random(n) < 0.1).astype(float),
            "case_dims_missing": (rng.random(n) < 0.1).astype(float),
            "case_weight_missing": (rng.random(n) < 0.05).astype(float),
            "data_quality_score": rng.integers(1, 5, n).astype(float),
            "asn_sent_late": (rng.random(n) < 0.1).astype(float),
            "days_late": rng.integers(0, 10, n).astype(float),
            "all_labels_scannable": (rng.random(n) < 0.9).astype(float),
            "sku_prior_chargeback_rate": rng.random(n) * 0.3,
            "retailer_RET_1": (rng.random(n) < 0.5).astype(float),
            "retailer_RET_2": (rng.random(n) < 0.5).astype(float),
        }
    )
    y = (rng.random(n) < 0.25).astype(int)
    model = RandomForestClassifier(n_estimators=5, random_state=42)
    model.fit(X, y)
    return model


@pytest.fixture
def sample_pos():
    return pd.DataFrame(
        {
            "order_id": ["PO1", "PO2", "PO3"],
            "retailer_id": ["RET-1", "RET-2", "RET-1"],
            "sku": ["SKU-A", "SKU-B", "SKU-C"],
            "order_date": pd.to_datetime(["2027-02-01", "2027-02-02", "2027-02-03"]),
            "order_value": [1000.0, 2000.0, 500.0],
        }
    )


@pytest.fixture
def sample_product_master():
    # SKU-A: missing gtin14 → gtin14_missing=True, data_quality_score=3
    # SKU-B: all present → data_quality_score=4
    # SKU-C: missing case dims → case_dims_missing=True, data_quality_score=3
    return pd.DataFrame(
        {
            "sku": ["SKU-A", "SKU-B", "SKU-C"],
            "gtin14": [None, "12345678901234", "23456789012345"],
            "upc": ["012345678901", "023456789012", "034567890123"],
            "case_length_in": [10.0, 12.0, None],
            "case_width_in": [8.0, 9.0, None],
            "case_height_in": [6.0, 7.0, None],
            "case_weight_lbs": [5.0, 6.0, 7.0],
        }
    )


@pytest.fixture
def sample_historical_rates():
    return pd.DataFrame(
        {
            "sku": ["SKU-A", "SKU-B", "SKU-C"],
            "retailer_id": ["RET-1", "RET-2", "RET-1"],
            "sku_prior_chargeback_rate": [0.30, 0.05, 0.20],
        }
    )


# ---------------------------------------------------------------------------
# build_product_quality_flags
# ---------------------------------------------------------------------------


def test_gtin14_missing_flagged_correctly(sample_pos, sample_product_master):
    result = build_product_quality_flags(sample_pos, sample_product_master)
    # SKU-A has null gtin14 → gtin14_missing=True
    sku_a = result[result["sku"] == "SKU-A"].iloc[0]
    assert sku_a["gtin14_missing"] is True or sku_a["gtin14_missing"] == True


def test_gtin14_present_not_flagged(sample_pos, sample_product_master):
    result = build_product_quality_flags(sample_pos, sample_product_master)
    # SKU-B has gtin14 populated → gtin14_missing=False
    sku_b = result[result["sku"] == "SKU-B"].iloc[0]
    assert sku_b["gtin14_missing"] is False or sku_b["gtin14_missing"] == False


def test_case_dims_missing_when_any_dim_is_null(sample_pos, sample_product_master):
    result = build_product_quality_flags(sample_pos, sample_product_master)
    # SKU-C has null case_length_in → case_dims_missing=True
    sku_c = result[result["sku"] == "SKU-C"].iloc[0]
    assert sku_c["case_dims_missing"] is True or sku_c["case_dims_missing"] == True


def test_data_quality_score_reflects_present_fields(sample_pos, sample_product_master):
    result = build_product_quality_flags(sample_pos, sample_product_master)
    # SKU-B: gtin14 ✓, upc ✓, case_dims ✓, case_weight ✓ → score = 4
    sku_b = result[result["sku"] == "SKU-B"].iloc[0]
    assert sku_b["data_quality_score"] == 4.0


def test_sku_absent_from_product_master_gets_all_missing(sample_product_master):
    pos = pd.DataFrame(
        {
            "order_id": ["PO-X"],
            "retailer_id": ["RET-1"],
            "sku": ["SKU-UNKNOWN"],
            "order_date": pd.to_datetime(["2027-03-01"]),
            "order_value": [100.0],
        }
    )
    result = build_product_quality_flags(pos, sample_product_master)
    row = result.iloc[0]
    assert row["gtin14_missing"] is True or row["gtin14_missing"] == True
    assert row["data_quality_score"] == 0.0


def test_product_quality_row_count_preserved(sample_pos, sample_product_master):
    result = build_product_quality_flags(sample_pos, sample_product_master)
    assert len(result) == len(sample_pos)


# ---------------------------------------------------------------------------
# build_compliance_defaults
# ---------------------------------------------------------------------------


def test_compliance_defaults_adds_required_columns(sample_pos, sample_product_master):
    df = build_product_quality_flags(sample_pos, sample_product_master)
    result = build_compliance_defaults(df)
    assert "asn_sent_late" in result.columns
    assert "days_late" in result.columns
    assert "all_labels_scannable" in result.columns


def test_compliance_defaults_asn_sent_late_is_false(sample_pos, sample_product_master):
    df = build_product_quality_flags(sample_pos, sample_product_master)
    result = build_compliance_defaults(df)
    assert (result["asn_sent_late"] == False).all()


def test_compliance_defaults_days_late_is_zero(sample_pos, sample_product_master):
    df = build_product_quality_flags(sample_pos, sample_product_master)
    result = build_compliance_defaults(df)
    assert (result["days_late"] == 0.0).all()


# ---------------------------------------------------------------------------
# attach_prior_chargeback_rate
# ---------------------------------------------------------------------------


def test_prior_rate_matched_correctly(
    sample_pos, sample_product_master, sample_historical_rates
):
    df = build_product_quality_flags(sample_pos, sample_product_master)
    df = build_compliance_defaults(df)
    result = attach_prior_chargeback_rate(df, sample_historical_rates, default_rate=0.1)
    # PO1: SKU-A, RET-1 → rate = 0.30
    po1 = result[result["order_id"] == "PO1"].iloc[0]
    assert abs(po1["sku_prior_chargeback_rate"] - 0.30) < 1e-9


def test_prior_rate_uses_default_when_no_match(sample_product_master):
    pos = pd.DataFrame(
        {
            "order_id": ["PO-X"],
            "retailer_id": ["RET-UNKNOWN"],
            "sku": ["SKU-B"],
            "order_date": pd.to_datetime(["2027-03-01"]),
            "order_value": [200.0],
        }
    )
    df = build_product_quality_flags(pos, sample_product_master)
    df = build_compliance_defaults(df)
    rates = pd.DataFrame(
        {"sku": ["SKU-B"], "retailer_id": ["RET-1"], "sku_prior_chargeback_rate": [0.20]}
    )
    result = attach_prior_chargeback_rate(df, rates, default_rate=0.07)
    assert abs(result.iloc[0]["sku_prior_chargeback_rate"] - 0.07) < 1e-9


# ---------------------------------------------------------------------------
# compute_dollar_exposure
# ---------------------------------------------------------------------------


def test_dollar_exposure_is_nonneg():
    df = pd.DataFrame(
        {
            "order_value": [1000.0, 500.0, 0.0],
            "chargeback_probability": [0.8, 0.0, 0.5],
        }
    )
    result = compute_dollar_exposure(df)
    assert (result["dollar_exposure"] >= 0).all()


def test_dollar_exposure_zero_for_zero_probability():
    df = pd.DataFrame(
        {"order_value": [1000.0], "chargeback_probability": [0.0]}
    )
    result = compute_dollar_exposure(df)
    assert result.iloc[0]["dollar_exposure"] == 0.0


def test_dollar_exposure_equals_order_value_times_probability():
    df = pd.DataFrame(
        {"order_value": [2000.0], "chargeback_probability": [0.35]}
    )
    result = compute_dollar_exposure(df)
    assert abs(result.iloc[0]["dollar_exposure"] - 700.0) < 1e-6


# ---------------------------------------------------------------------------
# assign_risk_tier
# ---------------------------------------------------------------------------


def test_risk_tier_high_for_high_probability():
    df = pd.DataFrame({"chargeback_probability": [RISK_TIER_HIGH]})
    result = assign_risk_tier(df)
    assert result.iloc[0]["risk_tier"] == "HIGH"


def test_risk_tier_medium_for_medium_probability():
    df = pd.DataFrame({"chargeback_probability": [RISK_TIER_MEDIUM]})
    result = assign_risk_tier(df)
    assert result.iloc[0]["risk_tier"] == "MEDIUM"


def test_risk_tier_low_for_low_probability():
    df = pd.DataFrame({"chargeback_probability": [0.10]})
    result = assign_risk_tier(df)
    assert result.iloc[0]["risk_tier"] == "LOW"


def test_risk_tier_covers_all_three_values():
    df = pd.DataFrame({"chargeback_probability": [0.0, 0.30, 0.70]})
    result = assign_risk_tier(df)
    assert set(result["risk_tier"]) == {"LOW", "MEDIUM", "HIGH"}


# ---------------------------------------------------------------------------
# build_feature_matrix
# ---------------------------------------------------------------------------


def test_feature_matrix_aligns_to_model_columns(
    sample_pos, sample_product_master, sample_historical_rates, tiny_model
):
    df = build_product_quality_flags(sample_pos, sample_product_master)
    df = build_compliance_defaults(df)
    df = attach_prior_chargeback_rate(df, sample_historical_rates)
    X = build_feature_matrix(df, tiny_model)
    assert list(X.columns) == list(tiny_model.feature_names_in_)


def test_feature_matrix_fills_unknown_retailer_with_zero(
    sample_product_master, sample_historical_rates, tiny_model
):
    pos = pd.DataFrame(
        {
            "order_id": ["PO-Z"],
            "retailer_id": ["RET-BRAND-NEW"],
            "sku": ["SKU-A"],
            "order_date": pd.to_datetime(["2027-03-01"]),
            "order_value": [100.0],
        }
    )
    rates = pd.DataFrame(
        {"sku": ["SKU-A"], "retailer_id": ["RET-BRAND-NEW"], "sku_prior_chargeback_rate": [0.1]}
    )
    df = build_product_quality_flags(pos, sample_product_master)
    df = build_compliance_defaults(df)
    df = attach_prior_chargeback_rate(df, rates)
    X = build_feature_matrix(df, tiny_model)
    # retailer_RET_1 and retailer_RET_2 columns should be 0 for unknown retailer
    if "retailer_RET_1" in X.columns:
        assert X.iloc[0]["retailer_RET_1"] == 0
    if "retailer_RET_2" in X.columns:
        assert X.iloc[0]["retailer_RET_2"] == 0


def test_feature_matrix_excludes_metadata_columns(
    sample_pos, sample_product_master, sample_historical_rates, tiny_model
):
    df = build_product_quality_flags(sample_pos, sample_product_master)
    df = build_compliance_defaults(df)
    df = attach_prior_chargeback_rate(df, sample_historical_rates)
    X = build_feature_matrix(df, tiny_model)
    for col in ("order_id", "sku", "order_date", "order_value", "retailer_id"):
        assert col not in X.columns


# ---------------------------------------------------------------------------
# score_pos — integration
# ---------------------------------------------------------------------------


def test_score_pos_row_count_matches_input(
    sample_pos, sample_product_master, sample_historical_rates, tiny_model
):
    result = score_pos(
        sample_pos, sample_product_master, sample_historical_rates, tiny_model
    )
    assert len(result) == len(sample_pos)


def test_score_pos_probability_in_valid_range(
    sample_pos, sample_product_master, sample_historical_rates, tiny_model
):
    result = score_pos(
        sample_pos, sample_product_master, sample_historical_rates, tiny_model
    )
    assert (result["chargeback_probability"] >= 0).all()
    assert (result["chargeback_probability"] <= 1).all()


def test_score_pos_dollar_exposure_is_nonneg(
    sample_pos, sample_product_master, sample_historical_rates, tiny_model
):
    result = score_pos(
        sample_pos, sample_product_master, sample_historical_rates, tiny_model
    )
    assert (result["dollar_exposure"] >= 0).all()


def test_score_pos_sorted_by_dollar_exposure_descending(
    sample_pos, sample_product_master, sample_historical_rates, tiny_model
):
    result = score_pos(
        sample_pos, sample_product_master, sample_historical_rates, tiny_model
    )
    exposures = result["dollar_exposure"].tolist()
    assert exposures == sorted(exposures, reverse=True)


def test_score_pos_risk_tier_column_present(
    sample_pos, sample_product_master, sample_historical_rates, tiny_model
):
    result = score_pos(
        sample_pos, sample_product_master, sample_historical_rates, tiny_model
    )
    assert "risk_tier" in result.columns
    assert set(result["risk_tier"]).issubset({"HIGH", "MEDIUM", "LOW"})
