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

[Model choice, feature selection, evaluation decisions]

---

## Output Formats

[Decisions about deliverable formats, structure, organization]

---

## Writing & Voice

### 2026-05-31 — Use Economist style for all written deliverables
- **Why:** Lailara design system standard. Sober, declarative, data-forward. No marketing voice.
- **Scope:** All written output, chart titles, footnotes, the executive summary
- **Do not:** Use hedging language that softens a real finding, or marketing filler ("leverage," "unlock," "drive value")

---

## Reversed / Superseded

[Reversed decisions with links to replacements go here]
