"""
Pipeline step 3: point-in-time feature engineering (Move 2).

Queries Cinderhaven, builds the labeled training feature DataFrame,
and writes it to output/frames/training_features.parquet.

All feature engineering logic lives in src/pipeline/features.py
(importable module).  This file is the pipeline runner only.
"""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.pipeline.db import query_to_df  # noqa: E402
from src.pipeline.features import build_training_features  # noqa: E402

logger = logging.getLogger(__name__)

FRAMES_DIR = Path("output/frames")


_ENRICHED_SHIPMENTS_SQL = """
SELECT
    s.shipment_id,
    s.order_id,
    s.ship_date,
    s.delivery_date,
    s.asn_sent,
    s.asn_sent_late,
    o.retailer_id,
    o.requested_ship_date,
    ol.sku,
    ol.units_ordered
FROM raw.retailer_shipments s
JOIN raw.retailer_orders      o  ON s.order_id = o.order_id
JOIN raw.retailer_order_lines ol ON o.order_id = ol.order_id
"""


def run(frames_dir: Path = FRAMES_DIR) -> None:
    """Query Cinderhaven, build training features, write to parquet."""
    import pandas as pd  # noqa: PLC0415

    shipments_df = query_to_df(_ENRICHED_SHIPMENTS_SQL)
    shipments_df["ship_date"] = pd.to_datetime(shipments_df["ship_date"])
    if "delivery_date" in shipments_df.columns:
        shipments_df["delivery_date"] = pd.to_datetime(shipments_df["delivery_date"])
    if "requested_ship_date" in shipments_df.columns:
        shipments_df["requested_ship_date"] = pd.to_datetime(
            shipments_df["requested_ship_date"]
        )

    # Alias 'month' → 'chargeback_date': source stores charge month (first of month).
    chargebacks_df = query_to_df(
        "SELECT *, month AS chargeback_date FROM raw.retailer_chargebacks"
    )
    chargebacks_df["chargeback_date"] = pd.to_datetime(chargebacks_df["chargeback_date"])

    pmh_df = query_to_df("SELECT * FROM public_staging.stg_product_master_history")
    pmh_df["snapshot_date"] = pd.to_datetime(pmh_df["snapshot_date"])

    df = build_training_features(shipments_df, chargebacks_df, pmh_df)

    frames_dir.mkdir(parents=True, exist_ok=True)
    out_path = frames_dir / "training_features.parquet"
    df.to_parquet(out_path, index=False)
    logger.info("Saved %d training rows to %s", len(df), out_path)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    run()
