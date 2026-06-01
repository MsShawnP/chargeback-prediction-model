"""Tests for the point-in-time feature engineering pipeline (U4)."""

import pandas as pd
import pytest

from src.pipeline.features import (
    add_prior_chargeback_rate,
    add_product_quality_features,
    add_shipment_compliance_features,
    add_time_features,
    build_chargeback_labels,
    build_training_features,
    encode_and_impute,
)


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def shipments():
    return pd.DataFrame(
        {
            "order_id": ["O1", "O2", "O3", "O4", "O5"],
            "retailer_id": ["RET-1", "RET-1", "RET-1", "RET-2", "RET-2"],
            "sku": ["SKU-A", "SKU-A", "SKU-B", "SKU-A", "SKU-B"],
            "ship_date": pd.to_datetime(
                ["2024-01-15", "2024-03-01", "2024-04-01", "2024-06-01", "2024-07-01"]
            ),
            "asn_sent_late": [False, True, False, False, True],
        }
    )


@pytest.fixture
def chargebacks():
    # One chargeback: SKU-A at RET-1 on 2024-02-01.
    # Falls within 90 days of O1 (Jan 15 → window ends Apr 15). ✓
    # Does NOT fall within 90 days of O2 (Mar 1 → only future dates count). ✗
    return pd.DataFrame(
        {
            "retailer_id": ["RET-1"],
            "sku": ["SKU-A"],
            "chargeback_date": pd.to_datetime(["2024-02-01"]),
            "amount": [100.0],
            "reason": ["label_fine"],
        }
    )


@pytest.fixture
def pmh():
    # SKU-A: gtin14 MISSING before 2024-04-01, PRESENT from 2024-04-01 onward.
    # SKU-B: gtin14 always present.
    return pd.DataFrame(
        {
            "sku": ["SKU-A", "SKU-A", "SKU-B"],
            "snapshot_date": pd.to_datetime(["2024-01-01", "2024-04-01", "2024-01-01"]),
            "gtin14_present": [False, True, True],
            "upc_present": [True, True, True],
            "case_dims_present": [True, True, True],
            "case_weight_present": [True, True, True],
            "data_quality_score": [3, 4, 4],
        }
    )


# ---------------------------------------------------------------------------
# build_chargeback_labels
# ---------------------------------------------------------------------------


def test_chargeback_label_is_1_when_chargeback_in_window(shipments, chargebacks):
    result = build_chargeback_labels(shipments, chargebacks)
    # O1: SKU-A, RET-1, Jan 15 — chargeback Feb 1 is within 90 days
    o1 = result[result["order_id"] == "O1"].iloc[0]
    assert o1["chargeback"] == 1


def test_chargeback_label_is_0_when_chargeback_outside_window(shipments, chargebacks):
    result = build_chargeback_labels(shipments, chargebacks)
    # O2: SKU-A, RET-1, Mar 1 — chargeback Feb 1 is BEFORE ship_date
    o2 = result[result["order_id"] == "O2"].iloc[0]
    assert o2["chargeback"] == 0


def test_chargeback_label_is_0_when_no_matching_chargeback(shipments, chargebacks):
    result = build_chargeback_labels(shipments, chargebacks)
    # O3: SKU-B, RET-1 — no chargeback exists for SKU-B
    o3 = result[result["order_id"] == "O3"].iloc[0]
    assert o3["chargeback"] == 0


def test_chargeback_label_row_count_equals_input(shipments, chargebacks):
    result = build_chargeback_labels(shipments, chargebacks)
    assert len(result) == len(shipments)


def test_chargeback_label_no_chargeback_at_all_gives_all_zeros(shipments):
    empty_cb = pd.DataFrame(
        columns=["retailer_id", "sku", "chargeback_date", "amount", "reason"]
    )
    result = build_chargeback_labels(shipments, empty_cb)
    assert result["chargeback"].sum() == 0


# ---------------------------------------------------------------------------
# add_product_quality_features — point-in-time correctness
# ---------------------------------------------------------------------------


def test_point_in_time_uses_historical_state_before_fix(shipments, chargebacks, pmh):
    labeled = build_chargeback_labels(shipments, chargebacks)
    result = add_product_quality_features(labeled, pmh)
    # O1: SKU-A, Jan 15 — best snapshot ≤ Jan 15 is Jan 1 → gtin14_present=False
    o1 = result[result["order_id"] == "O1"].iloc[0]
    assert o1["gtin14_missing"] is True or o1["gtin14_missing"] == True


