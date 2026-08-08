"""Client-mode tests for chargeback-prediction-model.

Adversarial fixtures per checklist §6 for the `roadmap` command (clean file
renders clean, missing required column blocks, empty, headers-only, duplicate
headers, BOM+semicolon, Excel-mangled id as text, mixed date formats disclosed,
unmapped reason codes disclosed, negative/duplicate-key detection, --final
watermark), plus the `train-evaluate` command (metrics from one evaluate run;
missing label/date blocks).

Fixture brands/retailers are obviously-fictional placeholders — never a real
third party (the real-chain-fixture lesson, §3/§4).

Skipped if lailara_engagement isn't installed.
"""

import csv

import pytest

pytest.importorskip("lailara_engagement")

from lailara_engagement.errors import ReadError  # noqa: E402
import client_mode  # noqa: E402

_CONFIG = """
client: {name: Meridian Farms}
engagement: {id: MER-2026-08}
as_of_date: 2026-01-02
demo: true
basis:
  window_months: 37
  window_label: "Jan 2023 - Jan 2026"
  preventability_fractions:
    data_compliance_error: 0.80
    logistics_overage: 0.70
    pricing_discrepancy: 0.60
    legitimate: 0.20
archetype_map:
  "LBL-01": data_compliance_error
columns:
  chargeback_id: chargeback_id
  amount: amount
  chargeback_date: chargeback_date
  root_cause_archetype: root_cause_archetype
  reason_code: reason_code
  retailer: retailer
"""

_CLEAN = (
    "chargeback_id,amount,chargeback_date,root_cause_archetype,retailer\n"
    "CB001,1200.00,2025-03-14,logistics_overage,Harborline Markets\n"
    "CB002,800.00,2025-04-02,data_compliance_error,Cedarwood Foods\n"
    "CB003,450.00,2025-05-10,logistics_overage,Valleybrook Markets\n"
    "CB004,300.00,2025-06-01,pricing_discrepancy,Harborline Markets\n"
    "CB005,150.00,2025-06-15,legitimate,Cedarwood Foods\n"
)


@pytest.fixture
def cfg(tmp_path):
    p = tmp_path / "engagement.demo.yml"
    p.write_text(_CONFIG, encoding="utf-8")
    return str(p)


def _write(tmp_path, name, text, encoding="utf-8"):
    p = tmp_path / name
    p.write_bytes(text.encode(encoding) if isinstance(text, str) else text)
    return str(p)


# ---- roadmap command ------------------------------------------------------ #
def test_roadmap_clean_file_renders_clean(cfg, tmp_path):
    src = _write(tmp_path, "cb.csv", _CLEAN)
    out = str(tmp_path / "client-output")
    result = client_mode.run_roadmap(cfg, src, out)
    assert result["status"] == "ok"
    assert result["total"] == pytest.approx(2900.0, abs=0.01)
    # logistics 1650*.70 + dcompliance 800*.80 + pricing 300*.60 + legit 150*.20
    assert result["preventable"] == pytest.approx(1155 + 640 + 180 + 30, abs=0.01)
    html = open(result["report"], encoding="utf-8").read()
    assert "Meridian Farms" in html
    assert "#f5f3ee" in html                       # branded canvas
    assert "SHA-256" in html                        # provenance
    assert "DRAFT" in html
    assert "37 months" in html                      # window printed
    assert "×12/37" in html or "x12/37" in html     # annualization basis printed


def test_roadmap_annualized_from_config_window(cfg, tmp_path):
    src = _write(tmp_path, "cb.csv", _CLEAN)
    out = str(tmp_path / "out")
    result = client_mode.run_roadmap(cfg, src, out)
    import json
    t = json.load(open(result["summary_json"], encoding="utf-8"))["totals"]
    assert t["annualized"] == pytest.approx(2900.0 * 12 / 37, abs=0.01)


