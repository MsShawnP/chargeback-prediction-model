"""Demo golden lock — chargeback-prediction-model.

Locks the demo INPUTS that determine the published output, before any
engagement-ready change. What actually deploys is rendered fresh by CI
(.github/workflows/render.yml runs `quarto render` from the committed
`output/frames/*.csv` + `quarto/*.qmd` source, then deploys to Pages), and the
frontend deploys from `frontend/public/json`. So the golden pins those inputs —
not the derived `quarto/_site` render, which is a rebuildable cache.

Three things are pinned:

1. **Byte-lock** — SHA-256 of the frontend JSON the app consumes and the three
   output frames the Quarto reports read.
2. **Headline numbers** — the exact figures the reports render, with the basis
   the 2026-07-31 audit flagged (37-month window vs the "annual" mislabel;
   annualization ×12/37; the logistics fig-cap numbers).
3. **Source correctness + caption↔data consistency** — the fixed labels are
   present in the *source* qmd (what CI renders) and the fig-cap numbers match
   the chart data, so the caption can't silently drift from the chart.

If any assertion fails, STOP: a golden moved. Do not re-baseline without an
explicit, logged approval.

NOTE (reported as a needs-Shawn's-call item): the committed `quarto/_site` and
`quarto/_freeze` are STALE — they still render the pre-fix "annual chargebacks"
and "five retailers". CI renders fresh from the fixed source on main, so the
deployed deliverable is correct; the committed cache wants a mechanical
`quarto render` refresh (a separate, approved step — it moves those bytes).
"""

from __future__ import annotations

import hashlib
import shutil
import subprocess
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
FRAMES = ROOT / "output" / "frames"
JSON_DIR = ROOT / "frontend" / "public" / "json"
QUARTO = ROOT / "quarto"
SITE = QUARTO / "_site"

# Pinned 2026-08-04 against the committed demo dataset.
GOLDEN_SHA256 = {
    "output/frames/prevention_roadmap.csv": "0317f010db4dd578",
    "output/frames/historical_chargebacks_by_archetype.csv": "32cec1c7c322bd2b",
    "output/frames/model_performance.csv": "26851282b22a5fd4",
    "frontend/public/json/risk_ledger.json": "e7fedb39a6fc4ee0",
    "frontend/public/json/simulator.json": "9c7ae810f456d264",
    "frontend/public/json/summary.json": "6df5d1bb486ec53f",
}


@pytest.fixture(scope="module")
def roadmap():
    return pd.read_csv(FRAMES / "prevention_roadmap.csv")


@pytest.fixture(scope="module")
def perf():
    return pd.read_csv(FRAMES / "model_performance.csv")


@pytest.mark.parametrize("relpath", sorted(GOLDEN_SHA256))
def test_demo_artifact_sha256_prefix(relpath):
    """Each committed demo input is byte-for-byte unchanged (16-char prefix)."""
    digest = hashlib.sha256((ROOT / relpath).read_bytes()).hexdigest()[:16]
    assert digest == GOLDEN_SHA256[relpath], (
        f"{relpath} changed (sha256[:16] {digest} != golden "
        f"{GOLDEN_SHA256[relpath]}). A demo golden moved — STOP and report."
    )


class TestHeadlineNumbers:
    def test_total_chargeback_37_month(self, roadmap):
        # $446,200 total over the 37-month window (Jan 2023 - Jan 2026).
        total = roadmap["historical_loss"].sum()
        assert round(total, 2) == 446200.06

    def test_annualized_not_annual(self, roadmap):
        # The mislabel the audit flagged: $446,200 is the 37-MONTH total, not an
        # annual figure. Annual = total x12/37 = ~$144,714 (3.1x smaller).
        total = roadmap["historical_loss"].sum()
        annualized = total * 12 / 37
        assert round(annualized) == 144714

    def test_total_preventable_and_pct(self, roadmap):
        prev = roadmap["prevention_value"].sum()
        total = roadmap["historical_loss"].sum()
        assert round(prev, 2) == 324887.78
        assert round(prev / total, 3) == 0.728

    def test_logistics_figcap_matches_chart(self, roadmap):
        # The fig-cap cites "$171K in prevention value ($245K historical loss)"
        # for the top preventable cause. Pin the chart values so the caption
        # cannot silently drift from the chart (the audit's P1).
        p = roadmap[roadmap["preventability_fraction"] > 0].sort_values(
            "prevention_value", ascending=False).reset_index(drop=True)
        top = p.iloc[0]
        assert top["root_cause_archetype"] == "logistics_overage"
        assert round(top["prevention_value"] / 1000) == 171     # -> "$171K"
        assert round(top["historical_loss"] / 1000) == 245      # -> "$245K"

    def test_model_metrics_single_evaluate(self, perf):
        # Every reported model metric comes from ONE evaluate run (one row).
        assert len(perf) == 1
        row = perf.iloc[0]
        assert round(float(row["auc"]), 4) == 0.6986
        assert round(float(row["recall"]), 4) == 0.7215


