# Requirements: Chargeback Prediction Model — Portfolio Suite

**Status:** Ready for planning  
**Date:** 2026-05-31  
**Tier:** Heavy  
**Next step:** `/ce:plan`

---

## Problem

Specialty food brands at retail absorb $200K–$1.5M/year in chargebacks with no ability to predict or prevent them. The deductions person disputes reactively; the CFO sees a single P&L line. Nobody has connected upstream data quality conditions to the downstream chargeback outcomes they cause — because the two datasets (chargeback remittances and product/EDI data) have never been joined, and because retailers have no incentive to help brands prevent the chargebacks that generate revenue for them.

The result: brands stay on a dispute treadmill, recovering some of each quarter's losses while the same data problems generate the same chargebacks next quarter.

**Business question:** Which upstream data quality conditions will generate chargebacks, at what probability and dollar value, so the brand can intervene before shipment?

**The reframe:** Chargebacks aren't random — they're scheduled. They are the predictable downstream consequence of specific, fixable upstream conditions. ~60% of Cinderhaven's $680K/year chargeback bill traces to four data quality root causes.

---

## Target Audiences

| Audience | Primary need | Which artifact serves them |
|---|---|---|
| CFO | Understand the prevention opportunity; fund the data fix | Executive Tearsheet, Prevention Roadmap Report |
| COO / ops lead | Know which shipments are at risk before they ship | Interactive Risk Ledger |
| Deductions person | Prioritized, attributed queue instead of a blind backlog | Interactive Risk Ledger |
| Data / IT lead | Quantified ROI for the data cleanup they've been requesting | Prevention Roadmap Report, Methodology Appendix |
| Technical evaluator (prospect) | Proof the methodology is real and differentiated | Methodology Appendix |

---

## Deliverables (Five Artifacts)

### 1. Interactive Risk Ledger + Intervention Simulator (one React app, two views)

**Risk Ledger view:** Upcoming shipments ranked by predicted chargeback probability and dollar exposure. Each row carries a plain-language attribution string naming the specific data condition driving the risk ("missing case dimensions → $4,200 exposure at Walmart"). Filterable by retailer, SKU, risk tier.

**Intervention Simulator view:** Toggle specific data quality fixes (e.g., "populate case dimensions on SKU X at Walmart") and see projected chargeback reduction and prevention ROI update in real time. The only artifact of its kind — no recovery consultant offers this.

**Format:** React/Vite SPA, pre-computed JSON data layer from Python pipeline. Deployed to GitHub Pages. Lailara Design System v2.

---

### 2. Prevention Roadmap Report

Root causes ranked by prevention value with dollar estimates. Narrative + charts + ranked table. The board-ready business case: "fix these four things once, prevent $410K/year permanently."

Includes the margin math table (root cause → historical loss → preventable → actionable fix) and the prevention-vs-recovery economics argument.

**Format:** Quarto HTML with embedded Plotly/interactive charts. PDF export. Lailara Design System v2.

---

### 3. Executive Tearsheet

Two pages. Standalone. The CFO pitch document: "your chargebacks aren't random" reframe + three headline numbers ($680K total, $410K preventable, four root causes) + the prevention roadmap summary. Email-safe and printable.

**Format:** Quarto PDF-primary with HTML version. No interactivity. Lailara Design System v2.

---

### 4. Methodology Appendix

