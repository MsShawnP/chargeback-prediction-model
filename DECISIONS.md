# chargeback-prediction-model — Decisions Log

Permanent record of choices that should survive session turnover.
If a decision is reversed, strike it through and add the replacement
below — don't delete.

---

## Format

Each entry:
- **Date** — when decided
- **Decision** — one sentence, imperative voice
- **Why** — the reasoning, including what was tried and rejected
- **Scope** — what this applies to (file, chunk, deliverable, or "global")
- **Do not** — explicit anti-instructions, if any

---

## Audit findings

### 2026-07-08 — WITHDRAWN: the portfolio audit's "impossible / mutually-impossible metrics" finding
- **Decision:** Withdraw the audit finding that the model's headline metrics — AUC 0.6986, precision 0.847, recall 0.7215 — were mutually impossible. The metrics are internally consistent and genuine; treat the finding as closed, not actionable.
- **Why:** The finding assumed a low positive base rate (~8%), at which that precision/recall pair would be arithmetically impossible. The realized synthetic `chargeback` label prevalence is ~72% (verified), and at that prevalence the three figures are consistent — all reproduced from a single `evaluate_model()` run. The defects that did exist (a hardcoded 0.7834, and AUC reported as recall) were real and are separately fixed. Nothing was fabricated.
- **Scope:** Model evaluation metrics and every report that cites them (tearsheet, methodology, prevention_roadmap).
- **Remaining action (distinct from the withdrawn finding):** The 72% synthetic base rate is itself unrealistic against a real-world chargeback rate of ~1.5%. The open item is to reseed the synthetic labels toward a ~1.5% base rate for a less-flattered demo; until then the reports disclose the synthetic-prevalence caveat.
- **Do not:** Re-open the "impossible metrics" finding without first checking the realized label prevalence — at ~72% the numbers hold together.

---

## Architecture & Pipeline

### 2026-05-31 — Use an interpretable tree-based model with SHAP-style attribution; black-box models barred
- **Why:** A CFO won't authorize a data overhaul on a neural net's latent space. Every risk score must come with a plain-language operational explanation ("missing net-weight attribute → 78% probability of compliance fine within 14 days"). Interpretability is the value, not marginal accuracy.
- **Scope:** Global — applies to model selection throughout the project
- **Do not:** Use neural nets, gradient boosted ensembles without attribution layers, or any model that can't produce auditable per-feature importance scores

### 2026-05-31 — Reconstruct data-quality state at shipment time (point-in-time join); do not use current product master as a proxy for historical state
- **Why:** The product master shows today's data. Attributing a six-month-old chargeback to a data condition requires knowing what the data looked like at shipment time. Where snapshots exist, use them; where they don't, proxy from EDI exception logs and product-setup modification histories.
- **Scope:** Feature engineering pipeline
- **Do not:** Join chargebacks to current product master state — this breaks the model's causal logic and produces false negatives for already-fixed data errors

---

### 2026-05-31 — Deliver five purpose-built artifacts, not a single SPA
- **Why:** Different audiences need different formats. The CFO needs a printable tearsheet; the deductions person needs an interactive risk ledger; a technical evaluator needs a methodology doc. A single SPA serves none of them optimally. Multi-artifact also matches the Product Data Health Audit pattern in the portfolio.
- **Scope:** All deliverable decisions for this project
- **Do not:** Collapse deliverables into a single app to save build effort — the audience split is the point

### 2026-05-31 — Split stack: Python ML pipeline + Quarto (reports) + React/Vite (interactive app)
- **Why:** Each layer does what it's best at. Python owns ML/SHAP; Quarto renders narrative HTML + PDF from the same source; React handles the stateful interactive pieces (ledger + simulator). Quarto uses the Python/jupyter engine (not R/knitr) to stay on one language.
- **Scope:** Global — defines the three-layer architecture
- **Do not:** Use R for any pipeline work; do not attempt to render interactive simulations in Quarto

---

## Data & Schema

### 2026-05-31 — Numbered pipeline scripts are thin runners; all testable logic lives in importable modules
- **Why:** Python cannot import files whose names begin with a digit (`03_features.py`). The first attempt put functions inside the numbered scripts and tests couldn't import them. The fix: core logic lives in a properly-named module (`features.py`, `reason_codes.py`); the numbered file only calls `run()`.
- **Scope:** Every pipeline step — `0N_*.py` is the DB-querying orchestration wrapper; `*.py` (no digit prefix) is where functions live and are tested.
- **Do not:** Put testable logic directly in numbered pipeline scripts. Do not import from `src.pipeline._03_features` or similar workarounds.

