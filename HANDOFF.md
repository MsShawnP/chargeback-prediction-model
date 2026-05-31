# chargeback-prediction-model — Handoff Log

Session-by-session state. Updated by /log mid-session and /wrap at
session end.

For durable choices, see DECISIONS.md.
For the current work arc, see PLAN.md.
For things that didn't work, see FAILURES.md.

---

## 2026-05-31 — U1 + U2 complete; both U4 blockers resolved

**Started from:** Full pre-work complete (clarify → gates → brainstorm → plan). No code existed.

**Did:**
- U1: `db.py`, EDA script, `requirements.txt`, `.env.example`, 2 passing tests. Ran live EDA against Cinderhaven — confirmed 96.5% chargeback-to-shipment join rate via multi-hop chain.
- U2: `raw.product_master_history` seeded (1,900 rows, 50 SKUs x 38 months, 39 SKUs with synthetic gaps), dbt view + 4 tests all passing. Committed in cinderhaven-data-platform.

**State:** U1 and U2 done. Tests green. Both blockers for U4 resolved. U3–U16 remain.

**Next:** U3 -- reason-code harmonization engine. `src/harmonization/reason_codes.py` + `src/pipeline/02_harmonize.py` + `tests/pipeline/test_harmonize.py`. Both `reason` and `deduction_type` are already clean enum codes -- no regex needed, just two lookup dicts mapping to the five canonical archetypes. Codes: `label_fine`, `damaged`, `pricing_error`, `late_delivery`, `short_ship` (reason); `label_fine`, `short_ship`, `slotting`, `pricing_error`, `damaged`, `spoilage`, `late_delivery`, `pallet_fine`, `promo_billback` (deduction_type).

---

## 2026-05-31 — U2 complete: product_master_history seeded and live

**Did:** Added `raw.product_master_history` to cinderhaven-data-platform.
1,900 rows (50 SKUs x 38 monthly snapshots, 2024-01-01 to 2027-02-01).
39/50 SKUs have synthetic historical data quality gaps that resolve
monotonically. dbt staging model + 4 tests all pass.

**Key facts for U4:**
- Point-in-time lookup: `WHERE sku = :sku AND snapshot_date <= :ship_date ORDER BY snapshot_date DESC LIMIT 1`
- History columns: `gtin14_present, upc_present, case_dims_present, case_weight_present, data_quality_score`
- Known test case: CHP-AS-001 has `gtin14_present = FALSE` before 2025-03-01
- Seed script: `cinderhaven-data-platform/scripts/seed_product_master_history.py` (SEED=42, reproducible)
- dbt view: `public_staging.stg_product_master_history`

**State:** U1 and U2 complete. Both blockers for U4 are resolved.

**Next:** U3 -- reason-code harmonization engine.
`src/harmonization/reason_codes.py` + `src/pipeline/02_harmonize.py` + `tests/pipeline/test_harmonize.py`.
Key simplification vs. plan: `reason` field and `deduction_type` both use structured codes
(`label_fine`, `damaged`, `pricing_error`, `late_delivery`, `short_ship`), not free text.
The "keyword/regex" pathway is not needed -- just a lookup dict per pathway.
Still need to map these codes to the five canonical archetypes.

---

## 2026-05-31 — U3 complete: reason-code harmonization engine live

**What changed:** Harmonization engine maps all reason codes and deduction types to 6 canonical archetypes.

**Why:** U3 is the categorical target source for model training and the lens for the prevention roadmap.

**State:** U1–U3 complete. 29/29 tests green (also fixed pre-existing `test_db.py` import-ordering bug). `src/harmonization/reason_codes.py` holds all mapping logic; `src/pipeline/02_harmonize.py` is the pipeline step runner. `item_setup_gap` archetype is defined but assigned by U4, not here — documented in reason_codes.py. U4–U16 remain.

**Next:** U4 — point-in-time feature engineering. `src/pipeline/03_features.py` + `tests/pipeline/test_features.py`. Join chargebacks → shipments via multi-hop chain (96.5% match rate per EDA), look up `product_master_history` at ship_date, compute `sku_prior_chargeback_rate` with expanding window.

---

## 2026-05-31 — U1 complete: DB connected, EDA run, schema mapped

**Started from:** U1 infrastructure spike. DB helper, EDA script, tests committed.

**Did:** Connected to Cinderhaven via flyctl proxy; ran full EDA against `raw.*` schema.

**EDA findings (canonical source of truth for all downstream units):**

- Actual schema: tables live in `raw.*` (not public). Marts in `public_marts.*` (fct_ prefix).
- Tables confirmed: `raw.retailer_chargebacks`, `raw.retailer_shipments`, `raw.retailer_orders`,
  `raw.retailer_order_lines`, `raw.product_master`, `raw.distribution_log`,
  `raw.retailer_deduction_codes`.

