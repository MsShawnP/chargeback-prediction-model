"""Tests for the model training and SHAP attribution pipeline (U5)."""

import numpy as np
import pandas as pd
import pytest
import joblib

from src.pipeline.model import (
    AUC_GATE,
    FEATURE_LABELS,
    build_attribution_string,
    build_attribution_strings,
    compute_shap_values,
    evaluate_model,
    get_feature_columns,
    temporal_split,
    train_model,
)


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def training_df():
    """Synthetic training DataFrame with a strong learnable signal.

    gtin14_missing=True drives chargeback=1 with high probability.  The
    signal is deliberately strong so the model reliably meets AUC ≥ 0.65
    on the held-out temporal slice.
    """
    rng = np.random.default_rng(42)
    n = 300

    ship_dates = pd.date_range("2024-01-01", periods=n, freq="D")
    gtin14_missing = (rng.random(n) < 0.35).astype(bool)
    asn_sent_late = (rng.random(n) < 0.10).astype(bool)

    chargeback_prob = np.where(gtin14_missing, 0.85, 0.03)
    chargeback = (rng.random(n) < chargeback_prob).astype(int)

    return pd.DataFrame(
        {
            "order_id": [f"O{i}" for i in range(n)],
            "sku": [f"SKU-{i % 10}" for i in range(n)],
            "ship_date": ship_dates,
            "chargeback": chargeback,
            "gtin14_missing": gtin14_missing,
            "upc_missing": (rng.random(n) < 0.05).astype(bool),
            "case_dims_missing": (rng.random(n) < 0.10).astype(bool),
            "case_weight_missing": (rng.random(n) < 0.05).astype(bool),
            "data_quality_score": rng.integers(1, 5, n).astype(float),
            "asn_sent_late": asn_sent_late,
            "days_late": rng.integers(0, 15, n).astype(float),
            "all_labels_scannable": (~gtin14_missing).astype(bool),
            "sku_prior_chargeback_rate": np.where(gtin14_missing, 0.7, 0.03),
            "retailer_RET_1": (rng.random(n) < 0.5).astype(bool),
            "retailer_RET_2": (rng.random(n) < 0.5).astype(bool),
        }
    )


@pytest.fixture(scope="module")
def model_artifacts(training_df):
    """Split, train, and compute SHAP once for the whole module.

    Returns a dict with all computed artifacts so each test can pull what
    it needs without re-running the expensive steps.
    """
    train_df, test_df = temporal_split(training_df)
    feature_cols = get_feature_columns(training_df)

    X_train = train_df[feature_cols]
    y_train = train_df["chargeback"]
    X_test = test_df[feature_cols]
    y_test = test_df["chargeback"]

    model = train_model(X_train, y_train)

    X_all = pd.concat([X_train, X_test]).reset_index(drop=True)
    shap_df = compute_shap_values(model, X_all)
    proba = pd.Series(model.predict_proba(X_all.astype(float))[:, 1], index=X_all.index)

    return {
        "model": model,
        "X_train": X_train,
        "y_train": y_train,
        "X_test": X_test,
        "y_test": y_test,
        "feature_cols": feature_cols,
        "X_all": X_all,
        "shap_df": shap_df,
        "proba": proba,
    }


# ---------------------------------------------------------------------------
# temporal_split
# ---------------------------------------------------------------------------


def test_temporal_split_preserves_row_count(training_df):
    train, test = temporal_split(training_df)
    assert len(train) + len(test) == len(training_df)


def test_temporal_split_no_date_leakage(training_df):
    train, test = temporal_split(training_df)
    assert train["ship_date"].max() <= test["ship_date"].min()


def test_temporal_split_test_fraction_honored(training_df):
    train, test = temporal_split(training_df, test_fraction=0.20)
    expected_test = int(len(training_df) * 0.20)
    assert abs(len(test) - expected_test) <= 1


def test_temporal_split_train_precedes_test(training_df):
    train, test = temporal_split(training_df)
    assert train["ship_date"].max() <= test["ship_date"].min()


# ---------------------------------------------------------------------------
# train_model
# ---------------------------------------------------------------------------