def test_point_in_time_uses_updated_state_after_fix(shipments, chargebacks, pmh):
    labeled = build_chargeback_labels(shipments, chargebacks)
    result = add_product_quality_features(labeled, pmh)
    # O4: SKU-A, RET-2, Jun 1 — best snapshot ≤ Jun 1 is Apr 1 → gtin14_present=True
    o4 = result[result["order_id"] == "O4"].iloc[0]
    assert o4["gtin14_missing"] is False or o4["gtin14_missing"] == False


def test_point_in_time_does_not_use_current_state_for_historical_shipment(
    shipments, chargebacks, pmh
):
    labeled = build_chargeback_labels(shipments, chargebacks)
    result = add_product_quality_features(labeled, pmh)
    # O2: SKU-A, Mar 1 — best snapshot ≤ Mar 1 is still Jan 1 (Apr 1 > Mar 1)
    # → gtin14_present=False even though current product_master shows it present
    o2 = result[result["order_id"] == "O2"].iloc[0]
    assert o2["gtin14_missing"] is True or o2["gtin14_missing"] == True


def test_product_quality_adds_all_expected_columns(shipments, chargebacks, pmh):
    labeled = build_chargeback_labels(shipments, chargebacks)
    result = add_product_quality_features(labeled, pmh)
    for col in ("gtin14_missing", "upc_missing", "case_dims_missing", "case_weight_missing"):
        assert col in result.columns, f"Missing column: {col}"
    assert "data_quality_score" in result.columns


def test_product_quality_no_raw_present_columns_in_output(shipments, chargebacks, pmh):
    labeled = build_chargeback_labels(shipments, chargebacks)
    result = add_product_quality_features(labeled, pmh)
    for col in ("gtin14_present", "upc_present", "case_dims_present", "case_weight_present"):
        assert col not in result.columns, f"Raw present column should be removed: {col}"


# ---------------------------------------------------------------------------
# add_prior_chargeback_rate — no-leakage guarantee
# ---------------------------------------------------------------------------


def test_prior_rate_for_first_shipment_uses_dataset_mean(shipments, chargebacks):
    labeled = build_chargeback_labels(shipments, chargebacks)
    result = add_prior_chargeback_rate(labeled)
    dataset_mean = labeled["chargeback"].mean()

    # O1 is the earliest shipment for (SKU-A, RET-1) — should get dataset mean
    o1 = result[result["order_id"] == "O1"].iloc[0]
    assert abs(o1["sku_prior_chargeback_rate"] - dataset_mean) < 1e-9


def test_prior_rate_for_second_shipment_uses_only_prior_row(shipments, chargebacks):
    labeled = build_chargeback_labels(shipments, chargebacks)
    # O1 (SKU-A, RET-1, Jan 15) has chargeback=1.
    # O2 (SKU-A, RET-1, Mar 1) should see prior rate = 1.0 (one row, all chargebacks).
    result = add_prior_chargeback_rate(labeled)
    o2 = result[result["order_id"] == "O2"].iloc[0]
    assert abs(o2["sku_prior_chargeback_rate"] - 1.0) < 1e-9


def test_prior_rate_does_not_include_current_row(shipments, chargebacks):
    labeled = build_chargeback_labels(shipments, chargebacks)
    result = add_prior_chargeback_rate(labeled)
    # O4 (SKU-A, RET-2) is the first for that retailer — rate should be dataset_mean,
    # NOT influenced by O1/O2's chargeback history (different retailer).
    dataset_mean = labeled["chargeback"].mean()
    o4 = result[result["order_id"] == "O4"].iloc[0]
    assert abs(o4["sku_prior_chargeback_rate"] - dataset_mean) < 1e-9


def test_prior_rate_is_between_0_and_1(shipments, chargebacks):
    labeled = build_chargeback_labels(shipments, chargebacks)
    result = add_prior_chargeback_rate(labeled)
    rates = result["sku_prior_chargeback_rate"]
    assert (rates >= 0).all() and (rates <= 1).all()


# ---------------------------------------------------------------------------
# add_shipment_compliance_features
# ---------------------------------------------------------------------------


def test_compliance_adds_missing_columns_with_defaults(shipments, chargebacks):
    labeled = build_chargeback_labels(shipments, chargebacks)
    # Remove all compliance columns to test defaults
    labeled = labeled.drop(columns=["asn_sent_late"], errors="ignore")
    result = add_shipment_compliance_features(labeled)
    assert "asn_sent_late" in result.columns
    assert "days_late" in result.columns
    assert "all_labels_scannable" in result.columns


