# chargeback-prediction-model

A predictive model that connects upstream data quality conditions to downstream
chargeback outcomes — proving that chargebacks aren't random, they're the
scheduled consequence of specific, fixable data deficiencies. Quantifies the
preventable portion and produces a capital-allocation roadmap ranking root
causes by prevention value.

## What it does

Takes a brand's chargeback history, product data, and EDI records and:

1. Harmonizes opaque, retailer-specific chargeback reason codes into uniform
   root-cause archetypes across retailers
2. Reconstructs data-quality state at shipment time (not today's state) to
   correctly attribute chargebacks to their upstream causes
3. Trains an interpretable model scoring chargeback probability per shipment,
   with SHAP-style attribution so every risk score names the specific data
   condition driving it
4. Scores upcoming purchase orders to flag high-exposure shipments before
   they leave the dock
5. Produces a ranked remediation roadmap: root causes ordered by prevention
   value, with dollar estimates

## How to run

TBD — stack and entry point to be settled in planning.

## Stack

TBD — see PLAN.md and DECISIONS.md for current direction.

## Project structure

```
chargeback-prediction-model/
├── src/                  # Source code
├── tests/                # Tests
├── CLAUDE.md             # Project context for Claude Code
├── PLAN.md               # Current work arc
├── HANDOFF.md            # Session-to-session continuity
├── DECISIONS.md          # Durable architectural choices
├── FAILURES.md           # What didn't work and why
└── portfolio_project_brief_chargeback_prediction.md  # Project brief
```

## Portfolio context

Part of the Lailara LLC analytics portfolio. Bridges the Product Data Health
Audit (finds the data problems) and Retailer Deduction Recovery (disputes
chargebacks after arrival) by proving the causal link and quantifying the
prevention opportunity.

---

Built by [Lailara LLC](https://lailarallc.com) — data hygiene and analytics consulting for specialty food brands scaling into national retail.
