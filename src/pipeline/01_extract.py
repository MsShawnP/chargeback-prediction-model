"""
Pipeline step 1: extract raw tables from Cinderhaven Postgres.

Prerequisites:
  flyctl proxy 5432 -a cinderhaven-data-platform
  DATABASE_URL set in .env

Usage:
  python src/pipeline/01_extract.py
"""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.pipeline.extract import run  # noqa: E402

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    run()