def test_compliance_preserves_existing_asn_sent_late(shipments, chargebacks):
    labeled = build_chargeback_labels(shipments, chargebacks)
    result = add_shipment_compliance_features(labeled)
    # O2 has asn_sent_late=True in fixture
    o2 = result[result["order_id"] == "O2"].iloc[0]
    assert o2["asn_sent_late"] is True or o2["asn_sent_late"] == True


# ---------------------------------------------------------------------------
# add_time_features
# ---------------------------------------------------------------------------


def test_add_time_features_adds_ship_month(shipments, chargebacks):
    labeled = build_chargeback_labels(shipments, chargebacks)
    result = add_time_features(labeled)
    assert "ship_month" in result.columns


def test_add_time_features_adds_ship_quarter(shipments, chargebacks):
    labeled = build_chargeback_labels(shipments, chargebacks)
    result = add_time_features(labeled)
    assert "ship_quarter" in result.columns


def test_add_time_features_month_values_in_range(shipments, chargebacks):
    labeled = build_chargeback_labels(shipments, chargebacks)
    result = add_time_features(labeled)
    assert result["ship_month"].between(1, 12).all()


def test_add_time_features_quarter_values_in_range(shipments, chargebacks):
    labeled = build_chargeback_labels(shipments, chargebacks)
    result = add_time_features(labeled)
    assert result["ship_quarter"].between(1, 4).all()


def test_add_time_features_month_matches_ship_date(shipments, chargebacks):
    labeled = build_chargeback_labels(shipments, chargebacks)
    result = add_time_features(labeled)
    expected_months = result["ship_date"].dt.month
    pd.testing.assert_series_equal(
        result["ship_month"].reset_index(drop=True),
        expected_months.reset_index(drop=True),
        check_names=False,
    )


def test_add_time_features_row_count_unchanged(shipments, chargebacks):
    labeled = build_chargeback_labels(shipments, chargebacks)
    result = add_time_features(labeled)
    assert len(result) == len(labeled)


# ---------------------------------------------------------------------------
# encode_and_impute
# ---------------------------------------------------------------------------


def test_encode_and_impute_removes_retailer_id_column(shipments, chargebacks, pmh):
    labeled = build_chargeback_labels(shipments, chargebacks)
    labeled = add_product_quality_features(labeled, pmh)
    labeled = add_shipment_compliance_features(labeled)
    labeled = add_prior_chargeback_rate(labeled)
    result = encode_and_impute(labeled)
    assert "retailer_id" not in result.columns


def test_encode_and_impute_adds_retailer_dummy_columns(shipments, chargebacks, pmh):
    labeled = build_chargeback_labels(shipments, chargebacks)
    labeled = add_product_quality_features(labeled, pmh)
    labeled = add_shipment_compliance_features(labeled)
    labeled = add_prior_chargeback_rate(labeled)
    result = encode_and_impute(labeled)
    retailer_cols = [c for c in result.columns if c.startswith("retailer_")]
    assert len(retailer_cols) >= 2


# ---------------------------------------------------------------------------
# build_training_features — integration
# ---------------------------------------------------------------------------


def test_build_training_features_row_count_equals_shipments(
    shipments, chargebacks, pmh
):
    result = build_training_features(shipments, chargebacks, pmh)
    assert len(result) == len(shipments)


def test_build_training_features_no_nan_in_numeric_or_bool_columns(
    shipments, chargebacks, pmh
):
    result = build_training_features(shipments, chargebacks, pmh)
    check = result.select_dtypes(include=["number", "bool"])
    assert check.isna().sum().sum() == 0


def test_build_training_features_chargeback_rate_matches_expected(
    shipments, chargebacks, pmh
):
    result = build_training_features(shipments, chargebacks, pmh)
    # 1 chargeback in 5 shipments = 20%
    rate = result["chargeback"].mean()
    assert abs(rate - 0.2) < 1e-9


def test_build_training_features_all_expected_columns_present(
    shipments, chargebacks, pmh
):
    result = build_training_features(shipments, chargebacks, pmh)
    expected = [
        "chargeback",
        "gtin14_missing", "upc_missing", "case_dims_missing", "case_weight_missing",
        "data_quality_score",
        "asn_sent_late", "days_late", "all_labels_scannable",
        "sku_prior_chargeback_rate",
        "ship_month", "ship_quarter",
    ]
    for col in expected:
        assert col in result.columns, f"Missing expected column: {col}"
