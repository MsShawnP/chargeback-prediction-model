"""Canonical regression tests for Cinderhaven baked JSON data.

These tests load the baked JSON files in frontend/public/json/ and assert
that retailer codes and structural invariants match the values locked in
CINDERHAVEN_CANONICAL.md.  They exist to catch accidental data drift
when the pipeline is re-run.

Run:
    pytest tests/test_canonical_regression.py -v
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
JSON_DIR = ROOT / "frontend" / "public" / "json"

# The six canonical Cinderhaven retailers (code form).
CANONICAL_RETAILERS = {"WMT", "COSTCO", "WHOLEFOODS", "SPROUTS", "KGR", "REGIONAL"}

EXPECTED_JSON_FILES = ("risk_ledger.json", "simulator.json", "summary.json")


class TestCinderhavenCanonicalRegression:
    """Assert baked JSON matches locked canonical figures."""

    # ------------------------------------------------------------------
    # Smoke tests — files exist and parse as valid JSON
    # ------------------------------------------------------------------

    @pytest.mark.parametrize("filename", EXPECTED_JSON_FILES)
    def test_json_file_exists(self, filename: str) -> None:
        path = JSON_DIR / filename
        assert path.exists(), f"{filename} not found at {path}"

    @pytest.mark.parametrize("filename", EXPECTED_JSON_FILES)
    def test_json_file_is_valid(self, filename: str) -> None:
        path = JSON_DIR / filename
        text = path.read_text(encoding="utf-8")
        data = json.loads(text)  # will raise on invalid JSON
        assert data, f"{filename} parsed but is empty"

    # ------------------------------------------------------------------
    # Retailer code constraints — risk_ledger.json
    # ------------------------------------------------------------------

    @pytest.fixture()
    def risk_ledger(self) -> list[dict]:
        return json.loads(
            (JSON_DIR / "risk_ledger.json").read_text(encoding="utf-8")
        )

    @pytest.fixture()
    def simulator(self) -> list[dict]:
        return json.loads(
            (JSON_DIR / "simulator.json").read_text(encoding="utf-8")
        )

    def test_risk_ledger_retailers_are_canonical(self, risk_ledger: list[dict]) -> None:
        actual = {row["retailer"] for row in risk_ledger}
        unexpected = actual - CANONICAL_RETAILERS
        assert not unexpected, (
            f"risk_ledger.json contains non-canonical retailers: {unexpected}"
        )

    def test_risk_ledger_retailers_cover_all_canonical(
        self, risk_ledger: list[dict]
    ) -> None:
        """Every canonical retailer should appear at least once."""
        actual = {row["retailer"] for row in risk_ledger}
        missing = CANONICAL_RETAILERS - actual
        assert not missing, (
            f"risk_ledger.json is missing canonical retailers: {missing}"
        )

    # ------------------------------------------------------------------
    # Retailer code constraints — simulator.json
    # ------------------------------------------------------------------

    def test_simulator_retailers_are_canonical(self, simulator: list[dict]) -> None:
        actual = {row["retailer"] for row in simulator}
        unexpected = actual - CANONICAL_RETAILERS
        assert not unexpected, (
            f"simulator.json contains non-canonical retailers: {unexpected}"
        )

    def test_simulator_retailers_cover_all_canonical(
        self, simulator: list[dict]
    ) -> None:
        """Every canonical retailer should appear at least once."""
        actual = {row["retailer"] for row in simulator}
        missing = CANONICAL_RETAILERS - actual
        assert not missing, (
            f"simulator.json is missing canonical retailers: {missing}"
        )

    # ------------------------------------------------------------------
    # Structural invariants
    # ------------------------------------------------------------------

    def test_risk_ledger_rows_have_required_fields(
        self, risk_ledger: list[dict]
    ) -> None:
        required = {"sku", "retailer", "probability", "dollar_exposure", "risk_tier"}
        for i, row in enumerate(risk_ledger):
            missing = required - set(row.keys())
            assert not missing, (
                f"risk_ledger row {i} missing fields: {missing}"
            )

    def test_simulator_rows_have_shap_values(self, simulator: list[dict]) -> None:
        for i, row in enumerate(simulator):
            assert "shap_values" in row, (
                f"simulator row {i} missing shap_values"
            )
