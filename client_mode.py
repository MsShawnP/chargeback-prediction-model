"""Client-mode CLI for chargeback-prediction-model.

Two commands wrap the existing engine with the shared ``lailara_engagement``
scaffold so a client's own chargeback history is analyzed locally (validated,
never committed, never deployed):

  roadmap         — from a client chargeback ledger, harmonize reason codes to
                    root-cause archetypes and build the prevention roadmap
                    economics (historical loss × preventability = prevention
                    value), every dollar figure printed beside its basis+window.
  train-evaluate  — retrain the interpretable model on the client's reconstructed
                    feature table and report EVERY metric from ONE evaluate run
                    (a single held-out temporal split — no cherry-picking).

Each command preflights the input (a missing required column → a branded Data
Readiness Report instead of results) and writes a branded, provenance-footed,
draft-watermarked deliverable + summary.json to ``client-output/`` only.

Usage:
    python client_mode.py roadmap --config engagement.yml \
        --input client-data/chargebacks.csv --out client-output [--final]
    python client_mode.py train-evaluate --config engagement.yml \
        --features client-data/training_features.csv --out client-output
"""

from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path

import pandas as pd

from lailara_engagement import (
    ColumnSpec,
    PreflightSpec,
    build_provenance,
    load_config,
    read_table,
    run_preflight,
    validation_status_label,
    write_report,
)
from lailara_engagement import palette as P
from lailara_engagement.provenance import Provenance

sys.path.insert(0, str(Path(__file__).resolve().parent))
from src.pipeline.roadmap import (  # noqa: E402
    ARCHETYPE_FIX_DESCRIPTIONS,
    PREVENTABILITY_FRACTIONS,
    compute_prevention_roadmap,
)

TOOL = "chargeback-prediction-model"
TOOL_VERSION = "1.0"

KNOWN_ARCHETYPES = set(PREVENTABILITY_FRACTIONS) | {"unmapped"}


# --------------------------------------------------------------------------- #
# roadmap command
# --------------------------------------------------------------------------- #
def _roadmap_spec() -> PreflightSpec:
    return PreflightSpec(
        tool=TOOL,
        version=TOOL_VERSION,
        columns=[
            ColumnSpec(name="chargeback_id", dtype="identifier", required=True,
                       unique=True, description="unique chargeback line id",
                       spec_ref="INPUT-SPEC §1"),
            ColumnSpec(name="amount", dtype="number", required=True, not_negative=True,
                       description="chargeback dollar amount", spec_ref="INPUT-SPEC §1"),
            ColumnSpec(name="chargeback_date", dtype="date", required=True,
                       description="date the chargeback posted", spec_ref="INPUT-SPEC §1"),
            # Root-cause resolution: one of these two (both optional at the
            # column level; resolution is validated after mapping).
            ColumnSpec(name="root_cause_archetype", dtype="string", required=False,
                       allow_blank=True, description="root-cause archetype (preferred)"),
            ColumnSpec(name="reason_code", dtype="string", required=False,
                       allow_blank=True, description="raw retailer reason code (mapped via config)"),
            ColumnSpec(name="retailer", dtype="string", required=False, allow_blank=True,
                       description="retailer the chargeback came from"),
        ],
    )


def _resolve_archetype(archetype_val: str, reason_val: str, archetype_map: dict) -> str:
    a = str(archetype_val).strip()
    if a and a in PREVENTABILITY_FRACTIONS:
        return a
    if a:  # a non-blank archetype that isn't a known one is still honoured (0 fraction)
        return a
    code = str(reason_val).strip()
    if code and code in archetype_map:
        return str(archetype_map[code])
    return "unmapped"


