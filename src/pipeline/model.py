"""
Interpretable model training and SHAP attribution for the chargeback prediction model (Move 3).

Pure functions — all accept DataFrames and return typed artifacts. Testable without
a live database connection. Called by 04_model.py (the pipeline runner).
"""

import logging
from typing import Any

import pandas as pd
import shap
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import precision_score, recall_score, roc_auc_score
from sklearn.utils.class_weight import compute_sample_weight

logger = logging.getLogger(__name__)

AUC_GATE = 0.65
TEST_FRACTION = 0.20

_NON_FEATURE_COLS = {"order_id", "ship_date", "sku", "chargeback"}

FEATURE_LABELS: dict[str, str] = {
    "gtin14_missing": "Missing GTIN-14",
    "upc_missing": "Missing UPC",
    "case_dims_missing": "Missing case dimensions",
    "case_weight_missing": "Missing case weight",
    "data_quality_score": "Low data quality score",
    "asn_sent_late": "Late ASN",
    "days_late": "Late delivery",
    "all_labels_scannable": "Label compliance issue",
    "sku_prior_chargeback_rate": "Prior chargeback history",
    "ship_month": "Shipment month",
    "ship_quarter": "Shipment quarter",
}

FEATURE_ARCHETYPES: dict[str, str] = {
    "gtin14_missing": "data compliance error",
    "upc_missing": "data compliance error",
    "case_dims_missing": "logistics audit",
    "case_weight_missing": "logistics audit",
    "data_quality_score": "data compliance error",
    "asn_sent_late": "ASN timing error",
    "days_late": "delivery timing",
    "all_labels_scannable": "labeling error",
    "sku_prior_chargeback_rate": "historical pattern",
    "ship_month": "seasonal timing",
    "ship_quarter": "seasonal timing",
}


def get_feature_columns(df: pd.DataFrame) -> list[str]:
    """Return feature column names: numeric/bool columns excluding metadata."""
    return [
        col for col in df.select_dtypes(include=["number", "bool"]).columns
        if col not in _NON_FEATURE_COLS
    ]


def temporal_split(
    df: pd.DataFrame,
    test_fraction: float = TEST_FRACTION,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split df temporally: earlier rows → train, later rows → test.

    Sorts by ship_date ascending; the last test_fraction of rows form the test
    set. Never shuffles — shuffling would leak future chargeback rates into
    training features.
    """
    df_sorted = df.sort_values("ship_date").reset_index(drop=True)
    n = len(df_sorted)
    split_idx = int(n * (1 - test_fraction))
    return df_sorted.iloc[:split_idx].copy(), df_sorted.iloc[split_idx:].copy()


def train_model(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    n_estimators: int = 300,
    learning_rate: float = 0.03,
    max_depth: int = 5,
    random_state: int = 42,
) -> GradientBoostingClassifier:
    """Fit a GradientBoostingClassifier with balanced sample weights.

    GBM outperforms RF on this dataset because it iteratively corrects
    residuals — more effective when the positive class is rare (<1%) and
    a single feature (sku_prior_chargeback_rate) dominates the signal.
    sample_weight='balanced' replaces RF's class_weight, which GBM lacks.
    """
    sample_weights = compute_sample_weight("balanced", y_train)
    model = GradientBoostingClassifier(
        n_estimators=n_estimators,
        learning_rate=learning_rate,
        max_depth=max_depth,
        random_state=random_state,
    )
    model.fit(X_train.astype(float), y_train, sample_weight=sample_weights)
    logger.info(
        "Trained GradientBoosting on %d rows, %d features",
        len(X_train), X_train.shape[1],
    )
    return model


def evaluate_model(
    model: GradientBoostingClassifier,
    X_test: pd.DataFrame,
    y_test: pd.Series,
    n_train: int,
) -> dict[str, Any]:
    """Compute AUC, precision, recall on the held-out test set.

    Returns a flat dict suitable for a one-row CSV. n_train is passed in
    because this function only sees X_test.
    """
    proba = model.predict_proba(X_test.astype(float))[:, 1]
    pred = (proba >= 0.5).astype(int)

    if len(set(y_test)) < 2:
        logger.warning("Test set has only one class — AUC not computed, returning 0.0")
        auc = 0.0
    else:
        auc = float(roc_auc_score(y_test, proba))
    precision = float(precision_score(y_test, pred, zero_division=0))
    recall = float(recall_score(y_test, pred, zero_division=0))

    metrics: dict[str, Any] = {
        "auc": round(auc, 4),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "n_train": n_train,
        "n_test": len(X_test),
    }
    logger.info(
        "Metrics: AUC=%.4f  precision=%.4f  recall=%.4f",
        auc, precision, recall,
    )
    return metrics


def compute_shap_values(
    model: GradientBoostingClassifier,
    X: pd.DataFrame,
) -> pd.DataFrame:
    """Compute SHAP values for class 1 (chargeback) using TreeExplainer.

    Returns a DataFrame with the same columns as X and per-feature SHAP values
    as the values. shap_values() may return a list [class_0, class_1] or a 3-D
    array depending on the shap version — both cases are handled.
    """
    explainer = shap.TreeExplainer(model)
    raw = explainer.shap_values(X.astype(float))

    if isinstance(raw, list):
        vals = raw[1]          # list[class_0, class_1] — RF / old shap API
    elif raw.ndim == 3:
        vals = raw[:, :, 1]    # shape (n_samples, n_features, n_classes) — legacy shap
    else:
        vals = raw             # shape (n_samples, n_features) — GBM binary classification

    return pd.DataFrame(vals, columns=X.columns, index=X.index)


def _resolve_label(feature: str) -> str:
    """Map a feature column name to a human-readable label."""
    if feature in FEATURE_LABELS:
        return FEATURE_LABELS[feature]
    if feature.startswith("retailer_"):
        retailer_id = feature[len("retailer_"):]
        return f"Retailer {retailer_id}"
    return feature.replace("_", " ").title()


def _resolve_archetype(feature: str) -> str:
    """Map a feature column name to its root-cause archetype."""
    if feature in FEATURE_ARCHETYPES:
        return FEATURE_ARCHETYPES[feature]
    if feature.startswith("retailer_"):
        return "retailer relationship"
    return "unknown"


def build_attribution_string(
    probability: float,
    shap_row: pd.Series,
) -> str:
    """Build a plain-language attribution string for one prediction.

    Identifies the top-1 feature with the largest positive SHAP contribution.
    When all SHAP values are negative (model predicts low risk for every feature),
    picks the least-negative to identify the dominant factor.

    Template: "{label} → {archetype} → {probability:.0%} probability within 14 days"
    """
    positive = shap_row[shap_row > 0]
    top_feature = positive.idxmax() if not positive.empty else shap_row.abs().idxmax()

    label = _resolve_label(top_feature)
    archetype = _resolve_archetype(top_feature)
    return f"{label} → {archetype} → {probability:.0%} probability within 14 days"


def build_attribution_strings(
    probabilities: pd.Series,
    shap_df: pd.DataFrame,
) -> pd.Series:
    """Build attribution strings for all rows.

    probabilities: predicted chargeback probabilities aligned with shap_df.index.
    shap_df: per-feature SHAP values (from compute_shap_values).
    Returns: Series of attribution strings with the same index.
    """
    strings = [
        build_attribution_string(prob, shap_df.loc[idx])
        for idx, prob in probabilities.items()
    ]
    return pd.Series(strings, index=probabilities.index, name="attribution")