The credibility marker for technical evaluators. Explains the three differentiating pieces of engineering:
1. Cross-retailer reason-code harmonization (how Walmart Code 22 + Target Vendor Perf + KeHE Admin Fee all map to the same root cause)
2. Point-in-time feature engineering (why using today's product master breaks the model; how historical data quality state is reconstructed)
3. Interpretable model design (why black-box models are barred; what SHAP attribution provides that a probability score alone doesn't)

**Format:** Quarto HTML. Lailara Design System v2.

---

### 5. (Captured above — the Intervention Simulator is Artifact 1's second view)

---

## Five Analytical Moves (the pipeline)

These are what the Python pipeline must produce. They feed all five deliverables.

| Move | What it produces | Feeds |
|---|---|---|
| Move 1 — Reason-code harmonization | Canonical root-cause archetypes for all Cinderhaven chargebacks | Model target variable, Methodology Appendix |
| Move 2 — Point-in-time feature engineering | Data quality state at shipment time for each historical chargeback | Model features, Methodology Appendix |
| Move 3 — Interpretable model + SHAP | Per-shipment chargeback probability + attribution strings | Risk Ledger, Simulator |
| Move 4 — Forward risk scoring | Upcoming POs scored with dollar exposure | Risk Ledger |
| Move 5 — Prevention roadmap | Root causes ranked by prevention value with dollar estimates | Prevention Roadmap Report, Tearsheet |

---

## Key Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Deliverable shape | Multi-artifact collection | Different audiences need purpose-built formats; not all content is interactive |
| Interactive stack | React/Vite + pre-computed JSON | Richer interactivity for ledger + simulator; same pattern as Retailer Deduction Recovery |
| Report stack | Python + Quarto | Consistent with Product Data Health Audit; HTML + PDF from same source |
| Model family | Tree-based + SHAP attribution | Interpretability mandated; CFO needs to see WHY, not just probability |
| Black-box models | Barred | A CFO won't fund a data overhaul on a neural net's latent space |
| Historical data state | Point-in-time join required | Current product_master state breaks causal attribution for historical chargebacks |
| Data enrichment | Add signals to Cinderhaven if distribution_log + EDI signals are too sparse | Synthetic data = we control richness |

---

## Build Order (risk-first)

1. **Fly.io proxy setup + DB connectivity** — unblocks everything
2. **EDA on chargeback, shipment, and deduction data** — informs feature design
3. **Point-in-time join prototype (Move 2)** — highest technical risk; fail fast here before committing model architecture
4. **Reason-code harmonization (Move 1)** — required for model target variable
5. **Model + SHAP (Move 3)** — depends on 3 and 4
6. **Forward risk scoring + prevention roadmap (Moves 4–5)** — depends on model
7. **React app (Risk Ledger + Simulator)** — consumes JSON from pipeline
8. **Quarto reports (Prevention Roadmap, Tearsheet, Methodology)** — consumes pipeline outputs

---

## Scope

### In scope
- All five analytical moves on Cinderhaven data
- Five deliverables as described above
- Lailara Design System v2 throughout
- GitHub Pages deployment
- Cinderhaven Data Platform (Postgres via Fly.io) as SSOT

### Out of scope
- Real-time pre-ship scoring integration (engagement/integration work)
- Dispute automation (deduction-recovery territory)
- Actual data remediation (separate engagement)
- Non-Cinderhaven data sources
- Mobile-native or native app versions

---

## Success Criteria

- [ ] The "chargebacks aren't random" reframe is front-and-center in every artifact — the narrative opens the deliverable, the model proves it
- [ ] Every risk score carries a plain-language attribution string naming the specific data condition
- [ ] The prevention roadmap ranks root causes by dollar recovery value with specific, actionable fixes
- [ ] The Intervention Simulator lets a user toggle data quality fixes and see projected prevention ROI update in real time
- [ ] The Executive Tearsheet is standalone — usable without opening the app or reading the full report
- [ ] The Methodology Appendix explains the point-in-time join and reason-code harmonization in terms a technical evaluator can verify
- [ ] The synthetic-data framing is explicit: "this methodology, applied to your data, surfaces your root causes"
- [ ] All deliverables pass `/ce:review` and `/qa`
- [ ] Lailara Design System v2 applied throughout

---

## Dependencies and Constraints

- Cinderhaven Postgres requires `flyctl proxy` running locally during development
- `product_master` is current-state only — point-in-time join must reconstruct historical state from `distribution_log` auth/deauth dates and EDI change signals; enrich Cinderhaven if these signals prove too sparse
- Model interpretability is non-negotiable — any model choice must support auditable per-feature importance scores
- Small dataset (~2,000 deduction rows, ~7,200 shipment rows) — validate model on held-out data; spot-check SHAP attribution strings by hand before publishing
- Cinderhaven data is synthetic — deliverables must frame findings as demonstrating methodology, not as claims about a real brand

---

## Relationship to Existing Portfolio

| Project | Relationship |
|---|---|
| Retailer Deduction Recovery (published) | Recovery to this piece's prevention. React/JSON pattern to reuse. |
| Product Data Health Audit (published) | Cause to this piece's effect. Quarto/Python pattern to reuse. |
| EDI Pre-flight (published) | EDI errors are predictive features; Pre-flight catches some before they ship. |
| Contract-to-Cash (published) | Chargebacks are a gross-to-net leakage component C2C traces. |
