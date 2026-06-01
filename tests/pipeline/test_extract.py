"""Tests for src/pipeline/extract.py — Cinderhaven extraction (step 01)."""

from unittest.mock import call, patch

import pandas as pd
import pytest

from src.pipeline.extract import run


SAMPLE_CHARGEBACKS = pd.DataFrame({
    "chargeback_id":   ["CB-001", "CB-002"],
    "retailer_id":     ["RET-1",  "RET-2"],
    "sku":             ["CHP-AS-001", "CHP-AS-002"],
    "chargeback_date": pd.to_datetime(["2024-03-15", "2024-04-02"]),
    "amount":          [1250.00, 875.50],
    "reason":          ["label_fine", "damaged"],
})

SAMPLE_DEDUCTION_CODES = pd.DataFrame({
    "code_id":        ["DC-01", "DC-02", "DC-03"],
    "deduction_type": ["label_fine", "slotting", "short_ship"],
    "description":    ["Label compliance fine", "Slotting fee", "Short shipment"],
})


def _side_effect(sql: str) -> pd.DataFrame:
    if "retailer_chargebacks" in sql:
        return SAMPLE_CHARGEBACKS.copy()
    if "retailer_deduction_codes" in sql:
        return SAMPLE_DEDUCTION_CODES.copy()
    raise ValueError(f"Unexpected SQL: {sql}")


@pytest.fixture
def frames_dir(tmp_path):
    return tmp_path / "frames"


def test_extract_writes_chargebacks_parquet(frames_dir):
    with patch("src.pipeline.extract.query_to_df", side_effect=_side_effect):
        run(frames_dir=frames_dir)

    out = frames_dir / "chargebacks.parquet"
    assert out.exists()
    df = pd.read_parquet(out)
    assert len(df) == 2
    assert "reason" in df.columns


def test_extract_writes_deduction_codes_parquet(frames_dir):
    with patch("src.pipeline.extract.query_to_df", side_effect=_side_effect):
        run(frames_dir=frames_dir)

    out = frames_dir / "deduction_codes.parquet"
    assert out.exists()
    df = pd.read_parquet(out)
    assert len(df) == 3
    assert "deduction_type" in df.columns


def test_extract_creates_frames_dir_if_missing(tmp_path):
    frames_dir = tmp_path / "does_not_exist" / "frames"
    assert not frames_dir.exists()

    with patch("src.pipeline.extract.query_to_df", side_effect=_side_effect):
        run(frames_dir=frames_dir)

    assert frames_dir.exists()


def test_extract_preserves_all_source_columns(frames_dir):
    with patch("src.pipeline.extract.query_to_df", side_effect=_side_effect):
        run(frames_dir=frames_dir)

    cb = pd.read_parquet(frames_dir / "chargebacks.parquet")
    assert set(SAMPLE_CHARGEBACKS.columns).issubset(set(cb.columns))

    dc = pd.read_parquet(frames_dir / "deduction_codes.parquet")
    assert set(SAMPLE_DEDUCTION_CODES.columns).issubset(set(dc.columns))


def test_extract_queries_correct_tables(frames_dir):
    with patch("src.pipeline.extract.query_to_df", side_effect=_side_effect) as mock_q:
        run(frames_dir=frames_dir)

    sqls = [c.args[0] for c in mock_q.call_args_list]
    assert any("retailer_chargebacks" in s for s in sqls)
    assert any("retailer_deduction_codes" in s for s in sqls)
