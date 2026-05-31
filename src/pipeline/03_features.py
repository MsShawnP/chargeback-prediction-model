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


def run(frames_dir: Path = FRAMES_DIR) -> None:
    """Query Cinderhaven, build training features, write to parquet."""
    shipments_df = query_to_df("SELECT * FROM raw.retailer_shipments")
    chargebacks_df = query_to_df("SELECT * FROM raw.retailer_chargebacks")
    pmh_df = query_to_df("SELECT * FROM public_staging.stg_product_master_history")

    df = build_training_features(shipments_df, chargebacks_df, pmh_df)

    frames_dir.mkdir(parents=True, exist_ok=True)
    out_path = frames_dir / "training_features.parquet"
    df.to_parquet(out_path, index=False)
    logger.info("Saved %d training rows to %s", len(df), out_path)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    run()