def test_roadmap_window_and_annualization_track_config_not_hardcoded(tmp_path):
    """The rendered window ('N months (label)') and the ×12/N annualization
    divisor must come from basis.window_months / window_label, not a hardcoded
    default. The clean-file test asserts only the demo's own '37 months' /
    '×12/37' — a positive-only check a hardcoded '37' would also pass, the exact
    gap that let trade-spend quote 26 weeks of data as 'trailing 52 weeks'.

    Both halves: feed a distinctive window and assert it tracks (label + divisor
    + numeric annualization), AND assert the demo default is absent."""
    cfg = tmp_path / "engagement.demo.yml"
    cfg.write_text(_CONFIG.replace("window_months: 37", "window_months: 29")
                          .replace("Jan 2023 - Jan 2026", "Feb 2024 - Jul 2026"), encoding="utf-8")
    src = _write(tmp_path, "cb.csv", _CLEAN)
    result = client_mode.run_roadmap(str(cfg), src, str(tmp_path / "out"))
    assert result["status"] == "ok"
    html = open(result["report"], encoding="utf-8").read()
    assert "29 months" in html and "Feb 2024 - Jul 2026" in html
    assert "×12/29" in html or "x12/29" in html
    assert "37 months" not in html                       # demo default must not survive
    assert "×12/37" not in html and "x12/37" not in html
    assert "Jan 2023 - Jan 2026" not in html
    import json
    t = json.load(open(result["summary_json"], encoding="utf-8"))["totals"]
    assert t["annualized"] == pytest.approx(2900.0 * 12 / 29, abs=0.01)


def test_roadmap_missing_required_column_blocks(cfg, tmp_path):
    # no amount column
    src = _write(tmp_path, "bad.csv",
                 "chargeback_id,chargeback_date,root_cause_archetype\nCB1,2025-01-01,logistics_overage\n")
    out = str(tmp_path / "out")
    result = client_mode.run_roadmap(cfg, src, out)
    assert result["status"] == "blocked"
    assert "amount" in open(result["readiness_report"], encoding="utf-8").read().lower()


def test_roadmap_empty_file_raises(cfg, tmp_path):
    src = _write(tmp_path, "empty.csv", "")
    with pytest.raises(ReadError):
        client_mode.run_roadmap(cfg, src, str(tmp_path / "out"))


def test_roadmap_headers_only_zero_rows(cfg, tmp_path):
    src = _write(tmp_path, "hdr.csv",
                 "chargeback_id,amount,chargeback_date,root_cause_archetype\n")
    result = client_mode.run_roadmap(cfg, src, str(tmp_path / "out"))
    assert result["status"] == "ok"
    assert result["total"] == 0


def test_roadmap_bom_semicolon_and_id_as_text(cfg, tmp_path):
    body = ("﻿chargeback_id;amount;chargeback_date;root_cause_archetype\n"
            "0012345;100;2025-01-01;logistics_overage\n"
            "0012346;200;2025-02-01;data_compliance_error\n")
    src = _write(tmp_path, "bom.csv", body)
    result = client_mode.run_roadmap(cfg, src, str(tmp_path / "out"))
    assert result["status"] == "ok"
    assert result["total"] == pytest.approx(300.0, abs=0.01)


