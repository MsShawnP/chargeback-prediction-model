"""
Prevention roadmap computation for the chargeback prediction model (Move 5).

Pure functions — testable without a live database.
Called by 06_roadmap.py (the pipeline runner).

Preventability fractions are informed by the project brief's $410K preventable
estimate out of ~$691K total: data quality and logistics archetypes carry the
highest prevention value.
"""

import logging

import pandas as pd

logger = logging.getLogger(__name__)

# Fraction of historical loss recoverable through operational intervention.
# Sourced from the project brief (Move 5 analysis) and industry benchmarks.
PREVENTABILITY_FRACTIONS: dict[str, float] = {
    "data_compliance_error": 0.80,
    "item_setup_gap": 0.80,
    "logistics_overage": 0.70,
    "asn_timing_infraction": 0.70,
    "pricing_discrepancy": 0.60,
    "legitimate": 0.20,
}

ARCHETYPE_FIX_DESCRIPTIONS: dict[str, str] = {
    "data_compliance_error": (
        "Populate missing barcodes (GTIN-14, UPC) and verify label compliance before shipment"
    ),
    "item_setup_gap": (
        "Complete product setup data (case dimensions, case weight) in product master "
        "before first shipment"
    ),
    "logistics_overage": (
        "Audit pick-and-pack procedures; add case-count verification before palletizing"
    ),
    "asn_timing_infraction": (
        "Submit Advance Ship Notices within the retailer-required lead time window"
    ),
    "pricing_discrepancy": (
        "Reconcile PO unit prices against approved price lists before invoicing"
    ),
    "legitimate": (
        "Review slotting and promotional agreements for accuracy; limited prevention upside"
    ),
}

_ROADMAP_COLUMNS = [
    "root_cause_archetype",
    "historical_loss",
    "preventability_fraction",
    "prevention_value",
    "fix_description",
]


def compute_prevention_roadmap(chargebacks_df: pd.DataFrame) -> pd.DataFrame:
    """Build ranked prevention roadmap from historical chargebacks.

    chargebacks_df must have: root_cause_archetype (str), amount (numeric).
    Rows with null archetype are excluded with a log warning.

    Returns a DataFrame with one row per archetype, sorted by prevention_value
    descending.  The invariant sum(prevention_value) ≤ sum(amount) holds
    because every preventability fraction is ≤ 1.0.
    """
    if chargebacks_df.empty or "root_cause_archetype" not in chargebacks_df.columns:
        logger.warning("compute_prevention_roadmap called with empty or invalid DataFrame")
        return pd.DataFrame(columns=_ROADMAP_COLUMNS)

    null_count = chargebacks_df["root_cause_archetype"].isna().sum()
    if null_count:
        logger.warning(
            "%d chargeback rows with null root_cause_archetype excluded from roadmap",
            null_count,
        )

    clean = chargebacks_df.dropna(subset=["root_cause_archetype"])
    if clean.empty:
        return pd.DataFrame(columns=_ROADMAP_COLUMNS)

    grouped = (
        clean.groupby("root_cause_archetype")["amount"]
        .sum()
        .reset_index()
        .rename(columns={"amount": "historical_loss"})
    )

    grouped["preventability_fraction"] = (
        grouped["root_cause_archetype"]
        .map(PREVENTABILITY_FRACTIONS)
        .fillna(0.0)
    )

    unknown = grouped.loc[
        ~grouped["root_cause_archetype"].isin(PREVENTABILITY_FRACTIONS),
        "root_cause_archetype",
    ].tolist()
    if unknown:
        logger.warning(
            "Archetypes with no preventability fraction (defaulted to 0): %s", unknown
        )

    grouped["prevention_value"] = (
        grouped["historical_loss"] * grouped["preventability_fraction"]
    )

    grouped["fix_description"] = (
        grouped["root_cause_archetype"]
        .map(ARCHETYPE_FIX_DESCRIPTIONS)
        .fillna("No fix description available")
    )

    return (
        grouped[_ROADMAP_COLUMNS]
        .sort_values("prevention_value", ascending=False)
        .reset_index(drop=True)
    )
