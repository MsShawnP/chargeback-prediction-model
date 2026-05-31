"""
Pipeline step 6: prevention roadmap (Move 5).

Reads the harmonized chargebacks frame (produced by 02_harmonize.py), computes
the ranked prevention roadmap, and writes prevention_roadmap.parquet.

All roadmap logic lives in src/pipeline/roadmap.py (importable module).
This file is the pipeline runner only.
"""

import logging
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.pipeline.roadmap import compute_prevention_roadmap  # noqa: E402

logger = logging.getLogger(__name__)

FRAMES_DIR = Path("output/frames")


def run(frames_dir: Path = FRAMES_DIR) -> None:
    """Compute and save the prevention roadmap."""
    cb_path = frames_dir / "chargebacks_harmonized.parquet"
    if not cb_path.exists():
        raise FileNotFoundError(f"{cb_path} not found. Run 02_harmonize.py first.")

    chargebacks = pd.read_parquet(cb_path)

    roadmap = compute_prevention_roadmap(chargebacks)

    total_loss = float(chargebacks["amount"].sum())
    total_preventable = float(roadmap["prevention_value"].sum())
    preventable_pct = total_preventable / total_loss if total_loss else 0.0

    logger.info(
        "Prevention roadmap: %d archetypes | total loss $%.0f | "
        "preventable $%.0f (%.0f%%)",
        len(roadmap),
        total_loss,
        total_preventable,
        preventable_pct * 100,
    )

    frames_dir.mkdir(parents=True, exist_ok=True)
    out_path = frames_dir / "prevention_roadmap.parquet"
    roadmap.to_parquet(out_path, index=False)
    logger.info("Saved prevention roadmap to %s", out_path)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    run()