def test_roadmap_excel_mangled_id_as_text(cfg, tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    wb = openpyxl.Workbook(); ws = wb.active
    ws.append(["chargeback_id", "amount", "chargeback_date", "root_cause_archetype"])
    ws.append([690123456789, 100, "2025-01-01", "logistics_overage"])
    ws.append([690123456790, 200, "2025-02-01", "data_compliance_error"])
    xlsx = tmp_path / "cb.xlsx"; wb.save(xlsx)
    result = client_mode.run_roadmap(cfg, str(xlsx), str(tmp_path / "out"))
    assert result["status"] == "ok"
    assert result["total"] == pytest.approx(300.0, abs=0.01)


def test_roadmap_mixed_date_formats_disclosed(cfg, tmp_path):
    src = _write(tmp_path, "d.csv",
                 "chargeback_id,amount,chargeback_date,root_cause_archetype\n"
                 "CB1,100,2025-01-15,logistics_overage\n"
                 "CB2,200,02/28/2025,data_compliance_error\n")
    result = client_mode.run_roadmap(cfg, src, str(tmp_path / "out"))
    assert result["status"] == "ok"
    assert result["n_warnings"] >= 1


def test_roadmap_unmapped_reason_codes_disclosed(cfg, tmp_path):
    # reason codes with no archetype (and no archetype column) -> unmapped, disclosed
    src = _write(tmp_path, "r.csv",
                 "chargeback_id,amount,chargeback_date,reason_code\n"
                 "CB1,500,2025-01-01,LBL-01\n"            # mapped -> data_compliance_error
                 "CB2,700,2025-02-01,ZZZ-99\n")           # unmapped
    result = client_mode.run_roadmap(cfg, src, str(tmp_path / "out"))
    assert result["status"] == "ok"
    import json
    s = json.load(open(result["summary_json"], encoding="utf-8"))
    archs = {r["root_cause_archetype"] for r in s["roadmap"]}
    assert "unmapped" in archs
    html = open(result["report"], encoding="utf-8").read()
    assert "unmapped" in html.lower()


def test_roadmap_negative_amount_flagged(cfg, tmp_path):
    src = _write(tmp_path, "n.csv",
                 "chargeback_id,amount,chargeback_date,root_cause_archetype\n"
                 "CB1,-50,2025-01-01,logistics_overage\n"
                 "CB2,200,2025-02-01,data_compliance_error\n")
    result = client_mode.run_roadmap(cfg, src, str(tmp_path / "out"))
    assert result["n_warnings"] >= 1


def test_roadmap_duplicate_id_blocks(cfg, tmp_path):
    src = _write(tmp_path, "dup.csv",
                 "chargeback_id,amount,chargeback_date,root_cause_archetype\n"
                 "CB1,100,2025-01-01,logistics_overage\n"
                 "CB1,200,2025-02-01,data_compliance_error\n")
    result = client_mode.run_roadmap(cfg, src, str(tmp_path / "out"))
    assert result["status"] == "blocked"
    assert "duplicat" in open(result["readiness_report"], encoding="utf-8").read().lower()


def test_roadmap_final_drops_watermark(cfg, tmp_path):
    src = _write(tmp_path, "cb.csv", _CLEAN)
    result = client_mode.run_roadmap(cfg, src, str(tmp_path / "out"), final=True)
    assert "ll-draft" not in open(result["report"], encoding="utf-8").read()


# ---- train-evaluate command ----------------------------------------------- #
def _features_csv(path, n=400, seed=7):
    import random
    random.seed(seed)
    rows = [["ship_date", "chargeback", "gtin14_missing", "case_dims_missing", "sku_prior_chargeback_rate"]]
    for i in range(n):
        day, month, year = 1 + i % 28, 1 + (i // 28) % 12, 2024 + (i // 336)
        g, d = random.random() < 0.3, random.random() < 0.25
        prior = round(random.random() * 0.2, 3)
        p = 0.05 + 0.4 * g + 0.3 * d + prior
        cb = 1 if random.random() < min(p, 0.95) else 0
        rows.append([f"{year}-{month:02d}-{day:02d}", cb, int(g), int(d), prior])
    with open(path, "w", newline="") as f:
        csv.writer(f).writerows(rows)


def test_train_evaluate_produces_every_metric_one_run(cfg, tmp_path):
    feats = tmp_path / "features.csv"
    _features_csv(feats)
    result = client_mode.run_train_evaluate(cfg, str(feats), str(tmp_path / "out"))
    assert result["status"] == "ok"
    for k in ("auc", "precision", "recall", "n_train", "n_test"):
        assert k in result
    assert 0.0 <= result["auc"] <= 1.0
    # one evaluate run -> one row in model_performance.csv
    import pandas as pd
    perf = pd.read_csv(result["model_performance"])
    assert len(perf) == 1
    html = open(result["report"], encoding="utf-8").read()
    assert "Meridian Farms" in html and "AUC" in html and "DRAFT" in html


def test_train_evaluate_missing_label_blocks(cfg, tmp_path):
    src = _write(tmp_path, "nolabel.csv", "ship_date,gtin14_missing\n2025-01-01,1\n2025-02-01,0\n")
    result = client_mode.run_train_evaluate(cfg, src, str(tmp_path / "out"))
    assert result["status"] == "blocked"
    assert "chargeback" in open(result["readiness_report"], encoding="utf-8").read().lower()