class TestSourceCorrectness:
    """The fixed labels live in the SOURCE qmd (what CI renders), and the
    audit's mislabels are absent from source."""

    def test_roadmap_source_37_month_computed_annualization(self):
        src = (QUARTO / "prevention_roadmap.qmd").read_text(encoding="utf-8")
        assert "over 37 months" in src
        assert "total_chargeback * 12 / 37" in src          # computed annualization
        assert "annual chargebacks" not in src              # the mislabel is gone

    def test_roadmap_figcap_numbers_present(self):
        src = (QUARTO / "prevention_roadmap.qmd").read_text(encoding="utf-8")
        assert "$171K in prevention value ($245K historical loss)" in src

    def test_methodology_six_retailers(self):
        src = (QUARTO / "methodology.qmd").read_text(encoding="utf-8")
        assert "six retailers" in src
        assert "five retailers" not in src

    def test_tearsheet_37_month(self):
        src = (QUARTO / "tearsheet.qmd").read_text(encoding="utf-8")
        assert "37 months" in src
        assert "annual chargebacks" not in src


class TestCorrectedRender:
    """Lock the committed render on the FIX. The committed quarto/_site was
    stale (rendered "annual chargebacks" / "five retailers"); it was regenerated
    from the fixed source (2026-08-04, freeze deleted → chunks re-executed).
    These assert the corrected content is present and no mislabel survives — a
    semantic lock, robust to Quarto-version byte differences (CI re-renders the
    site fresh on main via render.yml)."""

    def test_roadmap_html_corrected(self):
        html = (SITE / "prevention_roadmap.html").read_text(encoding="utf-8")
        assert "over 37 months" in html
        assert "144,714 a year" in html
        assert "$171K in prevention value ($245K historical loss)" in html
        assert "annual chargebacks" not in html
        assert "446,200 in annual" not in html

    def test_methodology_html_corrected(self):
        html = (SITE / "methodology.html").read_text(encoding="utf-8")
        assert "six retailers" in html
        assert "five retailers" not in html

    def test_tearsheet_html_corrected(self):
        html = (SITE / "tearsheet.html").read_text(encoding="utf-8")
        assert "37 months" in html
        assert "annual chargebacks" not in html

    @pytest.mark.parametrize("stem,markers", [
        ("prevention_roadmap", ("over 37 months", "144,714", "$171K", "$245K")),
        ("methodology", ("six retailers",)),
        ("tearsheet", ("37 months", "$171K")),
    ])
    def test_pdf_carries_corrected_figures(self, stem, markers):
        """The committed PDFs (in the binary-drift scan) carry the corrected
        figures too. Skips if poppler's pdftotext is unavailable."""
        pdftotext = shutil.which("pdftotext")
        if not pdftotext:
            pytest.skip("pdftotext (poppler) not available")
        pdf = SITE / f"{stem}.pdf"
        if not pdf.exists():
            pytest.skip(f"{pdf.name} not present")
        text = subprocess.run(
            [pdftotext, "-layout", str(pdf), "-"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        ).stdout
        for m in markers:
            assert m in text, f"{pdf.name} missing corrected marker {m!r}"
        for bad in ("annual chargebacks", "446,200 in annual", "five retailers"):
            assert bad not in text, f"{pdf.name} still carries mislabel {bad!r}"
