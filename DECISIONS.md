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

## Data & Schema

[Decisions about data sources, schemas, transformations]

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