def test_model_trains_without_error(model_artifacts):
    assert model_artifacts["model"] is not None


def test_model_has_correct_feature_importances_length(model_artifacts):
    model = model_artifacts["model"]
    feature_cols = model_artifacts["feature_cols"]
    assert len(model.feature_importances_) == len(feature_cols)


def test_model_predict_proba_output_shape(model_artifacts):
    model = model_artifacts["model"]
    X_test = model_artifacts["X_test"]
    proba = model.predict_proba(X_test.astype(float))
    assert proba.shape == (len(X_test), 2)
    assert (proba >= 0).all() and (proba <= 1).all()


# ---------------------------------------------------------------------------
# evaluate_model
# ---------------------------------------------------------------------------


def test_evaluate_model_meets_auc_gate(model_artifacts):
    m = model_artifacts
    metrics = evaluate_model(m["model"], m["X_test"], m["y_test"], n_train=len(m["X_train"]))
    assert metrics["auc"] >= AUC_GATE, (
        f"AUC {metrics['auc']:.4f} is below the hard gate {AUC_GATE}"
    )


def test_evaluate_model_returns_correct_keys(model_artifacts):
    m = model_artifacts
    metrics = evaluate_model(m["model"], m["X_test"], m["y_test"], n_train=len(m["X_train"]))
    assert set(metrics.keys()) == {"auc", "precision", "recall", "n_train", "n_test"}


def test_evaluate_model_n_train_n_test_correct(model_artifacts):
    m = model_artifacts
    metrics = evaluate_model(m["model"], m["X_test"], m["y_test"], n_train=len(m["X_train"]))
    assert metrics["n_train"] == len(m["X_train"])
    assert metrics["n_test"] == len(m["X_test"])


def test_evaluate_model_metrics_in_valid_range(model_artifacts):
    m = model_artifacts
    metrics = evaluate_model(m["model"], m["X_test"], m["y_test"], n_train=len(m["X_train"]))
    assert 0.0 <= metrics["auc"] <= 1.0
    assert 0.0 <= metrics["precision"] <= 1.0
    assert 0.0 <= metrics["recall"] <= 1.0


def test_auc_gate_constant_is_0_65():
    assert AUC_GATE == 0.65


# ---------------------------------------------------------------------------
# compute_shap_values
# ---------------------------------------------------------------------------


def test_shap_values_shape_matches_input(model_artifacts):
    shap_df = model_artifacts["shap_df"]
    X_all = model_artifacts["X_all"]
    assert shap_df.shape == X_all.shape


def test_shap_columns_match_feature_columns(model_artifacts):
    shap_df = model_artifacts["shap_df"]
    X_all = model_artifacts["X_all"]
    assert list(shap_df.columns) == list(X_all.columns)


def test_shap_values_are_numeric(model_artifacts):
    shap_df = model_artifacts["shap_df"]
    assert shap_df.select_dtypes(include="number").shape == shap_df.shape


def test_high_probability_rows_have_at_least_one_positive_shap_feature(model_artifacts):
    proba = model_artifacts["proba"]
    shap_df = model_artifacts["shap_df"]
    high_prob_mask = proba >= 0.5
    if high_prob_mask.any():
        high_shap = shap_df[high_prob_mask.values]
        assert (high_shap.max(axis=1) > 0).all(), (
            "Some high-probability rows have no positive SHAP feature"
        )


# ---------------------------------------------------------------------------
# build_attribution_string
# ---------------------------------------------------------------------------


def test_attribution_string_uses_human_readable_label_not_raw_column():
    shap_row = pd.Series({"gtin14_missing": 0.5, "asn_sent_late": 0.1})
    result = build_attribution_string(probability=0.78, shap_row=shap_row)
    assert "Missing GTIN-14" in result
    assert "gtin14_missing" not in result


