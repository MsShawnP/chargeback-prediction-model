#!/usr/bin/env python3
"""
run_pipeline.py — End-to-end Cinderhaven chargeback prediction pipeline.

Runs pipeline steps 01–07 in order.  Each step is loaded by file path
(importlib handles numeric-prefixed names that Python cannot import directly)
and called via its run() function.

A failed step logs the error and exits non-zero immediately.  Step 01
(data extraction) is optional — skipped with a warning when the script is
absent so the pipeline can run against pre-extracted parquet fixtures.

Usage:
    python run_pipeline.py
"""

import importlib.util
import logging
import sys
import time
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

PIPELINE_ROOT = Path(__file__).resolve().parent
STEPS_DIR = PIPELINE_ROOT / "src" / "pipeline"
CONFIG_PATH = PIPELINE_ROOT / "config.yml"

# (step_name, script_path, optional)
# optional=True → skip gracefully when script is absent instead of failing
STEPS: list[tuple[str, Path, bool]] = [
    ("01_extract",   STEPS_DIR / "01_extract.py",   True),
    ("02_harmonize", STEPS_DIR / "02_harmonize.py",  False),
    ("03_features",  STEPS_DIR / "03_features.py",   False),
    ("04_model",     STEPS_DIR / "04_model.py",      False),
    ("05_score",     STEPS_DIR / "05_score.py",      False),
    ("06_roadmap",   STEPS_DIR / "06_roadmap.py",    False),
    ("07_export",    STEPS_DIR / "07_export.py",     False),
]


def _load_step(script_path: Path):
    """Load a pipeline step module by file path.

    importlib.util.spec_from_file_location handles numeric-prefixed filenames
    that Python's import machinery would otherwise reject.
    """
    spec = importlib.util.spec_from_file_location("_pipeline_step", script_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["_pipeline_step"] = module
    spec.loader.exec_module(module)
    return module


def _read_config() -> dict:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}


def run_all() -> None:
    """Run all pipeline steps in order; exit non-zero on first failure."""
    config = _read_config()
    engagement = config.get("engagement_name", "unknown")
    version = config.get("pipeline_version", "dev")

    logger.info("=" * 52)
    logger.info("Chargeback Prediction Pipeline")
    logger.info("  Engagement : %s", engagement)
    logger.info("  Version    : %s", version)
    logger.info("  Root       : %s", PIPELINE_ROOT)
    logger.info("=" * 52)

    total_start = time.monotonic()

    for name, script_path, optional in STEPS:
        if not script_path.exists():
            if optional:
                logger.warning("[SKIP] %-15s  (optional — script not found)", name)
                continue
            logger.error("[FAIL] %-15s  script not found: %s", name, script_path)
            sys.exit(1)

        logger.info("[START] %s", name)
        step_start = time.monotonic()
        try:
            module = _load_step(script_path)
            module.run()
            elapsed = time.monotonic() - step_start
            logger.info("[DONE]  %-15s  %.1fs", name, elapsed)
        except Exception as exc:
            elapsed = time.monotonic() - step_start
            logger.exception("[FAIL]  %-15s  %.1fs  —  %s", name, elapsed, exc)
            sys.exit(1)

    total_elapsed = time.monotonic() - total_start
    logger.info("=" * 52)
    logger.info("Pipeline complete in %.1fs", total_elapsed)
    logger.info("=" * 52)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S",
    )
    run_all()
