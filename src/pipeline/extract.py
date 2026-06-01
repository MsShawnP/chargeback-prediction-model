"""
Extract raw tables from Cinderhaven Postgres for the chargeback pipeline.

Called by 01_extract.py (the pipeline runner).  Lives in a separate importable
module so tests can exercise the logic without importlib gymnastics.
"""

import logging
from pathlib import Path

from src.pipeline.db import query_to_df

logger = logging.getLogger(__name__)

FRAMES_DIR = Path("output/frames")

_EXTRACTS: list[tuple[str, str, str]] = [
    ("chargebacks",     "SELECT * FROM raw.retailer_chargebacks",    "chargebacks.parquet"),
    ("deduction_codes", "SELECT * FROM raw.retailer_deduction_codes", "deduction_codes.parquet"),
]


def run(frames_dir: Path = FRAMES_DIR) -> None:
    """Extract Cinderhaven source tables and write to parquet."""
    frames_dir = Path(frames_dir)
    frames_dir.mkdir(parents=True, exist_ok=True)

    for name, sql, filename in _EXTRACTS:
        out_path = frames_dir / filename
        df = query_to_df(sql)
        df.to_parquet(out_path, index=False)
        logger.info("Extracted %s — %d rows → %s", name, len(df), out_path)
