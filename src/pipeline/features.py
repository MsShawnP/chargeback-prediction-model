"""
Point-in-time feature engineering for the chargeback prediction model (Move 2).

Pure functions — all accept DataFrames and return DataFrames.  Testable without
a live database connection.  Called by 03_features.py (the pipeline runner).
"""

import logging

import pandas as pd

logger = logging.getLogger(__name__)

CHARGEBACK_WINDOW_DAYS = 90

_QUALITY_KEYS = ("gtin14", "upc", "case_dims", "case_weight")
_PMH_COLS = (
    "sku", "snapshot_date",
    "gtin14_present", "upc_present", "case_dims_present",
    "case_weight_present", "data_quality_score",
)


def build_chargeback_labels(
    shipments_df: pd.DataFrame,
    chargebacks_df: pd.DataFrame,
    window_days: int = CHARGEBACK_WINDOW_DAYS,
) -> pd.DataFrame:
    """Add chargeback column (0/1) to shipments_df.

    Label = 1 if any chargeback for (retailer_id, sku) falls within
    [ship_date, ship_date + window_days].  Uses a temporary _row_id to
    preserve the original row structure after the fan-out merge.

    EDA finding (U1): retailer_shipments has retailer_id and sku directly —
    no multi-hop through retailer_orders needed.
    """
    df = shipments_df.copy().reset_index(drop=True)
    df["_row_id"] = df.index

    probe = df[["_row_id", "retailer_id", "sku", "ship_date"]].merge(
        chargebacks_df[["retailer_id", "sku", "chargeback_date"]],
        on=["retailer_id", "sku"],
        how="left",
    )
    cutoff = probe["ship_date"] + pd.Timedelta(days=window_days)
    probe["_in_window"] = (
        probe["chargeback_date"].notna()
        & (probe["chargeback_date"] >= probe["ship_date"])
        & (probe["chargeback_date"] <= cutoff)
    )

    flags = probe.groupby("_row_id")["_in_window"].any()
    df["chargeback"] = df["_row_id"].map(flags).fillna(False).astype(int)
    return df.drop(columns=["_row_id"])


def add_product_quality_features(
    df: pd.DataFrame,
    pmh_df: pd.DataFrame,
) -> pd.DataFrame:
    """Point-in-time join: attach data quality flags from product_master_history.

    For each (sku, ship_date) row finds the most recent snapshot where
    snapshot_date <= ship_date (pd.merge_asof, direction='backward').
    No matching history → assume all fields absent (missing=True).
    """
    df_sorted = df.sort_values("ship_date").reset_index(drop=True)
    pmh_sorted = (
        pd.DataFrame(pmh_df)[list(_PMH_COLS)]
        .sort_values("snapshot_date")
        .reset_index(drop=True)
    )

    result = pd.merge_asof(
        df_sorted,
        pmh_sorted,
        left_on="ship_date",
        right_on="snapshot_date",
        by="sku",
        direction="backward",
    )

    for key in _QUALITY_KEYS:
        # fillna(False): no historical record → assume field absent → missing=True
        result[f"{key}_missing"] = ~result[f"{key}_present"].fillna(False)

    drop_cols = ["snapshot_date"] + [f"{k}_present" for k in _QUALITY_KEYS]
    return result.drop(columns=drop_cols, errors="ignore")


def add_shipment_compliance_features(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure compliance columns exist; fill missing ones with safe defaults."""
    result = df.copy()

    if "asn_sent_late" not in result.columns:
        logger.warning("asn_sent_late missing — defaulting to False")
        result["asn_sent_late"] = False
    result["asn_sent_late"] = result["asn_sent_late"].fillna(False).astype(bool)

    if "days_late" not in result.columns:
        if "delivery_date" in result.columns and "requested_ship_date" in result.columns:
            result["days_late"] = (
                result["delivery_date"] - result["requested_ship_date"]
            ).dt.days.clip(lower=0)
        else:
            logger.warning("days_late unavailable — defaulting to 0")
            result["days_late"] = 0
    result["days_late"] = result["days_late"].fillna(0)

    if "all_labels_scannable" not in result.columns:
        result["all_labels_scannable"] = True
    result["all_labels_scannable"] = (
        result["all_labels_scannable"].fillna(True).astype(bool)
    )

    return result


def add_prior_chargeback_rate(df: pd.DataFrame) -> pd.DataFrame:
    """Add sku_prior_chargeback_rate via expanding window with no data leakage.

    For each row uses only (sku, retailer_id) rows with ship_date strictly
    before the current row.  First shipments in a group receive the
    dataset-wide mean.

    Uses groupby.transform so the shift stays within each group — a plain
    Series.shift(1) crosses group boundaries when groups are contiguous after
    the sort, leaking the tail of one group into the head of the next.
    """
    df = df.copy().sort_values(["sku", "retailer_id", "ship_date"]).reset_index(drop=True)
    dataset_mean = df["chargeback"].mean()

    def _rate_within_group(s: pd.Series) -> pd.Series:
        cum_sum = s.cumsum().shift(1)                               # NaN for first row
        cum_count = pd.Series(range(len(s)), index=s.index, dtype=float)  # 0, 1, 2, ...
        rate = cum_sum / cum_count                                  # NaN for first row
        rate.iloc[0] = dataset_mean                                 # no prior history
        return rate

    df["sku_prior_chargeback_rate"] = (
        df.groupby(["sku", "retailer_id"], sort=False)["chargeback"]
        .transform(_rate_within_group)
    )
    return df


def encode_and_impute(df: pd.DataFrame) -> pd.DataFrame:
    """One-hot encode retailer_id; impute numeric NaN with column mean.

    Asserts no NaN remains in numeric or boolean columns after imputation.
    Keeps order_id, ship_date, and sku for downstream use by U5.
    """
    retailer_dummies = pd.get_dummies(df["retailer_id"], prefix="retailer", prefix_sep="_")
    # Retailer IDs may contain hyphens — sanitize to valid Python identifiers
    retailer_dummies.columns = retailer_dummies.columns.str.replace(
        r"[^a-zA-Z0-9_]", "_", regex=True
    )
    df = pd.concat([df.drop(columns=["retailer_id"]), retailer_dummies], axis=1)

    for col in df.select_dtypes(include="number").columns:
        n_null = int(df[col].isna().sum())
        if n_null:
            fill = df[col].mean()
            df[col] = df[col].fillna(fill)
            logger.debug("Imputed %d NaN in '%s' with mean %.4f", n_null, col, fill)

    check_cols = df.select_dtypes(include=["number", "bool"]).columns
    n_remaining = int(df[check_cols].isna().sum().sum())
    assert n_remaining == 0, (
        f"{n_remaining} NaN values remain in feature columns after imputation"
    )
    return df


def build_training_features(
    shipments_df: pd.DataFrame,
    chargebacks_df: pd.DataFrame,
    pmh_df: pd.DataFrame,
) -> pd.DataFrame:
    """Full feature engineering pipeline. Returns one row per shipment."""
    df = build_chargeback_labels(shipments_df, chargebacks_df)
    df = add_product_quality_features(df, pmh_df)
    df = add_shipment_compliance_features(df)
    df = add_prior_chargeback_rate(df)
    df = encode_and_impute(df)

    n_cb = int(df["chargeback"].sum())
    logger.info(
        "Training features: %d rows, %d chargebacks (%.1f%%)",
        len(df), n_cb, 100 * n_cb / len(df),
    )
    return df