def run_roadmap(config_path: str, input_path: str, out_dir: str, *, final: bool = False) -> dict:
    config = load_config(config_path)
    read = read_table(input_path)
    spec = _roadmap_spec()
    report = run_preflight(read, spec, config)

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    provenance = build_provenance(
        tool=TOOL, tool_version=TOOL_VERSION, inputs=[read], config=config,
        validation_status=validation_status_label(report.status, report.n_warnings),
    )
    if not report.passed:
        paths = write_report(report, config, str(out), provenance=provenance,
                             draft=not final, basename="data-readiness-report",
                             title="Chargeback Data Readiness Report")
        return {"status": "blocked", "readiness_report": paths["html"]}

    m = report.column_mapping
    frame = read.frame
    archetype_map = config.raw.get("archetype_map") or {}
    fractions = {**PREVENTABILITY_FRACTIONS, **(config.basis.get("preventability_fractions") or {})}

    arch_col = m.get("root_cause_archetype")
    reason_col = m.get("reason_code")
    amt_col = m.get("amount")

    archetypes = []
    for i in range(len(frame)):
        av = frame[arch_col].iloc[i] if arch_col else ""
        rv = frame[reason_col].iloc[i] if reason_col else ""
        archetypes.append(_resolve_archetype(av, rv, archetype_map))

    charge_df = pd.DataFrame({
        "root_cause_archetype": archetypes,
        "amount": [float(str(v).strip() or 0) for v in frame[amt_col]],
    })

    # Build the roadmap with the engine's own function, but apply the (possibly
    # client-overridden) preventability fractions.
    grouped = (charge_df.groupby("root_cause_archetype")["amount"].sum()
               .reset_index().rename(columns={"amount": "historical_loss"}))
    grouped["preventability_fraction"] = grouped["root_cause_archetype"].map(fractions).fillna(0.0)
    grouped["prevention_value"] = grouped["historical_loss"] * grouped["preventability_fraction"]
    grouped["fix_description"] = grouped["root_cause_archetype"].map(ARCHETYPE_FIX_DESCRIPTIONS).fillna("—")
    roadmap = grouped.sort_values("prevention_value", ascending=False).reset_index(drop=True)

    total = float(roadmap["historical_loss"].sum())
    prev = float(roadmap["prevention_value"].sum())
    window_months = int(config.basis.get("window_months") or 0) or None
    window_label = config.basis.get("window_label", "")
    annualized = (total * 12 / window_months) if window_months else None
    unmapped_loss = float(roadmap.loc[roadmap["root_cause_archetype"] == "unmapped", "historical_loss"].sum())

    summary = {
        "window": {"months": window_months, "label": window_label},
        "totals": {
            "total_chargeback": round(total, 2),
            "annualized": round(annualized, 2) if annualized is not None else None,
            "total_preventable": round(prev, 2),
            "preventable_pct": round(prev / total, 4) if total else None,
        },
        "roadmap": [
            {"root_cause_archetype": r["root_cause_archetype"],
             "historical_loss": round(float(r["historical_loss"]), 2),
             "preventability_fraction": round(float(r["preventability_fraction"]), 2),
             "prevention_value": round(float(r["prevention_value"]), 2)}
            for _, r in roadmap.iterrows()
        ],
    }
    limitations = []
    if unmapped_loss > 0:
        limitations.append(
            f"${unmapped_loss:,.0f} of loss had no root-cause archetype (unmapped reason "
            f"codes) — grouped as 'unmapped' with 0% preventability. Map these in "
            f"engagement.yml archetype_map to include them in the prevention estimate.")
    if window_months is None:
        limitations.append("No basis.window_months in config — annualized figure omitted.")

    json_dir = out / "json"
    json_dir.mkdir(parents=True, exist_ok=True)
    (json_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    report_path = out / "prevention-roadmap-summary.html"
    report_path.write_text(_roadmap_html(config, summary, limitations, provenance, draft=not final),
                           encoding="utf-8")
    return {"status": "ok", "total": round(total, 2), "preventable": round(prev, 2),
            "report": str(report_path), "summary_json": str(json_dir / "summary.json"),
            "n_warnings": report.n_warnings}


# --------------------------------------------------------------------------- #
# train-evaluate command
# --------------------------------------------------------------------------- #
def _features_spec() -> PreflightSpec:
    return PreflightSpec(
        tool=TOOL,
        version=TOOL_VERSION,
        columns=[
            ColumnSpec(name="ship_date", dtype="date", required=True,
                       description="ship date — drives the temporal train/test split",
                       spec_ref="INPUT-SPEC §2"),
            ColumnSpec(name="chargeback", dtype="integer", required=True,
                       description="0/1 label the model predicts", spec_ref="INPUT-SPEC §2"),
        ],
    )


def run_train_evaluate(config_path: str, features_path: str, out_dir: str, *, final: bool = False) -> dict:
    config = load_config(config_path)
    read = read_table(features_path)
    spec = _features_spec()
    report = run_preflight(read, spec, config)

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    provenance = build_provenance(
        tool=TOOL, tool_version=TOOL_VERSION, inputs=[read], config=config,
        validation_status=validation_status_label(report.status, report.n_warnings),
    )
    if not report.passed:
        paths = write_report(report, config, str(out), provenance=provenance,
                             draft=not final, basename="data-readiness-report",
                             title="Chargeback Features Readiness Report")
        return {"status": "blocked", "readiness_report": paths["html"]}

    # Lazy import — only train-evaluate needs sklearn/shap.
    from src.pipeline.model import (evaluate_model, get_feature_columns,
                                    temporal_split, train_model)

    # Reconstruct a typed frame from the all-text read (features are numeric).
    df = read.frame.copy()
    df["ship_date"] = pd.to_datetime(df["ship_date"], errors="coerce")
    df["chargeback"] = pd.to_numeric(df["chargeback"], errors="coerce").fillna(0).astype(int)
    feat_cols = get_feature_columns(
        df.assign(**{c: pd.to_numeric(df[c], errors="coerce")
                     for c in df.columns if c not in ("ship_date", "chargeback", "sku", "order_id")}))
    for c in feat_cols:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)

    train_df, test_df = temporal_split(df)
    X_train, y_train = train_df[feat_cols], train_df["chargeback"]
    X_test, y_test = test_df[feat_cols], test_df["chargeback"]
    model = train_model(X_train, y_train)
    metrics = evaluate_model(model, X_test, y_test, n_train=len(X_train))  # ONE run → all metrics

    frames_dir = out / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([metrics]).to_csv(frames_dir / "model_performance.csv", index=False)

    report_path = out / "model-metrics-summary.html"
    report_path.write_text(_metrics_html(config, metrics, feat_cols, provenance, draft=not final),
                           encoding="utf-8")
    return {"status": "ok", **metrics, "report": str(report_path),
            "model_performance": str(frames_dir / "model_performance.csv"),
            "n_warnings": report.n_warnings}


