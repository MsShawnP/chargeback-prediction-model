---
title: "feat: Chargeback prediction model and multi-artifact portfolio suite"
status: active
date: 2026-05-31
source: docs/brainstorms/chargeback-prediction-requirements.md
plan_depth: deep
---

# feat: Chargeback Prediction Model — Multi-Artifact Portfolio Suite

**Source:** `docs/brainstorms/chargeback-prediction-requirements.md`
**Date:** 2026-05-31 | **Depth:** Deep | **Status:** Active

---

## Summary

Build a five-artifact Lailara portfolio suite proving that Cinderhaven's chargebacks are
predictable and ~60% preventable. A Python ML pipeline queries Cinderhaven's Postgres
database, harmonizes cross-retailer reason codes, reconstructs data quality state at
shipment time, trains an interpretable tree-based model with SHAP attribution, and exports
pre-computed results to two deliverable layers: a React/Vite app (Interactive Risk Ledger +
Intervention Simulator, deployed to Cloudflare Pages) and three Quarto documents (Prevention
Roadmap Report, Executive Tearsheet, Methodology Appendix, deployed to GitHub Pages). Every
risk score names the specific data condition driving it in plain language.

---

## Problem Frame

Cinderhaven carries $680K/year in chargebacks. The deductions team disputes reactively; the
CFO sees a single P&L line. Nobody has joined the chargeback remittance data to the upstream
product and EDI data that caused each chargeback. This suite connects those two datasets,
proves the causal relationship, scores future shipments before they ship, and ranks root
causes by prevention value.

**Business question:** Which upstream data quality conditions will generate chargebacks, at
what probability and dollar value, so the brand can intervene before shipment?

*(See origin: `docs/brainstorms/chargeback-prediction-requirements.md`)*

---

## Key Technical Decisions

| Decision | Choice | Rationale |
|---|---|---|
| ML model | RandomForestClassifier + SHAP | Interpretable by design; native SHAP support; handles mixed boolean/numeric features; upgrade path to GradientBoosting if AUC < 0.65 |
| Target variable | Binary per shipment-SKU: any chargeback within 90 days | Aligns to operational question; join via retailer_id + sku + date window |
| Reason-code harmonization | Dual pathway: structured (`deduction_codes.deduction_type` → archetype lookup) + unstructured (`chargeback.reason` free text → keyword/regex) | `reason` field is free text (~450 events); `deduction_codes` are structured; both pathways needed |
| Point-in-time join | Add `product_master_history` to Cinderhaven Data Platform (separate project); look up most recent snapshot where `snapshot_date ≤ ship_date` | `product_master.last_updated` is a single timestamp — insufficient for historical reconstruction; enrichment belongs in the SSOT |
| SHAP delivery to React | Pre-computed at pipeline run time, stored in JSON | No backend server required; consistent with Retailer Deduction Recovery pattern |
| React deployment | Cloudflare Pages via wrangler | Consistent with Retailer Deduction Recovery; SPA routing handled natively |
| Quarto engine | Python (jupyter) | All pipeline code is Python; avoids R/knitr dependency |
| Quarto deployment | GitHub Actions → GitHub Pages | Consistent with Product Data Health Audit pattern |
| Output format | JSON for React; CSV/Parquet for Quarto | Decouples pipeline from deliverables; each consumer reads what it needs |

---

## High-Level Technical Design

*This illustrates the intended data flow and is directional guidance for review, not
implementation specification.*

```
Cinderhaven Postgres  (flyctl proxy → localhost:5432)
        │
        ▼
src/pipeline/01_extract.py     Pull raw tables + dbt marts → output/frames/
        │
        ▼
src/pipeline/02_harmonize.py   Map reason codes → canonical archetypes
        │                      (structured lookup + keyword/regex for free text)
        ▼
src/pipeline/03_features.py    Point-in-time feature engineering
        │                      (join product_master_history at ship_date)
        ▼
src/pipeline/04_model.py       Train RandomForestClassifier; compute SHAP values
        │
        ▼
src/pipeline/05_score.py       Score upcoming POs; attach attribution strings
        │
        ▼
src/pipeline/06_roadmap.py     Aggregate root causes; rank by prevention value
        │
        ▼
src/pipeline/07_export.py  ────┬── JSON → frontend/public/json/
                               └── CSV/Parquet → output/frames/

frontend/public/json/          React fetches at runtime (no backend)
  └── React (Vite/TS)      ────┬── RiskLedger view
        └── Cloudflare Pages   └── Simulator view

output/frames/                 Quarto reads via Python chunks
  └── Quarto (.qmd)        ────┬── prevention_roadmap.qmd
        └── GitHub Pages       ├── tearsheet.qmd
                               └── methodology.qmd
```

