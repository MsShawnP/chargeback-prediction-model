"""
JSON and CSV export for the chargeback prediction model (Move export / U7).

Pure functions — testable without a live database or saved artifacts.
Called by 07_export.py (the pipeline runner).

Three JSON outputs feed the React app; two CSV outputs feed Quarto reports.
"""

import json
import logging
from pathlib import Path
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# JSON builders
# ---------------------------------------------------------------------------


def build_risk_ledger(scored_pos_df: pd.DataFrame) -> list[dict[str, Any]]:
    """Convert scored POs to the risk_ledger JSON structure.

    Each element represents one purchase order.  The ship_date field is
    populated from order_date (the forward proxy) if ship_date is absent.

    scored_pos_df must have: sku, retailer_id, chargeback_probability,
    dollar_exposure, risk_tier.  Optional: order_date, ship_date, attribution.
    """
    records = []
    for _, row in scored_pos_df.reset_index(drop=True).iterrows():
        ship_date = row.get("ship_date") if "ship_date" in row.index else None
        if ship_date is None or (hasattr(ship_date, "__class__") and pd.isna(ship_date)):
            ship_date = row.get("order_date")
        if ship_date is not None and hasattr(ship_date, "isoformat"):
            ship_date = ship_date.isoformat()

        records.append(
            {
                "sku": str(row["sku"]),
                "retailer": str(row["retailer_id"]),
                "ship_date": ship_date,
                "probability": round(float(row["chargeback_probability"]), 4),
                "dollar_exposure": round(float(row["dollar_exposure"]), 2),
                "attribution_string": str(row.get("attribution") or ""),
                "risk_tier": str(row["risk_tier"]),
            }
        )
    return records


def build_simulator_payload(
    scored_pos_df: pd.DataFrame,
    shap_df: pd.DataFrame,
) -> list[dict[str, Any]]:
    """Risk ledger rows enriched with per-feature SHAP values.

    shap_df must have one row per scored PO (aligned by position) and one
    column per model feature.  The simulator uses these values to recompute
    dollar_exposure when the user toggles feature states in-browser.
    """
    ledger = build_risk_ledger(scored_pos_df)
    shap_records = shap_df.reset_index(drop=True).to_dict(orient="records")

    if len(ledger) != len(shap_records):
        raise ValueError(
            f"scored_pos_df has {len(ledger)} rows but shap_df has "
            f"{len(shap_records)} rows — they must be aligned."
        )

    result = []
    for row, shap_row in zip(ledger, shap_records):
        shap_values = {k: round(float(v), 6) for k, v in shap_row.items()}
        result.append({**row, "shap_values": shap_values})
    return result


def build_summary(
    scored_pos_df: pd.DataFrame,
    prevention_roadmap_df: pd.DataFrame,
    chargebacks_harmonized_df: pd.DataFrame,
    model_performance_df: pd.DataFrame,
) -> dict[str, Any]:
    """Compute headline summary numbers for summary.json.

    Invariant: total_preventable ≤ total_chargeback_amount because every
    preventability fraction in the roadmap is ≤ 1.0.
    """
    total_chargeback = float(chargebacks_harmonized_df["amount"].sum())
    total_preventable = (
        float(prevention_roadmap_df["prevention_value"].sum())
        if len(prevention_roadmap_df)
        else 0.0
    )
    preventable_pct = (
        round(total_preventable / total_chargeback, 4) if total_chargeback else 0.0
    )

    root_cause_counts: dict[str, int] = {}
    if "root_cause_archetype" in chargebacks_harmonized_df.columns:
        root_cause_counts = {
            k: int(v)
            for k, v in (
                chargebacks_harmonized_df.dropna(subset=["root_cause_archetype"])
                .groupby("root_cause_archetype")
                .size()
                .to_dict()
                .items()
            )
        }

    model_auc = (
        round(float(model_performance_df["auc"].iloc[0]), 4)
        if len(model_performance_df)
        else 0.0
    )

    return {
        "total_chargeback_amount": round(total_chargeback, 2),
        "total_preventable": round(total_preventable, 2),
        "preventable_pct": preventable_pct,
        "root_cause_counts": root_cause_counts,
        "model_auc": model_auc,
    }


# ---------------------------------------------------------------------------
# CSV builder
# ---------------------------------------------------------------------------


def build_chargebacks_by_archetype(
    chargebacks_harmonized_df: pd.DataFrame,
) -> pd.DataFrame:
    """Group historical chargebacks by archetype for Quarto CSV export.

    Returns one row per archetype with count, total_amount, and mean_amount.
    """
    if chargebacks_harmonized_df.empty:
        return pd.DataFrame(
            columns=["root_cause_archetype", "count", "total_amount", "mean_amount"]
        )

    clean = chargebacks_harmonized_df.dropna(subset=["root_cause_archetype"])
    if clean.empty:
        return pd.DataFrame(
            columns=["root_cause_archetype", "count", "total_amount", "mean_amount"]
        )

    result = (
        clean.groupby("root_cause_archetype")["amount"]
        .agg(count="count", total_amount="sum", mean_amount="mean")
        .reset_index()
        .sort_values("total_amount", ascending=False)
        .reset_index(drop=True)
    )
    result["total_amount"] = result["total_amount"].round(2)
    result["mean_amount"] = result["mean_amount"].round(2)
    return result


# ---------------------------------------------------------------------------
# File writer
# ---------------------------------------------------------------------------


def write_json(data: Any, path: Path) -> None:
    """Write data as indented JSON; creates parent directories if needed."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)
    logger.info("Wrote %s (%d bytes)", path, path.stat().st_size)