### 2026-05-31 — raw.retailer_shipments is line-level; direct join to chargebacks via retailer_id + sku works
- **Why:** U4 implementation confirmed that `retailer_shipments` already contains `retailer_id` and `sku` per row — it is a shipment-line table, not a shipment-header table. The EDA script's own date-window join (`ON c.retailer_id = s.retailer_id AND c.sku = s.sku`) achieved 96.5% and is the correct approach. The multi-hop through `retailer_orders + retailer_order_lines` is unnecessary for the chargeback label join.
- **Scope:** Feature engineering (U4) and any future query joining chargebacks to shipments
- **Do not:** Build the multi-hop join chain for the chargeback label — it adds complexity with no benefit. If a future unit needs `order_id`-level precision, re-evaluate then.

### 2026-05-31 — `item_setup_gap` archetype is assigned by feature engineering, not harmonization
- **Why:** No raw reason code or deduction_type maps to `item_setup_gap`. The archetype represents missing product master fields (GTIN absent, dimensions absent) which are only visible in `product_master_history` boolean flags — not in the chargeback reason strings. Assigning it during harmonization would require joining to product data, which is U4's job.
- **Scope:** `src/harmonization/reason_codes.py` and `src/pipeline/features.py`
- **Do not:** Add a mapping from any reason code to `item_setup_gap` in `reason_codes.py`. Set it in the feature engineering step based on `gtin14_missing` or similar flags if needed for model labeling.

### 2026-05-31 — Use multi-hop join chain for chargeback-to-shipment linkage; no direct join exists

- **Why:** `raw.retailer_chargebacks` has no `order_id` column; `raw.retailer_shipments` has no `retailer_id` or `sku`. The only valid join is: `retailer_chargebacks (retailer_id, sku, month)` → `retailer_order_lines (sku, order_id)` → `retailer_orders (order_id, retailer_id)` → `retailer_shipments (order_id, ship_date)`, with `chargeback.month BETWEEN ship_date AND ship_date + 90 days`. Confirmed 96.5% match rate in EDA.
- **Scope:** Feature engineering pipeline (U4), any future query joining chargebacks to shipments
- **Do not:** Attempt to join `retailer_chargebacks.order_id` to shipments — that column does not exist. Do not join on `retailer_shipments.retailer_id` — that column does not exist either.

### 2026-05-31 — Reason-code harmonization uses lookup dicts only; no regex or free-text parsing

- **Why:** EDA revealed that both `raw.retailer_chargebacks.reason` and `raw.retailer_deduction_codes.deduction_type` contain clean enum-style codes (`label_fine`, `damaged`, `pricing_error`, `late_delivery`, `short_ship`, etc.), not narrative free text. The "keyword/regex" pathway described in the implementation plan is unnecessary.
- **Scope:** `src/harmonization/reason_codes.py` and `src/pipeline/02_harmonize.py`
- **Do not:** Add a regex/keyword matching pathway — it adds complexity with no benefit given the structured codes. If new free-text fields appear in future data, revisit then.

---

## Modeling

### 2026-06-01 — Synthetic training labels; Cinderhaven raw.* is read-only for all projects

- **Why:** `raw.retailer_chargebacks` was seeded without correlations to quality or compliance features — chargebacks are statistically random (r < 0.003 for all features). Modifying the shared Postgres to embed signal would break 10+ dependent projects (confirmed by surveying trade-spend-leakage, competitive-shelf-intelligence, production-demand-forecast, sku-rationalization-framework, otif-blind-spot — all treat raw.* as read-only). `scripts/generate_training_data.py` generates synthetic labels from a domain-grounded causal model (ASN compliance × quality flags → chargeback probability) and writes `training_features_synthetic.parquet`. Forward scoring (step 05) always uses real Cinderhaven POs.
- **Scope:** Model training pipeline only. The synthetic file is generated locally and committed. It is not the source of truth for chargeback dollars or counts reported in deliverables.
- **Do not:** Modify `raw.retailer_chargebacks` or any other `raw.*` table to embed signal. Do not use real Cinderhaven chargeback labels for model training without first verifying they have signal (run the correlation check in `scripts/diagnose_signal.py` or equivalent).

---

## Output Formats

