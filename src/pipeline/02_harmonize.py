"""
Pipeline step 2: reason-code harmonization.

Reads chargebacks and deduction_codes from output/frames/, adds
root_cause_archetype to each, writes harmonized parquet files back.

Requires step 01_extract.py to have run first (produces the input parquet files).
"""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.harmonization.reason_codes import harmonize_chargebacks, harmonize_deductions  # noqa: E402

logger = logging.getLogger(__name__)

FRAMES_DIR = Path("output/frames")


def run(frames_dir: Path = FRAMES_DIR) -> None:
    """Harmonize chargebacks and deduction codes; write enriched parquet files."""
    cb_path = frames_dir / "chargebacks.parquet"
    dc_path = frames_dir / "deduction_codes.parquet"

    if not cb_path.exists():
        raise FileNotFoundError(f"{cb_path} not found. Run 01_extract.py first.")
    if not dc_path.exists():
        raise FileNotFoundError(f"{dc_path} not found. Run 01_extract.py first.")

    import pandas as pd

    chargebacks = pd.read_parquet(cb_path)
    deduction_codes = pd.read_parquet(dc_path)

    chargebacks_out = harmonize_chargebacks(chargebacks)
    deduction_codes_out = harmonize_deductions(deduction_codes)

    unmatched_cb = chargebacks_out["root_cause_archetype"].isna().sum()
    unmatched_dc = deduction_codes_out["root_cause_archetype"].isna().sum()
    if unmatched_cb > 0:
        pct = unmatched_cb / len(chargebacks_out)
        logger.warning(
            "%d chargeback rows (%.1f%%) have no archetype — check logs above",
            unmatched_cb, pct * 100,
        )
    if unmatched_dc > 0:
        logger.warning(
            "%d deduction_code rows have no archetype — check logs above", unmatched_dc,
        )

    chargebacks_out.to_parquet(frames_dir / "chargebacks_harmonized.parquet", index=False)
    deduction_codes_out.to_parquet(
        frames_dir / "deduction_codes_harmonized.parquet", index=False
    )
    logger.info(
        "Harmonization complete — %d chargebacks (%d unmatched), "
        "%d deduction codes (%d unmatched)",
        len(chargebacks_out), unmatched_cb,
        len(deduction_codes_out), unmatched_dc,
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    run()