**Row counts (actual vs. plan estimate):**
- `retailer_chargebacks`: 690 (plan: ~450 -- higher, fine)
- `retailer_shipments`: 46,414 (plan: ~7,200 -- much higher, 3 years of data)
- `retailer_deductions`: 13,804 (plan: ~2,000 -- larger dataset)
- `product_master`: 50 SKUs (plan: 30 -- close)
- `distribution_log`: 10,638 rows

**Chargeback amounts:** $691,338 total -- matches the $680K in the brief.
**Date range:** shipments 2024-01-02 to 2027-01-07 (3 years); chargebacks 2024-01-01 to 2027-01-01.

**Join strategy (blocks U4):** Multi-hop join required -- chargebacks have no direct `order_id`.
Join chain: `retailer_chargebacks (retailer_id, sku, month)` -> `retailer_order_lines (sku)` ->
`retailer_orders (order_id, retailer_id)` -> `retailer_shipments (order_id, ship_date)`.
Match rate via this chain + 90-day window: **96.5% (666/690)**. Gate passed. Proceed with this join.

**Chargeback reasons (both fields are structured codes, not free text):**
- `reason` field values: `label_fine`, `damaged`, `pricing_error`, `late_delivery`, `short_ship`
- `deduction_type` values: `label_fine`, `short_ship`, `slotting`, `pricing_error`, `damaged`,
  `spoilage`, `late_delivery`, `pallet_fine`, `promo_billback`
- NOTE for U3: "free text" harmonization pathway is simpler than planned -- both fields use
  clean enum-style codes, not narrative text. Harmonization is a lookup dict, no regex needed.

**Product master:** 50 SKUs, 0% null on all key fields (gtin14, upc, case_dims, case_weight)
in current state. Confirms point-in-time join is needed -- today's clean state hides historical gaps.
Columns: `sku, product_name, gtin14, upc, case_pack_qty, unit_weight_lbs, case_weight_lbs,
case_length_in, case_width_in, case_height_in, last_updated`.

**Distribution log:** `(sku, store_id, authorized_date, deauthorized_date)` per-SKU-store auth events.
Spans the full shipment date range. Available for historical reconstruction narrative in methodology doc.

**ASN features:** `raw.retailer_shipments` has `asn_sent_late` boolean directly. ASN late rate: 8.6%.
No `days_late` column -- may need to compute from `ship_date` vs. `delivery_date` or `requested_ship_date`.

**State:** U1 fully complete. EDA script committed at `src/pipeline/eda.py`.
All code for U1 committed (`src/pipeline/db.py`, `requirements.txt`, `.env.example`, tests).

**Next:** U2 -- add `product_master_history` table to cinderhaven-data-platform.
Table must cover 2024-01-01 to 2027-01-07. Synthetic history only (current product_master
is 100% clean; historical gaps must be fabricated to demonstrate the methodology).
Check whether `days_late` needs to be derived or if it exists on another table before U4.

---

## 2026-05-31 — Full workflow gates complete; implementation plan ready

**Started from:** Empty project directory with one file (project brief). No git, no scaffolding.

**Did:** Ran full Heavy-tier pre-work — /new-project → /clarify → /office-hours →
/plan-ceo-review → /plan-eng-review → /ce:brainstorm → /ce:plan. Project is fully
scaffolded, all gates passed, requirements doc and 16-unit implementation plan written.
No code yet.

**State:** `docs/brainstorms/chargeback-prediction-requirements.md` and
`docs/plans/2026-05-31-001-feat-chargeback-prediction-suite-plan.md` in place.
GitHub remote live at https://github.com/MsShawnP/chargeback-prediction-model.
All workflow steps in PLAN.md through /ce:plan marked complete.

**Next:** Start /ce:work on U1 (infrastructure spike) — establish Cinderhaven Postgres
connection via `flyctl proxy`, EDA on the six tables, confirm chargeback-to-shipment
join match rate ≥ 50%. Then open PR in cinderhaven-data-platform for the
product_master_history enrichment (U2). These are the two blockers for all downstream
units.

---

## 2026-05-31 — Project initialized

**Started from:** New project setup via /new-project.

**Did:** Created repo structure — CLAUDE.md, PLAN.md, HANDOFF.md,
DECISIONS.md, FAILURES.md, README.md, .gitignore, src/CLAUDE.md,
tests/CLAUDE.md. Project brief already present at
portfolio_project_brief_chargeback_prediction.md. Git initialized,
initial commit made, GitHub private remote created.

**State:** Foundation in place. No arc defined yet — /clarify is the
next step to scope the first work arc.

**Next:** Run /clarify to get to 95% confidence on what to build first.
Then follow the Heavy tier workflow: /office-hours → /plan-ceo-review →
/plan-eng-review → /ce:brainstorm → /ce:plan → /ce:work.

---
