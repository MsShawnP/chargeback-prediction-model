"""
Pipeline step 7: JSON and CSV export (U7).

Reads all pipeline artifacts, writes three JSON files for the React app and
two CSV files for Quarto reports.

All export logic lives in src/pipeline/export.py (importable module).
This file is the pipeline runner only.
"""

import logging
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.pipeline.export import (  # noqa: E402
    build_chargebacks_by_archetype,
    build_risk_ledger,
    build_simulator_payload,
    build_summary,
    write_json,
)

logger = logging.getLogger(__name__)

FRAMES_DIR = Path("output/frames")
JSON_DIR = Path("frontend/public/json")


def run(frames_dir: Path = FRAMES_DIR, json_dir: Path = JSON_DIR) -> None:
    """Read pipeline artifacts; write JSON and CSV outputs."""
    scored_pos = pd.read_parquet(frames_dir / "scored_pos.parquet")
    shap_values = pd.read_parquet(frames_dir / "scored_pos_shap.parquet")
    roadmap = pd.read_parquet(frames_dir / "prevention_roadmap.parquet")
    chargebacks_harmonized = pd.read_parquet(frames_dir / "chargebacks_harmonized.parquet")
    performance = pd.read_csv(frames_dir / "model_performance.csv")

    # Ensure row alignment between scored_pos and shap_values
    scored_pos = scored_pos.reset_index(drop=True)
    shap_values = shap_values.reset_index(drop=True)

    json_dir.mkdir(parents=True, exist_ok=True)
    write_json(build_risk_ledger(scored_pos), json_dir / "risk_ledger.json")
    write_json(
        build_simulator_payload(scored_pos, shap_values), json_dir / "simulator.json"
    )
    write_json(
        build_summary(scored_pos, roadmap, chargebacks_harmonized, performance),
        json_dir / "summary.json",
    )

    # CSV exports for Quarto reports
    roadmap.to_csv(frames_dir / "prevention_roadmap.csv", index=False)
    build_chargebacks_by_archetype(chargebacks_harmonized).to_csv(
        frames_dir / "historical_chargebacks_by_archetype.csv", index=False
    )

    logger.info(
        "Export complete — %d scored POs  |  %d roadmap rows  |  AUC %.4f",
        len(scored_pos),
        len(roadmap),
        float(performance["auc"].iloc[0]) if len(performance) else 0.0,
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    run()
