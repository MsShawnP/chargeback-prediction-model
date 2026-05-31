"""
Pipeline step 5: forward risk scoring (Move 4).

Loads the trained model and training features, queries Cinderhaven for
upcoming purchase orders and current product master, scores each PO for
chargeback risk, and writes scored_pos.parquet.

All scoring logic lives in src/pipeline/scoring.py (importable module).
This file is the pipeline runner only.
"""

import logging
import sys
from pathlib import Path

import joblib
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.pipeline.db import query_to_df  # noqa: E402
from src.pipeline.scoring import score_pos  # noqa: E402

logger = logging.getLogger(__name__)

FRAMES_DIR = Path("output/frames")
MODEL_DIR = Path("output/model")


def _load_historical_rates(frames_dir: Path) -> pd.DataFrame:
    """Derive per-(sku, retailer_id) chargeback rates from the training feature frame."""
    training = pd.read_parquet(frames_dir / "training_features.parquet")
    rates = (
        training.groupby(["sku", "retailer_id"])["sku_prior_chargeback_rate"]
        .mean()
        .reset_index()
    )
    return rates


def run(frames_dir: Path = FRAMES_DIR, model_dir: Path = MODEL_DIR) -> None:
    """Score upcoming POs; write scored_pos.parquet."""
    model = joblib.load(model_dir / "chargeback_model.joblib")
    historical_rates = _load_historical_rates(frames_dir)
    default_rate = float(historical_rates["sku_prior_chargeback_rate"].mean())

    # Pull orders that have no matched shipment yet (upcoming / in-flight)
    pos_df = query_to_df("""
        SELECT
            o.order_id,
            o.retailer_id,
            ol.sku,
            o.order_date,
            SUM(ol.quantity * ol.unit_price) AS order_value
        FROM raw.retailer_orders o
        JOIN raw.retailer_order_lines ol USING (order_id)
        WHERE o.order_id NOT IN (
            SELECT DISTINCT order_id FROM raw.retailer_shipments
        )
        GROUP BY o.order_id, o.retailer_id, ol.sku, o.order_date
    """)

    if pos_df.empty:
        logger.warning("No upcoming POs found — scored_pos.parquet will be empty")

    product_master_df = query_to_df("SELECT * FROM raw.product_master")

    scored = score_pos(
        pos_df=pos_df,
        product_master_df=product_master_df,
        historical_rates_df=historical_rates,
        model=model,
        default_rate=default_rate,
    )

    frames_dir.mkdir(parents=True, exist_ok=True)
    out_path = frames_dir / "scored_pos.parquet"
    scored.to_parquet(out_path, index=False)
    logger.info(
        "Scored %d POs — top dollar_exposure: $%.0f",
        len(scored),
        scored["dollar_exposure"].max() if len(scored) else 0,
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    run()
