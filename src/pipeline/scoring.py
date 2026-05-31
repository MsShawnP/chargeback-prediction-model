"""
Forward risk scoring for the chargeback prediction model (Move 4).

Pure functions — testable without a live database or saved model file.
Called by 05_score.py (the pipeline runner).

Forward scoring uses current product_master state (not point-in-time history)
because we are assessing risk for orders that have not yet shipped.  The
point-in-time join in features.py is correct for historical training; this
module is correct for forward prediction.
"""

import logging

import pandas as pd

logger = logging.getLogger(__name__)

# Probability thresholds for risk tier assignment
RISK_TIER_HIGH = 0.50
RISK_TIER_MEDIUM = 0.25


def build_product_quality_flags(
    pos_df: pd.DataFrame,
    product_master_df: pd.DataFrame,
) -> pd.DataFrame:
    """Join current product quality flags from product_master to each PO row.

    SKUs absent from product_master are treated as fully missing (worst case)
    since an unknown SKU has no verified data quality.

    product_master_df must have column: sku.
    Recognized optional columns: gtin14, upc, case_length_in, case_width_in,
    case_height_in, case_weight_lbs.
    """
    pm = product_master_df.set_index("sku")
    df = pos_df.copy()

    def _map(col: str) -> pd.Series:
        if col in pm.columns:
            return df["sku"].map(pm[col])
        return pd.Series(pd.NA, index=df.index)

    gtin14 = _map("gtin14")
    upc = _map("upc")
    case_len = _map("case_length_in")
    case_wid = _map("case_width_in")
    case_hgt = _map("case_height_in")
    case_wt = _map("case_weight_lbs")

    df["gtin14_missing"] = gtin14.isna()
    df["upc_missing"] = upc.isna()
    df["case_dims_missing"] = case_len.isna() | case_wid.isna() | case_hgt.isna()
    df["case_weight_missing"] = case_wt.isna()
    df["data_quality_score"] = (
        (~df["gtin14_missing"]).astype(int)
        + (~df["upc_missing"]).astype(int)
        + (~df["case_dims_missing"]).astype(int)
        + (~df["case_weight_missing"]).astype(int)
    ).astype(float)

    return df


def build_compliance_defaults(df: pd.DataFrame) -> pd.DataFrame:
    """Fill compliance features with conservative forward-looking defaults.

    For orders that have not yet shipped, ASN status and delivery timing are
    unknown.  Defaults assume compliance (optimistic), so any predicted risk
    is driven by data quality signals rather than assumed future compliance
    failures.
    """
    result = df.copy()
    result["asn_sent_late"] = False
    result["days_late"] = 0.0
    result["all_labels_scannable"] = True
    return result


def attach_prior_chargeback_rate(
    df: pd.DataFrame,
    historical_rates_df: pd.DataFrame,
    default_rate: float = 0.0,
) -> pd.DataFrame:
    """Merge historical chargeback rate per (sku, retailer_id) into each PO row.

    historical_rates_df must have columns: sku, retailer_id, sku_prior_chargeback_rate.
    PO rows with no historical match receive default_rate.
    """
    merged = df.merge(
        historical_rates_df[["sku", "retailer_id", "sku_prior_chargeback_rate"]],
        on=["sku", "retailer_id"],
        how="left",
    )
    merged["sku_prior_chargeback_rate"] = (
        merged["sku_prior_chargeback_rate"].fillna(default_rate)
    )
    return merged


def build_feature_matrix(
    df: pd.DataFrame,
    model,
) -> pd.DataFrame:
    """One-hot encode retailer_id and align columns to model.feature_names_in_.

    Columns absent from the model's training set are dropped; columns the
    model expects but this DataFrame lacks are filled with 0.  This handles
    both new retailers (unknown to model → 0) and retailers in training that
    don't appear in the current PO batch.
    """
    retailer_dummies = pd.get_dummies(df["retailer_id"], prefix="retailer", prefix_sep="_")
    retailer_dummies.columns = retailer_dummies.columns.str.replace(
        r"[^a-zA-Z0-9_]", "_", regex=True
    )
    features = pd.concat(
        [df.drop(columns=["retailer_id"], errors="ignore"), retailer_dummies],
        axis=1,
    )

    # Drop metadata columns that are not model features
    for col in ("order_id", "sku", "order_date", "ship_date", "order_value"):
        if col in features.columns:
            features = features.drop(columns=[col])

    expected = list(model.feature_names_in_)
    return features.reindex(columns=expected, fill_value=0).astype(float)


def compute_dollar_exposure(df: pd.DataFrame) -> pd.DataFrame:
    """Add dollar_exposure = order_value × chargeback_probability.

    Requires chargeback_probability and order_value columns.
    """
    result = df.copy()
    result["dollar_exposure"] = (
        result["order_value"] * result["chargeback_probability"]
    ).clip(lower=0.0)
    return result


def assign_risk_tier(df: pd.DataFrame) -> pd.DataFrame:
    """Classify each row as 'high', 'medium', or 'low' by chargeback_probability."""
    result = df.copy()
    result["risk_tier"] = "low"
    result.loc[result["chargeback_probability"] >= RISK_TIER_MEDIUM, "risk_tier"] = "medium"
    result.loc[result["chargeback_probability"] >= RISK_TIER_HIGH, "risk_tier"] = "high"
    return result


def score_pos(
    pos_df: pd.DataFrame,
    product_master_df: pd.DataFrame,
    historical_rates_df: pd.DataFrame,
    model,
    default_rate: float = 0.0,
) -> pd.DataFrame:
    """Full forward scoring pipeline. Returns one row per PO, ranked by dollar_exposure.

    Attaches SHAP attribution strings when the model exposes feature_names_in_
    (requires shap and the model module).

    pos_df must have: order_id, retailer_id, sku, order_date, order_value.
    product_master_df must have: sku, gtin14, upc, case_length_in, case_width_in,
                                 case_height_in, case_weight_lbs.
    historical_rates_df must have: sku, retailer_id, sku_prior_chargeback_rate.
    """
    df = build_product_quality_flags(pos_df, product_master_df)
    df = build_compliance_defaults(df)
    df = attach_prior_chargeback_rate(df, historical_rates_df, default_rate=default_rate)

    X = build_feature_matrix(df, model)

    proba = model.predict_proba(X)[:, 1]

    result = pos_df.copy().reset_index(drop=True)
    result["chargeback_probability"] = proba
    result = compute_dollar_exposure(result)
    result = assign_risk_tier(result)

    # Attach attribution strings (imports from model module — no circular dependency)
    try:
        from src.pipeline.model import (  # noqa: PLC0415
            build_attribution_strings,
            compute_shap_values,
        )
        shap_df = compute_shap_values(model, X)
        proba_series = pd.Series(proba, index=X.index)
        result["attribution"] = build_attribution_strings(proba_series, shap_df).values
    except Exception as exc:
        logger.warning("Attribution strings skipped: %s", exc)
        result["attribution"] = ""

    return result.sort_values("dollar_exposure", ascending=False).reset_index(drop=True)