# --------------------------------------------------------------------------- #
# HTML deliverables
# --------------------------------------------------------------------------- #
def _fmt(v):
    return "—" if v is None else f"${v:,.0f}"


def _roadmap_html(config, summary, limitations, provenance: Provenance, *, draft: bool) -> str:
    esc = html.escape
    t = summary["totals"]
    wm = summary["window"].get("months")
    wl = summary["window"].get("label") or ""
    win = (f"{wm} months" + (f" ({esc(wl)})" if wl else "")) if wm else "full window"
    rows = "".join(
        f"<tr><td>{esc(r['root_cause_archetype'].replace('_',' ').title())}</td>"
        f"<td class=num>{_fmt(r['historical_loss'])}</td>"
        f"<td class=num>{r['preventability_fraction']*100:.0f}%</td>"
        f"<td class=num>{_fmt(r['prevention_value'])}</td></tr>"
        for r in summary["roadmap"])
    lim = "".join(f"<li>{esc(x)}</li>" for x in limitations) or "<li>None.</li>"
    return f"""<!doctype html><html lang=en><head><meta charset=utf-8>
<meta name=viewport content="width=device-width, initial-scale=1">
<title>Prevention Roadmap — {esc(config.client_name)}</title><style>{_css(draft)}</style></head>
<body class="{' ll-draft' if draft else ''}"><main class=ll-page>
<header class=ll-header>
  <div class=ll-eyebrow>Lailara LLC · Chargeback Prevention</div>
  <h1 class=ll-title>Prevention Roadmap</h1>
  <div class=ll-client>
    <div><span class=ll-k>Client</span> {esc(config.client_name)}</div>
    <div><span class=ll-k>Engagement</span> {esc(config.engagement_id)}</div>
    <div><span class=ll-k>As of</span> {esc(config.as_of_date.isoformat())}</div>
    <div><span class=ll-k>Window</span> {win}</div>
  </div>
</header>
<section class=ll-banner>
  <div class=ll-score>{_fmt(t['total_chargeback'])} in chargebacks over {win}</div>
  <div>annualized {_fmt(t['annualized'])} · {_fmt(t['total_preventable'])} preventable
       ({'' if t['preventable_pct'] is None else f"{t['preventable_pct']*100:.0f}%"})</div>
</section>
<section class=ll-section>
  <h2 class=ll-h2>Prevention roadmap — loss by root cause</h2>
  <table class=ll-table><thead><tr><th>Root cause</th><th>Historical loss</th>
  <th>Preventable</th><th>Prevention value</th></tr></thead><tbody>{rows}</tbody></table>
  <p class=ll-note>Prevention value = historical loss × preventability fraction (from config);
  always ≤ the loss. Annualization is ×12/{wm if wm else '—'}.</p>
</section>
<section class=ll-section><h2 class=ll-h2>Data limitations</h2><ul class=ll-limitations>{lim}</ul></section>
{provenance.to_html()}
</main></body></html>"""