### 2026-06-01 — 07_export owns summary.json; generate_sample_json.py does not write it
- **Why:** After a real pipeline run, `07_export` writes `summary.json` with authoritative values (AUC, preventable amount, root-cause counts from Cinderhaven). `generate_sample_json.py` previously overwrote it with stale hardcoded numbers, which would have deployed wrong figures to the live app.
- **Scope:** Any script touching `frontend/public/json/summary.json`.
- **Do not:** Have `generate_sample_json.py` write `summary.json`, even as a fallback. If the pipeline hasn't run, the real values aren't known — an empty or stale file is less misleading than confidently wrong numbers.

---

### 2026-05-31 — Simulator savings math uses SHAP delta proxy; raw feature values not stored in simulator.json
- **Why:** `build_simulator_payload` enriches each risk-ledger row with per-feature SHAP values but not the original boolean feature values. The simulator interprets `shap_values[feature] > 0` as "this feature is active and contributing risk." Savings per row: `new_prob = max(0, prob − Σ positive_shap_deltas_for_active_toggles)`; `savings = delta_prob × (dollar_exposure / prob)`. This is pure JS math on the loaded JSON, no backend call.
- **Scope:** `frontend/src/views/Simulator.tsx` and `src/pipeline/export.py` (simulator payload schema)
- **Do not:** Store raw feature values in `simulator.json` to fix this — the SHAP proxy is intentional and avoids duplicating the feature matrix in the JSON. If exact feature values are needed for future UI (e.g., showing "this SKU has gtin14_missing = True"), add a `features` sub-dict to `build_simulator_payload`, update the TypeScript types, and revise the savings math accordingly.

---

### 2026-06-01 — Tests for pipeline output fields must assert the TypeScript-contract value, not just Python round-trip consistency
- **Why:** `assign_risk_tier` emitted `"low"/"medium"/"high"` and tests asserted those same lowercase values — tests passed for months while confirming the wrong behavior. The TypeScript `RiskEntry` type declared `"HIGH" | "MEDIUM" | "LOW"`. The bug was present from the first commit and only caught by code review, not tests.
- **Scope:** Any pipeline function whose output is consumed by the TypeScript frontend — field values, field names, and data types must be verified against `frontend/src/types.ts`, not just internal Python consistency.
- **Do not:** Write Python tests that only verify Python-to-Python round-trips for fields that cross the pipeline→frontend contract. If a TypeScript type declares a union or specific casing, the Python test must assert that exact value.

---

## Writing & Voice

### 2026-05-31 — Use Economist style for all written deliverables
- **Why:** Lailara design system standard. Sober, declarative, data-forward. No marketing voice.
- **Scope:** All written output, chart titles, footnotes, the executive summary
- **Do not:** Use hedging language that softens a real finding, or marketing filler ("leverage," "unlock," "drive value")

---

### 2026-05-31 — Commit sample JSON + CSV data with gitignore exceptions; deploy before real pipeline data is available

- **Why:** The pipeline requires `flyctl proxy` and a live Cinderhaven connection. Blocking the portfolio deployment on that connection means the deliverable isn't live until an arbitrary infrastructure step is complete. Sample data (generated with a committed script and a fixed seed) makes the app demonstrable immediately and gets replaced when the pipeline runs. The alternative — deploying an empty-array app — is a worse portfolio artifact.
- **Scope:** `frontend/public/json/` (React app) and `output/frames/*.csv` (Quarto reports). Both have `.gitignore` exceptions. The generator script `scripts/generate_sample_json.py` documents how to regenerate.
- **Do not:** Hard-code sample values in the app or reports — all numbers must come from the JSON/CSV files so that running the real pipeline automatically upgrades the deliverables without touching application code.

---

## Documentation Process

### 2026-06-01 — Always read the implementation before writing compound doc code examples
- **Why:** Solution Extractor composed examples from session notes and produced an additive probability model when the real script (`generate_training_data.py`) uses a multiplicative model — architecturally different. Feature names were also inverted (`missing_gtin14` vs. `gtin14_missing`). Both were caught by the Phase 3 Python reviewer, but only because Phase 3 ran. Examples composed from memory will be wrong in non-obvious ways.
- **Scope:** All `/ce:compound` runs that produce code examples. The orchestrator or Solution Extractor prompt must read the actual source files before drafting examples.
- **Do not:** Write documentation code examples from memory, session notes, or paraphrase. Always read the file first.

---

## Reversed / Superseded

### ~~2026-05-31 — Use multi-hop join chain for chargeback-to-shipment linkage; no direct join exists~~
**Superseded 2026-05-31 by the entry below.** The "no direct join" claim was wrong — `retailer_shipments` is at line granularity and has both `retailer_id` and `sku` directly.
