# chargeback-prediction-model — Current Work Plan

The current arc of work. Updated when the arc changes, not every
session. For session-by-session state, see HANDOFF.md.

---

## Goal — 2026-05-31

Build a complete, shippable Lailara portfolio piece proving that Cinderhaven's
chargebacks are predictable and ~60% preventable — from the "chargebacks aren't
random" reframe through an interpretable prediction model to a ranked prevention
roadmap, delivered as one or more interactive HTML pieces.

## Why this arc, why now

This is the portfolio's most technically ambitious piece and the predictive
bridge between Product Data Health Audit (cause) and Retailer Deduction Recovery
(effect). Building it now makes the causal argument across the whole portfolio
complete.

## Business question this arc answers

Which upstream data quality conditions will generate chargebacks, at what
probability and dollar value, so the brand can intervene before shipment?

## Confirmed scope

**In:**
- Cross-retailer reason-code harmonization engine (Move 1)
- Point-in-time feature engineering / historical data quality reconstruction (Move 2)
- Interpretable tree-based model + SHAP attribution (Move 3)
- Forward risk scoring on upcoming POs (Move 4)
- Capital-allocation prevention roadmap (Move 5)
- Interactive HTML portfolio deliverable(s) — story + methodology + outputs
- Cinderhaven Data Platform (Postgres) as SSOT

**Out:**
- Real-time pre-ship scoring integration (engagement work)
- Dispute automation (deduction-recovery territory)
- Actual data remediation (separate engagement)
- Black-box models (barred — interpretability mandated)

## Known constraint to solve in planning

`product_master` is current-state only. Point-in-time join must reconstruct
historical data quality from `distribution_log` auth/deauth dates and EDI
change signals. No shortcut to today's state.

## Tasks

- [x] Run /clarify to scope the first work arc (2026-05-31)
- [x] Run /office-hours to stress-test the approach (2026-05-31) — green light
- [x] Run /plan-ceo-review for product gate (2026-05-31) — ship it
- [x] Run /plan-eng-review for architecture gate (2026-05-31) — sound
- [x] Run /ce:brainstorm to produce the spec (2026-05-31) — docs/brainstorms/chargeback-prediction-requirements.md
- [x] Run /ce:plan to research and plan implementation (2026-05-31) — docs/plans/2026-05-31-001-feat-chargeback-prediction-suite-plan.md
- [x] Run /ce:work — U1: DB helper, EDA script, tests (2026-05-31)
- [x] Run /ce:work — U2: product_master_history in cinderhaven-data-platform (2026-05-31)
- [x] Run /ce:work — U3: reason-code harmonization engine (2026-05-31)
- [x] Run /ce:work — U4: point-in-time feature engineering (2026-05-31)
- [x] Run /ce:work — U5: model training + SHAP attribution (2026-05-31)
- [x] Run /ce:work — U6: forward scoring + prevention roadmap (2026-05-31)
- [x] Run /ce:work — U7: pipeline orchestration + JSON/CSV export (2026-05-31)
- [x] Run /ce:work — U8–U10: React app (Risk Ledger + Simulator) (2026-05-31)
- [x] Run /ce:work — U11: Cloudflare Pages deployment (2026-05-31)
- [x] Run /ce:work — U12–U15: Quarto reports (2026-05-31)
- [x] Run /ce:work — U16: GitHub Actions CI/CD (2026-05-31)

## Definition of done for this arc

- [x] Interactive HTML deliverable(s) published and visually complete
- [x] Model trained on Cinderhaven data, predictions validated (2026-06-01 — AUC=0.7485, $691K chargebacks, $485K preventable 70%)
- [x] Every risk score carries a plain-language attribution string
- [x] Prevention roadmap ranks root causes by dollar recovery value
- [x] Passes /ce:review (2026-06-01 — 15 bugs fixed; /qa remaining)
- [x] Lailara design system applied throughout

---

## Arc history

[Arcs archived here as they complete]

---

## Improvement history

<!-- Entries are added by /improve — don't delete this section -->