**Five canonical root-cause archetypes** (output of harmonization, input to model labels):
`data_compliance_error` · `logistics_overage` · `asn_timing_infraction` ·
`item_setup_gap` · `pricing_discrepancy` · `legitimate`

**Feature set** (inputs to model):
- Data quality flags at shipment time: `gtin14_missing`, `case_dims_missing`,
  `case_weight_missing`, `upc_missing`, `data_quality_score` (0–4 count)
- Shipment compliance: `asn_sent_late`, `days_late`, `all_labels_scannable`
- Historical: `sku_prior_chargeback_rate` (computed with temporal split — no leakage)
- Retailer: `retailer_id` (categorical)

---

## Output Structure

```
chargeback-prediction-model/
├── src/
│   ├── pipeline/
│   │   ├── db.py                     # Connection helpers, DATABASE_URL loading
│   │   ├── 01_extract.py
│   │   ├── 02_harmonize.py
│   │   ├── 03_features.py
│   │   ├── 04_model.py
│   │   ├── 05_score.py
│   │   ├── 06_roadmap.py
│   │   └── 07_export.py
│   └── harmonization/
│       └── reason_codes.py           # Archetype mapping tables
├── output/
│   ├── frames/                       # Parquet/CSV intermediates (gitignored)
│   └── model/                        # Saved model artifact (gitignored)
├── frontend/
│   ├── public/json/                  # Pre-computed JSON for React
│   ├── src/
│   │   ├── App.tsx
│   │   ├── App.css                   # Lailara CSS tokens
│   │   ├── data.ts                   # JSON loaders
│   │   ├── views/
│   │   │   ├── RiskLedger.tsx
│   │   │   └── Simulator.tsx
│   │   └── components/
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   └── wrangler.jsonc
├── quarto/
│   ├── assets/report.css             # Lailara design tokens for Quarto
│   ├── _quarto.yml
│   ├── prevention_roadmap.qmd
│   ├── tearsheet.qmd
│   └── methodology.qmd
├── tests/
│   ├── pipeline/
│   │   ├── test_harmonize.py
│   │   ├── test_features.py
│   │   └── test_model.py
│   └── fixtures/
│       └── sample_chargebacks.csv
├── config.yml                        # Engagement metadata, run date
├── run_pipeline.py                   # Orchestration entry point
├── requirements.txt
├── .env.example
└── .github/workflows/render.yml     # Quarto CI/CD
```

---

## Implementation Units

### U1. Infrastructure spike — DB connectivity + EDA

**Goal:** Establish Cinderhaven Postgres connection, run exploratory data analysis on the
chargeback + shipment + deduction data, and verify the data is sufficient to train the model.

**Requirements:** Prerequisite for all downstream units. Validates the data assumptions
in the requirements doc.

**Dependencies:** None

**Files:**
- `src/pipeline/db.py`
- `.env.example`
- `requirements.txt`
- `output/frames/` (EDA scratch outputs, gitignored)

**Approach:**
- `db.py` reads `DATABASE_URL` env var (`postgresql://user:pass@localhost:5432/cinderhaven`
  via `flyctl proxy`); exposes a thin `query_to_df(sql, params)` helper and a context-manager
  connection
- EDA targets: `retailer_chargebacks`, `retailer_deductions`, `retailer_shipments`,
  `product_master`, `distribution_log`, `retailer_deduction_codes`
- Profile: row counts, date ranges, null rates per nullable column in `product_master`,
  chargeback rate per SKU/retailer, chargeback-to-shipment join match rate
- Key question: can chargebacks be linked to specific shipments via `order_id` or via
  `retailer_id + sku + date window`? Match rate must be ≥ 50% to proceed
- Document findings in HANDOFF.md before proceeding to U2

**Test scenarios:**
- `db.py` raises a descriptive error (not a raw psycopg2 exception) when `DATABASE_URL`
  is not set
- `query_to_df()` returns a DataFrame with expected columns for `SELECT * FROM retailers LIMIT 1`
- EDA row counts match known ranges: ~450 chargebacks, ~2,000 deductions, ~7,200 shipments,
  30 SKUs — flag if materially different

**Verification:** Pipeline connects to Cinderhaven; EDA outputs are readable; chargeback-to-shipment
joinability is confirmed or documented as a constraint.

---

### U2. Cinderhaven enrichment — product_master_history table

**Goal:** Add a `product_master_history` table to the Cinderhaven Data Platform with
per-SKU data quality state at each relevant shipment date, enabling the point-in-time join.

**Requirements:** Required by U4. *(See origin: Known constraint —
`product_master.last_updated` is a single timestamp, insufficient for historical
reconstruction)*

**Dependencies:** U1 (EDA confirms which nullable columns and date range matter)