def test_attribution_string_no_raw_column_names_for_any_known_feature():
    """No internal column name should appear verbatim in its attribution string."""
    for feat, label in FEATURE_LABELS.items():
        shap_row = pd.Series({feat: 0.5, "other_col": 0.1})
        result = build_attribution_string(probability=0.6, shap_row=shap_row)
        assert feat not in result, (
            f"Raw column name '{feat}' found in attribution: {result}"
        )
        assert label in result, (
            f"Expected label '{label}' not found in attribution: {result}"
        )


def test_attribution_string_contains_formatted_probability():
    shap_row = pd.Series({"gtin14_missing": 0.5})
    result = build_attribution_string(probability=0.78, shap_row=shap_row)
    assert "78%" in result


def test_attribution_string_non_empty_when_all_shap_negative():
    shap_row = pd.Series({"gtin14_missing": -0.3, "asn_sent_late": -0.1})
    result = build_attribution_string(probability=0.1, shap_row=shap_row)
    assert result and len(result) > 0


def test_attribution_string_uses_retailer_label_for_retailer_columns():
    shap_row = pd.Series({"retailer_RET_1": 0.4, "gtin14_missing": 0.1})
    result = build_attribution_string(probability=0.55, shap_row=shap_row)
    assert "Retailer" in result
    assert "retailer_RET_1" not in result


def test_attribution_string_follows_template_structure():
    shap_row = pd.Series({"gtin14_missing": 0.5})
    result = build_attribution_string(probability=0.78, shap_row=shap_row)
    # Template: "{label} → {archetype} → {probability:.0%} probability within 14 days"
    assert "→" in result
    assert "probability within 14 days" in result


# ---------------------------------------------------------------------------
# build_attribution_strings (bulk)
# ---------------------------------------------------------------------------


def test_bulk_attribution_strings_no_none_or_empty(model_artifacts):
    proba = model_artifacts["proba"]
    shap_df = model_artifacts["shap_df"]
    strings = build_attribution_strings(proba, shap_df)
    assert strings.notna().all()
    assert (strings.str.len() > 0).all()


def test_bulk_attribution_strings_length_matches_input(model_artifacts):
    proba = model_artifacts["proba"]
    shap_df = model_artifacts["shap_df"]
    strings = build_attribution_strings(proba, shap_df)
    assert len(strings) == len(proba)


def test_bulk_attribution_strings_index_matches_input(model_artifacts):
    proba = model_artifacts["proba"]
    shap_df = model_artifacts["shap_df"]
    strings = build_attribution_strings(proba, shap_df)
    assert list(strings.index) == list(proba.index)


# ---------------------------------------------------------------------------
# Model serialization (joblib round-trip)
# ---------------------------------------------------------------------------


def test_model_serializes_and_deserializes_cleanly(model_artifacts, tmp_path):
    model = model_artifacts["model"]
    X_test = model_artifacts["X_test"]
    path = tmp_path / "model.joblib"
    joblib.dump(model, path)
    loaded = joblib.load(path)
    original = model.predict_proba(X_test.astype(float))[:, 1]
    reloaded = loaded.predict_proba(X_test.astype(float))[:, 1]
    np.testing.assert_array_equal(original, reloaded)


def test_loaded_model_produces_valid_probabilities(model_artifacts, tmp_path):
    model = model_artifacts["model"]
    X_test = model_artifacts["X_test"]
    path = tmp_path / "model2.joblib"
    joblib.dump(model, path)
    loaded = joblib.load(path)
    proba = loaded.predict_proba(X_test.astype(float))[:, 1]
    assert (proba >= 0).all() and (proba <= 1).all()


# ---------------------------------------------------------------------------
# get_feature_columns
# ---------------------------------------------------------------------------


def test_get_feature_columns_excludes_metadata_columns(training_df):
    feature_cols = get_feature_columns(training_df)
    for col in ("order_id", "ship_date", "sku", "chargeback"):
        assert col not in feature_cols, f"Metadata column '{col}' should not be a feature"


def test_get_feature_columns_includes_expected_features(training_df):
    feature_cols = get_feature_columns(training_df)
    for col in ("gtin14_missing", "asn_sent_late", "days_late", "sku_prior_chargeback_rate"):
        assert col in feature_cols, f"Expected feature '{col}' missing from feature list"
