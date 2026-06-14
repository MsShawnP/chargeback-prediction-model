"""
Maps Cinderhaven chargeback reason codes and deduction types to canonical
root-cause archetypes.

EDA finding (U1): both fields are structured enum codes, not free text.
Harmonization is a lookup dict per pathway — no regex needed.

Add new codes to the appropriate dict when the retailer introduces them.
Unknown codes raise UnmappedCodeError rather than silently falling through —
a silent miss would corrupt the model's target labels.
"""

import logging

import pandas as pd

logger = logging.getLogger(__name__)

# Six canonical archetypes — the model's target labels and prevention roadmap
# categories. Note: item_setup_gap is assigned by feature engineering (U4)
# from product_master_history flags, not from chargeback reason codes.
ARCHETYPES = frozenset({
    "data_compliance_error",  # Label/barcode/GTIN issues
    "logistics_overage",      # Damaged, short ship, pallet, spoilage
    "asn_timing_infraction",  # Late delivery / late ASN
    "item_setup_gap",         # Missing product setup data (set by U4, not here)
    "pricing_discrepancy",    # Price or invoice mismatch
    "legitimate",             # Slotting fees, promo billbacks — not preventable
})

# retailer_chargebacks.reason → archetype
REASON_TO_ARCHETYPE: dict[str, str] = {
    "label_fine":    "data_compliance_error",
    "damaged":       "logistics_overage",
    "pricing_error": "pricing_discrepancy",
    "late_delivery": "asn_timing_infraction",
    "short_ship":              "logistics_overage",
    "receiving_discrepancy":   "data_compliance_error",
}

# retailer_deduction_codes.deduction_type → archetype
DEDUCTION_TYPE_TO_ARCHETYPE: dict[str, str] = {
    "label_fine":     "data_compliance_error",
    "short_ship":     "logistics_overage",
    "slotting":       "legitimate",
    "pricing_error":  "pricing_discrepancy",
    "damaged":        "logistics_overage",
    "spoilage":       "logistics_overage",
    "late_delivery":  "asn_timing_infraction",
    "pallet_fine":              "logistics_overage",
    "promo_billback":           "legitimate",
    "receiving_discrepancy":    "data_compliance_error",
}


class UnmappedCodeError(Exception):
    """Raised when a structured code has no entry in the mapping dict."""


def harmonize_reason(code: str) -> str:
    """Map a retailer_chargebacks.reason code to its canonical archetype."""
    try:
        return REASON_TO_ARCHETYPE[code]
    except KeyError:
        raise UnmappedCodeError(
            f"Unknown reason code {code!r}. "
            "Add it to REASON_TO_ARCHETYPE in src/harmonization/reason_codes.py."
        )


def harmonize_deduction_type(code: str) -> str:
    """Map a deduction_type code to its canonical archetype."""
    try:
        return DEDUCTION_TYPE_TO_ARCHETYPE[code]
    except KeyError:
        raise UnmappedCodeError(
            f"Unknown deduction_type {code!r}. "
            "Add it to DEDUCTION_TYPE_TO_ARCHETYPE in src/harmonization/reason_codes.py."
        )


def harmonize_chargebacks(df: pd.DataFrame) -> pd.DataFrame:
    """Add root_cause_archetype to a chargebacks DataFrame using the reason column.

    Rows with unmapped codes get None and are logged for manual review.
    Returns a copy; does not mutate the input.
    """
    archetypes = []
    for code in df["reason"]:
        try:
            archetypes.append(harmonize_reason(code))
        except UnmappedCodeError:
            logger.warning("Unmapped reason code %r — flagged for manual review", code)
            archetypes.append(None)
    result = df.copy()
    result["root_cause_archetype"] = archetypes
    return result


def harmonize_deductions(df: pd.DataFrame) -> pd.DataFrame:
    """Add root_cause_archetype to a deduction_codes DataFrame using deduction_type.

    Rows with unmapped codes get None and are logged for manual review.
    Returns a copy; does not mutate the input.
    """
    archetypes = []
    for code in df["deduction_type"]:
        try:
            archetypes.append(harmonize_deduction_type(code))
        except UnmappedCodeError:
            logger.warning("Unmapped deduction_type %r — flagged for manual review", code)
            archetypes.append(None)
    result = df.copy()
    result["root_cause_archetype"] = archetypes
    return result