def _metrics_html(config, metrics, feat_cols, provenance: Provenance, *, draft: bool) -> str:
    esc = html.escape
    fc = ", ".join(esc(c) for c in feat_cols)
    return f"""<!doctype html><html lang=en><head><meta charset=utf-8>
<meta name=viewport content="width=device-width, initial-scale=1">
<title>Model Metrics — {esc(config.client_name)}</title><style>{_css(draft)}</style></head>
<body class="{' ll-draft' if draft else ''}"><main class=ll-page>
<header class=ll-header>
  <div class=ll-eyebrow>Lailara LLC · Chargeback Model</div>
  <h1 class=ll-title>Model Metrics</h1>
  <div class=ll-client>
    <div><span class=ll-k>Client</span> {esc(config.client_name)}</div>
    <div><span class=ll-k>Engagement</span> {esc(config.engagement_id)}</div>
    <div><span class=ll-k>As of</span> {esc(config.as_of_date.isoformat())}</div>
  </div>
</header>
<section class=ll-banner><div class=ll-score>AUC {metrics['auc']:.4f}</div>
  <div>precision {metrics['precision']:.4f} · recall {metrics['recall']:.4f}</div></section>
<section class=ll-section>
  <h2 class=ll-h2>Held-out evaluation (single temporal split)</h2>
  <table class=ll-table>
    <tr><td>AUC</td><td class=num>{metrics['auc']:.4f}</td></tr>
    <tr><td>Precision</td><td class=num>{metrics['precision']:.4f}</td></tr>
    <tr><td>Recall</td><td class=num>{metrics['recall']:.4f}</td></tr>
    <tr><td>Train rows</td><td class=num>{metrics['n_train']:,}</td></tr>
    <tr><td>Test rows</td><td class=num>{metrics['n_test']:,}</td></tr>
  </table>
  <p class=ll-note>Every metric above comes from ONE evaluate run on a single held-out
  temporal split (later ship dates), never shuffled — no cherry-picking a good split.</p>
</section>
<section class=ll-section><h2 class=ll-h2>Features used</h2><p>{fc}</p></section>
{provenance.to_html()}
</main></body></html>"""


