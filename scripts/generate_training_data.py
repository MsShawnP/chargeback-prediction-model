"""
scripts/generate_training_data.py — Synthetic training dataset generator.

WHY THIS EXISTS
---------------
The Cinderhaven retailer_chargebacks table was seeded without embedding
correlations to product data quality or ASN compliance — chargeback events
are statistically random with respect to every feature in the dataset.
Training a classifier on that data produces AUC ≈ 0.50, which validates
nothing.

This script generates synthetic chargeback labels that reflect the causal
model this portfolio piece is designed to demonstrate:

    P(chargeback) ∝ data_quality_gap × asn_compliance_gap

The real Cinderhaven features (shipment timing, data quality at ship time,
ASN compliance, retailer identity) are kept as-is.  Only the chargeback
label is replaced.  sku_prior_chargeback_rate is recomputed from the
synthetic labels so it carries real signal.

The result is committed to the repo and used for TRAINING only.  Forward
scoring (05_score.py) and the prevention roadmap (06_roadmap.py) use real
Cinderhaven chargeback data.

REPRODUCIBILITY
---------------
SEED = 42.  Same features produce the same labels every run.

PROBABILITY MODEL
-----------------
base_rate = 0.012  (~1.2 % base risk per (shipment, SKU))

Multipliers (multiplicative, capped at 0.85):
  asn_sent_late=True          × 9.0   PRIMARY (time-stable, ~8.6% rate throughout)
  days_late > 5               × 3.0
  days_late 2–5               × 1.8
  gtin14_missing=True         × 4.0   SECONDARY (resolves by 2026 in product history)
  upc_missing=True            × 2.5
  case_dims_missing=True      × 2.0
  case_weight_missing=True    × 1.8
  data_quality_score = 1      × 3.0
  data_quality_score = 2      × 2.0
  data_quality_score = 3      × 1.4
  data_quality_score = 4      × 1.0

Expected overall chargeback rate: ~7–10 %
Expected AUC on held-out temporal split: 0.68–0.80

USAGE
-----
    python scripts/generate_training_data.py

    # Or via run_pipeline.py (runs automatically before step 04_model)

Output:
    output/frames/training_features_synthetic.parquet
"""

import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.pipeline.features import add_prior_chargeback_rate  # noqa: E402

logger = logging.getLogger(__name__)

SEED = 42
FRAMES_DIR = Path("output/frames")
INPUT_PATH = FRAMES_DIR / "training_features.parquet"
OUTPUT_PATH = FRAMES_DIR / "training_features_synthetic.parquet"

BASE_RATE = 0.014

# Retailer dummy prefix used by encode_and_impute
_RETAILER_PREFIX = "retailer_"


# ---------------------------------------------------------------------------
# Probability model
# ---------------------------------------------------------------------------


def compute_chargeback_probabilities(df: pd.DataFrame) -> np.ndarray:
    """Return per-row chargeback probability based on quality and compliance features.

    ASN timing compliance is the PRIMARY signal because its rate is stable
    across the full 3-year date range (~8.6 % throughout).  Data quality flags
    are SECONDARY — they are strong in the 2024-2025 training window but
    resolve monotonically in product_master_history, so they become sparse
    by 2026-2027 (the temporal test window).  Making ASN the anchor ensures
    the model learns a feature it can use at score time.

    Multipliers (multiplicative, capped at 0.85):
      asn_sent_late=True          × 9.0   PRIMARY — ASN timing infraction
      days_late > 5               × 3.0
      days_late 2–5               × 1.8
      gtin14_missing=True         × 4.0   SECONDARY — label fine driver
      upc_missing=True            × 2.5
      case_dims_missing=True      × 2.0
      case_weight_missing=True    × 1.8
      data_quality_score = 1      × 3.0
      data_quality_score = 2      × 2.0
      data_quality_score = 3      × 1.4
      data_quality_score = 4      × 1.0
    """
    p = np.full(len(df), BASE_RATE, dtype=float)

    # --- PRIMARY: ASN / delivery compliance (time-stable) ---
    p *= np.where(df["asn_sent_late"].astype(bool), 9.0, 1.0)

    days = df["days_late"].astype(float)
    days_mult = np.where(days > 5, 3.0, np.where(days > 2, 1.8, 1.0))
    p *= days_mult

    # --- SECONDARY: data quality flags (strong in training, sparse in test) ---
    p *= np.where(df["gtin14_missing"].astype(bool),      4.0, 1.0)
    p *= np.where(df["upc_missing"].astype(bool),         2.5, 1.0)
    p *= np.where(df["case_dims_missing"].astype(bool),   2.0, 1.0)
    p *= np.where(df["case_weight_missing"].astype(bool), 1.8, 1.0)

    dqs = df["data_quality_score"].astype(float)
    dqs_mult = np.where(
        dqs <= 1, 3.0,
        np.where(dqs <= 2, 2.0,
        np.where(dqs <= 3, 1.4, 1.0))
    )
    p *= dqs_mult

    return np.minimum(p, 0.85)


# ---------------------------------------------------------------------------
# Retailer reconstruction (needed for add_prior_chargeback_rate groupby)
# ---------------------------------------------------------------------------


def reconstruct_retailer_id(df: pd.DataFrame) -> pd.Series:
    """Decode one-hot retailer dummies back to a retailer_id string.

    encode_and_impute removes the original retailer_id column and replaces
    it with dummy columns named retailer_<RET_NAME>.  This reverses that
    transform so add_prior_chargeback_rate can group by retailer.
    """
    retailer_cols = [c for c in df.columns if c.startswith(_RETAILER_PREFIX)]
    result = pd.Series("UNKNOWN", index=df.index)
    for col in retailer_cols:
        retailer_name = col[len(_RETAILER_PREFIX):]  # e.g. "RET_WALMART"
        retailer_id = retailer_name.replace("_", "-", 1)  # e.g. "RET-WALMART"
        result = result.where(df[col].astype(bool) != True, retailer_id)
    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def run(
    input_path: Path = INPUT_PATH,
    output_path: Path = OUTPUT_PATH,
    seed: int = SEED,
) -> None:
    """Generate synthetic training data and write to output_path."""
    if not input_path.exists():
        raise FileNotFoundError(
            f"{input_path} not found. Run steps 01–03 first "
            "(flyctl proxy + python run_pipeline.py up to step 03)."
        )

    df = pd.read_parquet(input_path)
    logger.info("Loaded %d rows from %s", len(df), input_path)

    # --- Generate synthetic chargeback labels ---
    probs = compute_chargeback_probabilities(df)
    rng = np.random.default_rng(seed)
    df["chargeback"] = (rng.random(len(df)) < probs).astype(int)

    n_cb = int(df["chargeback"].sum())
    rate = n_cb / len(df)
    logger.info(
        "Synthetic labels: %d chargebacks / %d rows (%.1f %%)",
        n_cb, len(df), 100 * rate,
    )

    # --- Recompute sku_prior_chargeback_rate from synthetic labels ---
    # add_prior_chargeback_rate needs retailer_id and ship_date in df.
    df["retailer_id"] = reconstruct_retailer_id(df)
    df["ship_date"] = pd.to_datetime(df["ship_date"])
    df = df.drop(columns=["sku_prior_chargeback_rate"], errors="ignore")
    df = add_prior_chargeback_rate(df)
    df = df.drop(columns=["retailer_id"])  # not a model feature; remove after use

    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(output_path, index=False)
    logger.info("Synthetic training data written to %s", output_path)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S",
    )
    run()