**Files (in `cinderhaven-data-platform`, not this repo):**
- `sql/migrations/add_product_master_history.sql`
- `cinderhaven/seeds/product_master_history.csv`
- `cinderhaven/models/staging/stg_product_master_history.sql`

**Approach:**
- Schema: `(sku TEXT, snapshot_date DATE, gtin14_present BOOLEAN, upc_present BOOLEAN,
  case_dims_present BOOLEAN, case_weight_present BOOLEAN, data_quality_score INTEGER)` —
  one row per SKU per snapshot date
- Synthetic history: generate snapshots spanning the full shipment date range in
  `retailer_shipments`; introduce realistic progression (some SKUs start with missing
  dimensions and have them populated mid-period, consistent with the project brief's narrative)
- dbt staging model: `stg_product_master_history.sql` passes through with correct types
- Point-in-time lookup pattern: `WHERE snapshot_date <= :ship_date ORDER BY snapshot_date
  DESC LIMIT 1`

**Test scenarios:**
- No duplicate `(sku, snapshot_date)` pairs
- Date range covers all dates in `retailer_shipments.ship_date`
- Point-in-time lookup returns the correct historical state for a known test case
  (a SKU that had missing dimensions before a known date, and populated ones after)
- `data_quality_score` is the sum of the four boolean flags

**Verification:** Table exists in Cinderhaven; spans required date range; point-in-time
query returns plausible historical states distinct from today's `product_master` values.

---

### U3. Reason-code harmonization engine (Move 1)

**Goal:** Map all Cinderhaven chargeback reasons and deduction codes to five canonical
root-cause archetypes, enabling cross-retailer comparison and model labeling.

**Requirements:** Produces the categorical target for model training and the root-cause
lens for the prevention roadmap. *(See origin: Move 1)*

**Dependencies:** U1

**Files:**
- `src/harmonization/reason_codes.py`
- `src/pipeline/02_harmonize.py`
- `tests/pipeline/test_harmonize.py`
- `tests/fixtures/sample_chargebacks.csv`

**Approach:**
- **Structured pathway:** `retailer_deduction_codes.deduction_type` → archetype lookup
  dict in `reason_codes.py`; each `deduction_type` maps to exactly one archetype;
  new codes raise a clear `UnmappedCodeError` rather than silently falling through
- **Unstructured pathway:** `retailer_chargebacks.reason` free text → ordered
  keyword/regex patterns in `reason_codes.py`; patterns checked in priority order;
  first match wins; unmatched reasons return `None` and are logged for manual review
- Both pathways are separate, testable functions; `02_harmonize.py` calls them and
  enriches the DataFrames with a `root_cause_archetype` column
- The mapping dict and patterns live in `reason_codes.py`, not hardcoded in the pipeline,
  so they can be updated without touching pipeline logic

**Test scenarios:**
- Known `deduction_type` strings map to the correct archetype (one test per archetype)
- Free text containing "ASN", "advance ship notice", "late ASN" → `asn_timing_infraction`
- Free text containing "case dimensions", "weight", "overage", "pallet" →
  `logistics_overage`
- Free text containing "GTIN", "barcode", "UPC", "compliance" → `data_compliance_error`
- Unrecognized free text returns `None`, not a silently assigned archetype
- Harmonization is deterministic: identical input always produces identical output
- `UnmappedCodeError` is raised for a structured code not in the lookup dict

**Verification:** All ~450 `retailer_chargebacks` rows have an archetype or a logged
`None`; <5% unmatched; archetype distribution is plausible given the project brief's
root-cause breakdown.

---

### U4. Point-in-time feature engineering (Move 2)

**Goal:** Join chargebacks to shipments, reconstruct data quality state at shipment time,
and compute the full feature set for model training.

**Requirements:** Produces the labeled training set the model trains on. *(See origin:
Move 2)*

**Dependencies:** U2, U3

**Files:**
- `src/pipeline/03_features.py`
- `tests/pipeline/test_features.py`

**Approach:**
- Build training set: join `fct_retailer_shipments` → `retailer_orders` → `retailer_chargebacks`
  (by `retailer_id + sku`, chargeback `month` within 90 days of `ship_date`); label each
  shipment-SKU as `chargeback = 1` or `0`
- Point-in-time join: for each shipment, look up `product_master_history` where
  `snapshot_date ≤ ship_date ORDER BY snapshot_date DESC LIMIT 1`; extract
  `gtin14_missing`, `case_dims_missing`, `case_weight_missing`, `upc_missing`,
  `data_quality_score`
- Add shipment compliance features from `fct_retailer_shipments`:
  `asn_sent_late`, `days_late`, `all_labels_scannable`
- Add `sku_prior_chargeback_rate`: for each row, compute the chargeback rate for that
  SKU at that retailer using only shipments strictly before the current `ship_date`
  (expanding window, no leakage); rows with no prior history use the dataset mean
- One-hot encode `retailer_id`
- Impute any remaining NaN with column mean/mode; assert no NaN in output
- Save to `output/frames/training_features.parquet`

**Test scenarios:**
- Point-in-time join uses historical state: a shipment before a GTIN was populated has
  `gtin14_missing = True` even if `product_master` currently shows it present
- `sku_prior_chargeback_rate` for the first shipment of a SKU uses the dataset mean
  (no leakage from future data)
- Output DataFrame has zero NaN values
- Row count equals total shipment-SKU pairs in the training window
- `chargeback` label rate roughly matches the known chargeback rate in the data

**Verification:** Feature DataFrame produced without NaN; point-in-time join verified by
spot-checking 5–10 known shipments against their actual chargeback outcomes.

---

### U5. Interpretable model training + SHAP attribution (Move 3)

**Goal:** Train a RandomForestClassifier, validate on held-out data, compute SHAP values,
and generate a plain-language attribution string for every prediction.

**Requirements:** The model's predictions and attributions are the core of every
deliverable. *(See origin: Move 3)*

**Dependencies:** U4

**Files:**
- `src/pipeline/04_model.py`
- `output/model/` (gitignored)
- `output/frames/shap_values.parquet`
- `output/frames/attribution_strings.parquet`
- `output/frames/model_performance.csv`
- `tests/pipeline/test_model.py`

**Approach:**
- Temporal train/test split: earlier shipments → train, later shipments → test
  (never random — would leak future data)
- RandomForestClassifier with `class_weight='balanced'` (chargebacks are rare events)
- Evaluate on held-out set: precision, recall, AUC; target AUC ≥ 0.70; flag if < 0.65
  and halt before generating deliverables — model needs investigation
- SHAP: `TreeExplainer` on the fitted model; compute SHAP values for all rows
  (train + test + forward POs)
- Attribution string: identify the top-1 positive SHAP feature per row; map internal
  column name to human-readable label; template:
  `"{label} → {archetype} → {probability:.0%} probability within 14 days"`
  e.g., `"Missing case dimensions → logistics audit → 78% probability within 14 days"`
- Save: model artifact (joblib), SHAP frame, attribution strings, performance metrics

**Test scenarios:**
- Model trains without error on the full feature DataFrame
- Held-out AUC ≥ 0.65 (hard gate — halt pipeline if not met)
- Attribution strings are non-empty for every row (no `None`, no unfilled templates)
- Human-readable labels are used throughout (not internal column names)
- High-probability rows (probability ≥ 0.5) have at least one positive SHAP feature
- Model artifact serializes and deserializes cleanly (joblib round-trip)
- Performance CSV has exactly one row with columns: `auc`, `precision`, `recall`, `n_train`,
  `n_test`

**Verification:** AUC reported and meets threshold; 10 high-risk attribution strings
spot-checked for plausibility; model artifact saved.

---

### U6. Forward risk scoring + prevention roadmap (Moves 4–5)

**Goal:** Score upcoming purchase orders for chargeback risk with dollar exposure; compute
the ranked prevention roadmap.

**Requirements:** Produces the Predictive Exposure Ledger and Data Remediation Business
Case inputs. *(See origin: Moves 4–5)*

**Dependencies:** U5

**Files:**
- `src/pipeline/05_score.py`
- `src/pipeline/06_roadmap.py`
- `output/frames/scored_pos.parquet`
- `output/frames/prevention_roadmap.parquet`

**Approach:**
- **Forward scoring** (`05_score.py`): pull `retailer_orders` without a matched chargeback
  yet; compute features using current `product_master` (forward-looking is correct here);
  run `model.predict_proba()`; compute
  `dollar_exposure = order_value × chargeback_probability`; attach SHAP attribution string;
  rank by `dollar_exposure` descending
- **Prevention roadmap** (`06_roadmap.py`): group historical chargebacks by
  `root_cause_archetype`; apply preventability fractions (data quality archetypes ~80%
  preventable, logistics ~70%, ASN timing ~70%, `legitimate` ~20%); compute
  `prevention_value = historical_loss × preventability`; rank descending; attach
  plain-English fix description per archetype (e.g., `data_compliance_error` →
  `"Populate missing GTIN and case dimensions in product master"`)

**Test scenarios:**
- Every scored PO has `dollar_exposure ≥ 0`; `dollar_exposure = 0` for rows with
  `probability ≈ 0`
- Prevention roadmap has exactly one row per archetype (no duplicates)
- Prevention roadmap `prevention_value` values sum to ≤ total historical chargeback
  amount (no overcounting)
- Roadmap rows are sorted by `prevention_value` descending
- Top roadmap item roughly matches the project brief's $240K logistics figure

**Verification:** Scored POs plausible (top-risk rows have known data quality issues);
roadmap sums verify; brief's $410K preventable figure is reproduced within ±20%.

---

### U7. Pipeline orchestration + JSON/CSV export

**Goal:** Wire the six pipeline steps into a single runnable entry point; export all
outputs in the formats each deliverable layer needs.

**Requirements:** Enables one-command pipeline execution; decouples pipeline from
deliverables.

**Dependencies:** U6

**Files:**
- `run_pipeline.py`
- `src/pipeline/07_export.py`
- `frontend/public/json/risk_ledger.json`
- `frontend/public/json/simulator.json`
- `frontend/public/json/summary.json`
- `output/frames/prevention_roadmap.csv`
- `output/frames/historical_chargebacks_by_archetype.csv`
- `output/frames/model_performance.csv`
- `config.yml`

**Approach:**
- `run_pipeline.py`: calls steps 01–07 in order; logs step start/end with timestamps;
  exits non-zero on any step failure
- JSON for React:
  - `risk_ledger.json`: array of scored POs — `{sku, retailer, ship_date, probability,
    dollar_exposure, attribution_string, risk_tier}`
  - `simulator.json`: same rows plus `shap_values: {feature: value}` dict (needed for
    the simulator to recompute exposure when features are toggled in-browser)
  - `summary.json`: headline numbers — `total_chargeback_amount`, `total_preventable`,
    `preventable_pct`, `root_cause_counts`, `model_auc`
- CSV for Quarto: `prevention_roadmap.csv`, `historical_chargebacks_by_archetype.csv`,
  `model_performance.csv`
- `config.yml`: engagement name, run date (stamped at execution time), pipeline version

**Test scenarios:**
- `run_pipeline.py` completes end-to-end without error (integration test using a
  small fixture dataset in `tests/fixtures/`)
- `risk_ledger.json` is valid JSON; every row has a non-null `attribution_string`
- `simulator.json` `shap_values` dict contains one key per feature used in the model
- `summary.json` `total_preventable` ≤ `total_chargeback_amount`
- Running the pipeline twice produces identical JSON output (deterministic model seed)

**Verification:** All JSON and CSV files present and non-empty; `risk_ledger.json` loads
in a browser without error.

---

### U8. React app scaffold

**Goal:** Initialize the React/Vite/TypeScript app following the Retailer Deduction
Recovery pattern with Lailara Design System v2 tokens.

**Requirements:** Foundation for U9 and U10. *(See origin: One combined React app,
Cloudflare Pages)*

**Dependencies:** U7 (JSON files must exist for development)

**Files:**
- `frontend/package.json`
- `frontend/vite.config.ts`
- `frontend/tsconfig.json`
- `frontend/wrangler.jsonc`
- `frontend/index.html`
- `frontend/src/main.tsx`
- `frontend/src/App.tsx`
- `frontend/src/App.css`
- `frontend/src/data.ts`

**Patterns to follow:** `retailer-deduction-recovery/frontend/` — exact same Vite +
React 19 + TypeScript + `@cloudflare/vite-plugin` stack; CSS custom properties for
Lailara tokens; `fetch()`-based JSON loading in `data.ts`; `Promise.all()` at mount.

**Approach:**
- Copy Lailara CSS token definitions from `retailer-deduction-recovery/frontend/src/App.css`
  as starting point; update with full Design System v2 token set
- `data.ts`: three async functions loading `risk_ledger.json`, `simulator.json`,
  `summary.json` from `/json/`
- `App.tsx`: two-tab navigation (Risk Ledger | Simulator); loads all JSON at mount;
  distributes to state via `useState`; no routing library
- `wrangler.jsonc`: SPA routing (all 404s → `index.html`), `nodejs_compat` flag

**Test scenarios:**
- `npm run build` passes TypeScript check and produces a `dist/` directory
- App renders in browser with no console errors when JSON files are present
- Both tab views render without crashing when passed empty arrays

**Verification:** `npm run dev` shows the two-tab shell; JSON loads in network tab.

---

### U9. Interactive Risk Ledger view

**Goal:** Build the Risk Ledger — upcoming shipments ranked by chargeback risk and dollar
exposure, filterable by retailer and risk tier, with click-to-pin attribution detail.

**Requirements:** Artifact 1 — Risk Ledger view. *(See origin: Interactive risk ledger)*

**Dependencies:** U8

**Files:**
- `frontend/src/views/RiskLedger.tsx`
- `frontend/src/views/RiskLedger.css`
- `frontend/src/components/RiskBadge.tsx`
- `frontend/src/components/RetailerFilter.tsx`

**Approach:**
- Table: rows sorted by `dollar_exposure` descending; columns: SKU, retailer, ship date,
  risk badge (HIGH/MEDIUM/LOW), dollar exposure, attribution string
- Risk tiers: HIGH ≥ 50%, MEDIUM 20–50%, LOW < 20%; Lailara semantic status colors
  (Tokyo-40 for HIGH, Singapore-55 for MEDIUM, HK-35 for LOW)
- Filters: retailer dropdown + risk tier toggle chips; `useMemo` filters on App state
- Click-to-pin: clicking a row pins a dark callout card above the table showing full
  feature breakdown (each feature's value and its SHAP contribution); click again to dismiss
- Summary bar: total upcoming exposure, count HIGH-risk shipments, top at-risk SKU

**Test scenarios:**
- Initial load: rows sorted by `dollar_exposure` descending
- Retailer filter: selecting one retailer hides all other retailers' rows
- Risk tier toggle: selecting HIGH hides MEDIUM and LOW rows
- Click-to-pin: clicking row shows card with the correct `attribution_string` from data
- Clicking pinned row dismisses card
- Summary bar totals update when filters change

**Verification:** All rows render; filters work correctly; attribution card shows
correct string from `risk_ledger.json`.

---

### U10. Intervention Simulator view

**Goal:** Build the Intervention Simulator — toggle data quality fixes and see projected
chargeback reduction update in real time, powered by pre-computed SHAP values.

**Requirements:** Artifact 1 — Simulator view. The portfolio differentiator. *(See origin:
Intervention Simulator)*

**Dependencies:** U8, U9 (shares layout components)

**Files:**
- `frontend/src/views/Simulator.tsx`
- `frontend/src/views/Simulator.css`
- `frontend/src/components/FixToggle.tsx`
- `frontend/src/components/ImpactMeter.tsx`

**Approach:**
- Left panel: one toggle per fixable feature (`gtin14_missing`, `case_dims_missing`,
  `case_weight_missing`, `upc_missing`, `asn_sent_late`); each toggle shows how many
  high-risk shipments it affects
- Right panel: live-updating — projected chargebacks prevented, projected dollar savings,
  prevention % of total exposure
- Calculation: when a toggle is flipped, re-score affected rows in `simulator.json`
  by setting the toggled feature's value to 0 (fixed); compute the delta in
  `dollar_exposure` using the pre-stored `shap_values`; this is pure JS math on loaded
  data, no backend call
- Prevention ROI callout card: `"Fixing these [N] conditions would prevent an estimated
  $[X]/year — permanently."`
- If no toggles are on: savings = $0 and a prompt to toggle a fix

**Test scenarios:**
- All toggles off: projected savings = $0
- Toggling `case_dims_missing` fix: savings = sum of `dollar_exposure` reduction for
  rows where `case_dims_missing = true`
- All toggles on: total savings ≤ `summary.json` `total_preventable` (no overcounting)
- Rapid toggling (multiple clicks) produces correct final state, not a stale intermediate
- Impact meter updates synchronously (no visible lag on toggle)

**Verification:** Top fix produces a savings estimate that approximately matches the
prevention roadmap's top root cause; numbers are internally consistent with
`simulator.json`.

---

### U11. Cloudflare Pages deployment

**Goal:** Deploy the React app to Cloudflare Pages and verify it renders correctly in
production.

**Requirements:** Deliverable must be publicly accessible. *(See origin: Cloudflare Pages)*

**Dependencies:** U9, U10

**Files:**
- `frontend/wrangler.jsonc` (already created in U8)
- `.github/workflows/deploy-frontend.yml` (optional — or manual wrangler deploy)

**Patterns to follow:** `retailer-deduction-recovery/frontend/wrangler.jsonc` and
deploy workflow.

**Test scenarios:**
- Production build loads without console errors
- Direct URL navigation to each view works (SPA routing)
- `/json/risk_ledger.json` is reachable in production

**Verification:** Production URL resolves; both views load; JSON fetches succeed in
production network tab.

---

### U12. Quarto project scaffold

**Goal:** Initialize the Quarto project with Python engine, Lailara CSS, and shared
infrastructure for all three reports.

**Requirements:** Foundation for U13, U14, U15.

**Dependencies:** U7

**Files:**
- `quarto/_quarto.yml`
- `quarto/assets/report.css`
- `config.yml`
- `requirements.txt` (add: `quarto`, `plotly`, `kaleido` for static chart export)

**Patterns to follow:** `product-data-health-audit/quarto/` structure;
`product-data-health-audit/quarto/assets/report.css` for Lailara tokens (adapt to
Python/Plotly rather than R/ggplot2).

**Approach:**
- `_quarto.yml`: `engine: jupyter`; output-dir `_site`; shared CSS `assets/report.css`;
  project type `website`
- `report.css`: full Lailara Design System v2 token set (canvas background, Chicago navy,
  Playfair Display headings, Source Sans 3 body); adapted from published design system
  at `~/projects/published/lailara-design-system/`
- Shared Python setup chunk used by all `.qmd` files: imports pandas + plotly, reads
  `config.yml` and relevant CSV/Parquet from `output/frames/`
- Verify `quarto render` produces valid HTML for a stub `.qmd`

**Test scenarios:**
- `quarto render` completes on a minimal stub `.qmd` with no errors
- Lailara canvas background and typography are visible in rendered HTML
- Python chunk successfully reads `config.yml` and a sample CSV from `output/frames/`

**Verification:** One stub `.qmd` renders to styled HTML.

---

### U13. Prevention Roadmap Report

**Goal:** Build the Prevention Roadmap Report — narrative + charts + ranked table — the
board-ready business case for data fixes.

**Requirements:** Artifact 2. *(See origin: Prevention roadmap report)*

**Dependencies:** U12

**Files:**
- `quarto/prevention_roadmap.qmd`
- `output/frames/prevention_roadmap.csv` (consumed)
- `output/frames/historical_chargebacks_by_archetype.csv` (consumed)

**Approach:**
- Five sections: (1) executive summary (`"$410K of Cinderhaven's $680K chargeback bill
  traces to four fixable data problems"`), (2) margin math table (root cause → historical
  loss → preventable → action), (3) root-cause attribution bar chart (Lailara HK teal
  palette, darkest = largest), (4) ranked prevention roadmap table with action column,
  (5) recovery vs. prevention economics argument
- Charts: Plotly (interactive hover in HTML); `kaleido` for static PNG fallback for PDF
- Voice: Economist style throughout — declarative, data-forward, no hedging
- Synthetic data disclaimer: one sentence explicitly framing this as a demonstrable
  methodology

**Test scenarios:**
- Report renders to HTML without error
- All charts appear; no broken Plotly imports
- Margin math table numbers match `prevention_roadmap.csv` values exactly (no hardcoded)
- PDF export renders (if enabled in `_quarto.yml`) without missing fonts

**Verification:** HTML report loads; all 5 sections present; numbers are internally
consistent with pipeline outputs.

---

### U14. Executive Tearsheet

**Goal:** Two-page standalone CFO document: the reframe + three headline numbers +
prevention roadmap summary.

**Requirements:** Artifact 3. *(See origin: Executive tearsheet)*

**Dependencies:** U12

**Files:**
- `quarto/tearsheet.qmd`

**Approach:**
- Two-page layout: page 1 = reframe statement + three headline numbers using Playfair
  Display 64px (`$680K total`, `$410K preventable`, `4 root causes`); page 2 = ranked
  prevention roadmap table + one-paragraph prevention/recovery economics argument
- PDF-primary; HTML also rendered
- No charts, no interactivity — designed to be emailed or printed in 60 seconds
- Headline numbers loaded from `summary.json` / `prevention_roadmap.csv` (not hardcoded)
- Synthetic data disclaimer in page 2 footnote

**Test scenarios:**
- PDF renders to ≤ 2 pages (flag if longer — layout needs adjustment)
- Headline numbers match `summary.json` values
- No Quarto rendering errors or broken references

**Verification:** PDF is two pages; numbers correct; legible standalone without context.

---

### U15. Methodology Appendix

**Goal:** Document the three differentiating pieces of engineering for technical
evaluators and prospects.

**Requirements:** Artifact 4. *(See origin: Methodology appendix)*

**Dependencies:** U12

**Files:**
- `quarto/methodology.qmd`
- `output/frames/model_performance.csv` (consumed)

**Approach:**
- Three sections: (1) Cross-retailer reason-code harmonization — explain the dual-pathway,
  show the complete archetype mapping table (all 6 archetypes + example codes for each
  retailer); (2) Point-in-time feature engineering — explain why today's `product_master`
  breaks the model; show the reconstruction approach; (3) Interpretable model design —
  explain interpretability mandate; show SHAP attribution worked example end-to-end
  (one high-risk shipment → features → probabilities → attribution string)
- Model performance metrics (AUC, precision, recall) with honest framing
- HTML-primary; PDF also rendered

**Test scenarios:**
- All three sections render without error
- Archetype mapping table covers all 6 archetypes
- Model performance metrics match `model_performance.csv` (not hardcoded)
- Worked example attribution string matches actual model output for the chosen shipment

**Verification:** HTML renders; three sections complete; worked example is
internally consistent with pipeline outputs.

---

### U16. GitHub Actions CI/CD for Quarto reports

**Goal:** Automate Quarto report rendering and deployment to GitHub Pages on push to main.

**Requirements:** Enables deliverable publishing without manual render steps.

**Dependencies:** U13, U14, U15

**Files:**
- `.github/workflows/render.yml`

**Patterns to follow:** `product-data-health-audit/.github/workflows/render.yml` — adapt
from R/renv to Python/pip.

**Approach:**
- Steps: checkout → setup Python → install Quarto + TinyTeX → `pip install -r requirements.txt`
  → `python run_pipeline.py` → `quarto render quarto/` → upload `quarto/_site` to
  GitHub Pages
- `DATABASE_URL` passed as GitHub secret
- Triggers: push to main, manual dispatch
- Cache: `pip` cache keyed on `requirements.txt` hash

**Test scenarios:**
- Workflow runs end-to-end on push to main without error
- GitHub Pages URL serves all three rendered reports
- `DATABASE_URL` secret is consumed by the pipeline step (connection succeeds)

**Verification:** GitHub Pages URL resolves; all three Quarto reports accessible.

---

## System-Wide Impact

| Surface | Change | Notes |
|---|---|---|
| Cinderhaven Data Platform | New `product_master_history` table (U2) | Tracked in that repo; consumed here via read-only SQL |
| Cloudflare Pages | New site: Interactive Risk Ledger + Simulator | U11 |
| GitHub Pages | New site: three Quarto reports | U16 |
| Cinderhaven Postgres | Read-only queries only | No writes from this project |

---

## Scope Boundaries

### In scope
- All five analytical moves on Cinderhaven data (Moves 1–5)
- Five artifacts: Interactive Risk Ledger, Intervention Simulator, Prevention Roadmap
  Report, Executive Tearsheet, Methodology Appendix
- Lailara Design System v2 throughout all deliverables
- Cloudflare Pages (React app) + GitHub Pages (Quarto reports)
- Cinderhaven Data Platform as SSOT (Postgres via Fly.io)

### Deferred to Follow-Up Work
- Upgrade RandomForest → GradientBoosting if AUC < 0.65 after U5
- dbt model in Cinderhaven to automate ongoing `product_master_history` maintenance
- `/ce:review` + `/qa` pass after all deliverables are complete
- Mobile layout optimization (deliverables are desktop-first)

### Outside scope
- Real-time pre-ship scoring integration (engagement/integration work)
- Dispute automation (deduction-recovery territory)
- Actual data remediation for Cinderhaven (separate engagement)
- Non-Cinderhaven data sources
- Black-box models (barred — interpretability mandated)

---

## Deferred Implementation Notes

- **Exact regex patterns for free-text harmonization (U3):** determined after reading
  the actual `retailer_chargebacks.reason` values in EDA (U1); cannot be specified before
  that data is seen
- **Chargeback-to-shipment join logic (U4):** depends on EDA findings about how tightly
  chargebacks link to specific shipments; may be a direct `order_id` join or a looser
  `retailer_id + sku + date window` join
- **Model hyperparameters (U5):** determined by cross-validation at training time;
  RandomForest defaults are a sensible starting point
- **Quarto PDF engine (U14):** TinyTeX vs. Chromium-based determined by U12 setup

---

## Risk Analysis

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Chargeback-to-shipment join match rate < 50% | Medium | High — blocks feature engineering | EDA in U1 confirms rate before committing to U4; if low, relax join to retailer + sku + month window |
| Small dataset (≤ 450 chargeback events) → AUC < 0.65 | Medium | High — blocks deliverables | U5 hard gate: halt before generating deliverables; options: (1) feature engineering improvements, (2) upgrade to GradientBoosting, (3) reframe from "per-shipment" to "per-SKU-retailer" target (larger n) |
| product_master_history enrichment is time-consuming in Cinderhaven | Low-Medium | Medium — delays U4 | Scope is well-defined; synthetic seed is under our control; risk is effort, not feasibility |
| SHAP simulator math is inconsistent with model predictions | Low | Medium — undermines credibility | Simulator uses actual pre-stored SHAP values from the model run; spot-check 5 simulator results against model.predict_proba() directly |
| Cloudflare Pages / wrangler config drift from Retailer Deduction Recovery | Low | Low — deployment friction only | Copy wrangler.jsonc directly; deploy manually first, automate later |
| Quarto PDF rendering requires LaTeX configuration | Low | Low — tearsheet and methodology may be HTML-only initially | Try HTML-first; add TinyTeX setup in U16 if PDF is needed for the tearsheet |

---

## Open Questions

- **Chargeback-to-shipment join match rate (blocking for U4):** EDA in U1 must confirm
  ≥ 50% match rate. If lower, the target variable construction needs revision before
  proceeding to feature engineering.
- **Product_master_history date range:** History table should span the full range of
  `retailer_shipments.ship_date`. Confirm in EDA (U1) before seeding Cinderhaven (U2).