def _css(draft: bool) -> str:
    draft_css = (
        ".ll-draft::before{content:'DRAFT';position:fixed;top:50%;left:50%;"
        "transform:translate(-50%,-50%) rotate(-32deg);font-family:var(--s);"
        "font-size:22vw;font-weight:700;color:rgba(204,16,10,.06);z-index:0;"
        "pointer-events:none;white-space:nowrap}" if draft else ""
    )
    return f"""
:root{{--s:{P.LL_SERIF};--f:{P.LL_SANS}}}*{{box-sizing:border-box}}
body{{margin:0;background:{P.LL_CANVAS};color:{P.LL_TEXT};font-family:var(--f);line-height:1.6}}
.ll-page{{position:relative;z-index:1;max-width:{P.LL_MAX_WIDTH};margin:0 auto;padding:48px 24px}}
.ll-header{{border-bottom:1px solid {P.LL_GRIDLINE};padding-bottom:24px;margin-bottom:24px}}
.ll-eyebrow{{font-size:12px;letter-spacing:.04em;text-transform:uppercase;color:{P.LL_RED};font-weight:600}}
.ll-title{{font-family:var(--s);font-weight:700;color:{P.LL_INK};font-size:34px;margin:8px 0 16px}}
.ll-client{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:8px 24px;font-size:14px}}
.ll-k{{display:block;color:{P.LL_TEXT_SEC};font-size:11px;text-transform:uppercase;letter-spacing:.04em}}
.ll-banner{{border-radius:2px;padding:16px 20px;margin-bottom:32px;background:{P.LL_HK_SURFACE};color:{P.LL_HK_DARK}}}
.ll-score{{font-family:var(--s);font-weight:700;font-size:22px}}
.ll-section{{margin:0 0 32px}}
.ll-h2{{font-family:var(--s);font-weight:700;color:{P.LL_INK};font-size:22px;
margin:0 0 12px;padding-bottom:6px;border-bottom:1px solid {P.LL_GRIDLINE}}}
.ll-note{{font-size:13px;color:{P.LL_TEXT_SEC};margin-top:8px}}
.ll-table{{width:100%;border-collapse:collapse;font-size:14px}}
.ll-table th{{text-align:left;background:{P.LL_CHICAGO};color:#fff;padding:8px 12px}}
.ll-table td{{padding:8px 12px;border-bottom:1px solid {P.LL_GRIDLINE}}}
.ll-limitations{{margin:0;padding-left:20px}}.ll-limitations li{{margin-bottom:6px}}
.num{{text-align:right;font-variant-numeric:tabular-nums}}
.ll-provenance{{margin-top:40px;background:{P.LL_CARD_BG};color:{P.LL_CARD_TEXT};
padding:20px 24px;border-radius:2px;font-size:13px}}
.ll-prov-title{{font-family:var(--s);font-weight:700;font-size:16px;margin-bottom:8px}}
.ll-provenance div{{margin-bottom:4px;color:{P.LL_CARD_SUBTITLE}}}
.ll-provenance strong{{color:{P.LL_CARD_TEXT}}}
.ll-prov-inputs{{width:100%;border-collapse:collapse;margin-top:8px}}
.ll-prov-inputs th{{text-align:left;border-bottom:1px solid rgba(255,255,255,.12);padding:4px 8px;color:{P.LL_CARD_MUTED}}}
.ll-prov-inputs td{{padding:4px 8px;border-bottom:1px solid rgba(255,255,255,.08);color:{P.LL_CARD_SUBTITLE}}}
.ll-prov-brand{{margin-top:12px;font-family:var(--s);color:{P.LL_CARD_MUTED}}}
{draft_css}
@media print{{body{{background:#fff}}}}
"""


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="chargeback client mode")
    sub = ap.add_subparsers(dest="command", required=True)
    rp = sub.add_parser("roadmap", help="prevention roadmap from a client chargeback ledger")
    rp.add_argument("--config", required=True)
    rp.add_argument("--input", required=True)
    rp.add_argument("--out", default="client-output")
    rp.add_argument("--final", action="store_true")
    te = sub.add_parser("train-evaluate", help="retrain + evaluate on a client feature table")
    te.add_argument("--config", required=True)
    te.add_argument("--features", required=True)
    te.add_argument("--out", default="client-output")
    te.add_argument("--final", action="store_true")
    args = ap.parse_args(argv)

    if args.command == "roadmap":
        result = run_roadmap(args.config, args.input, args.out, final=args.final)
        if result["status"] == "blocked":
            print(f"BLOCKED — data not ready. See {result['readiness_report']}")
            return 3
        print(f"roadmap: ${result['total']:,.0f} in chargebacks; "
              f"${result['preventable']:,.0f} preventable")
        print(f"report -> {result['report']}")
        return 0
    else:
        result = run_train_evaluate(args.config, args.features, args.out, final=args.final)
        if result["status"] == "blocked":
            print(f"BLOCKED — data not ready. See {result['readiness_report']}")
            return 3
        print(f"train-evaluate: AUC={result['auc']:.4f} precision={result['precision']:.4f} "
              f"recall={result['recall']:.4f} (n_train={result['n_train']}, n_test={result['n_test']})")
        print(f"report -> {result['report']}")
        return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
