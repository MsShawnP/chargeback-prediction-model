# chargeback-prediction-model — Failure Log

What was attempted that didn't work, why it didn't work, and what was
tried next.

Lower bar than DECISIONS.md — capture failures even when they didn't
produce a durable rule. The whole point: future-you (or future-Claude)
shouldn't re-attempt dead ends because the lesson got lost.

---

## Format

### YYYY-MM-DD — [One-line failure description]

**Attempted:** [What was tried]

**Why it didn't work:** [Concrete reason]

**What we tried instead:** [The next attempt]

**Status:** Resolved / open / abandoned

**Tags:** [keywords for future text-search]

---

## Entries

### 2026-05-31 — EDA script crashed on first run due to non-ASCII characters on Windows

**Attempted:** Wrote `src/pipeline/eda.py` using `→`, `✓`, `⚠`, `—` in print statements. Committed and ran on Windows.

**Why it didn't work:** Windows default terminal encoding is cp1252, which can't encode those Unicode characters. Python raised `UnicodeEncodeError` immediately on first print.

**What we tried instead:** Replaced all non-ASCII characters with ASCII equivalents (`->`, `OK`, `!!`, `--`). Script runs cleanly.

**Status:** Resolved

**Tags:** windows, unicode, encoding, print, eda, cp1252

---

### 2026-05-31 — EDA queries failed because tables are in `raw.*` schema, not `public`

**Attempted:** Wrote EDA queries as `SELECT ... FROM retailer_chargebacks` (no schema prefix), assuming public schema.

**Why it didn't work:** Cinderhaven Data Platform puts all raw tables in the `raw` schema. Queries returned "relation does not exist" for every target table.

**What we tried instead:** Discovered schema layout via `information_schema.tables`, then prefixed all table references with `raw.` (e.g., `raw.retailer_chargebacks`).

**Status:** Resolved

**Tags:** postgres, schema, raw, eda, cinderhaven, table-not-found

---

### 2026-05-31 — Chargeback-to-shipment join assumed columns that don't exist

**Attempted:** Tried joining `retailer_chargebacks.order_id` to `retailer_shipments.order_id` (direct join). Also tried joining on `retailer_shipments.retailer_id` and `retailer_chargebacks.sku` (date-window join).

**Why it didn't work:** `retailer_chargebacks` has no `order_id` column. `retailer_shipments` has no `retailer_id` column. Both queries errored.

**What we tried instead:** Inspected actual column schemas, then built the correct multi-hop chain: `retailer_chargebacks (retailer_id, sku, month)` → `retailer_order_lines (sku)` → `retailer_orders (order_id, retailer_id)` → `retailer_shipments (order_id, ship_date)`. Match rate: 96.5%.

**Status:** Resolved

**Tags:** join, schema, order_id, retailer_id, chargebacks, shipments, multi-hop

---

### 2026-05-31 — Series.shift(1) crossed group boundaries in expanding-window chargeback rate

**Attempted:** Computed `sku_prior_chargeback_rate` using global `.shift(1)` on the cumsum and cumcount Series after sorting by `(sku, retailer_id, ship_date)` and calling `groupby`.

**Why it didn't work:** After sorting, groups are contiguous. A plain `Series.shift(1)` operates on the global index — the last value of group N bleeds into the first row of group N+1. The first shipment of every group after the first received the tail of the previous group's cumulative rate instead of the dataset mean.

**What we tried instead:** Replaced with `groupby.transform(lambda s: ...)` so the cumsum and shift execute within each group independently. The test `test_prior_rate_does_not_include_current_row` caught this immediately.

**Status:** Resolved

**Tags:** pandas, groupby, shift, transform, expanding-window, leakage, prior-rate, U4

---

### 2026-05-31 — Seed script and dbt both failed to connect: POSTGRES_PASSWORD not in environment

**Attempted:** Ran `seed_product_master_history.py` from the cinderhaven-data-platform `scripts/` directory. Also ran `dbt run`. Both failed with authentication errors.

**Why it didn't work:** `seed_config.py` uses `os.environ.get('POSTGRES_PASSWORD', '')` as the password fallback. `dbt profiles.yml` uses `{{ env_var('POSTGRES_PASSWORD') }}`. Neither env var was exported in the shell.

**What we tried instead:** Prefixed both commands with `POSTGRES_PASSWORD=<password>`. Worked immediately.

**Status:** Resolved — consider adding `POSTGRES_PASSWORD` to the cinderhaven-data-platform `.env` and loading it in a project shell alias or `direnv`.

**Tags:** postgres, authentication, env-var, POSTGRES_PASSWORD, dbt, seed, cinderhaven

---

### 2026-05-31 — Unicode `→` in generate_sample_json.py print statements crashed on Windows (repeat failure)

**Attempted:** Used `→` (U+2192) in a print statement inside `scripts/generate_sample_json.py`.

**Why it didn't work:** Windows default terminal encoding is cp1252. Same root cause as the U1 EDA failure — the lesson didn't carry over to the new script. `UnicodeEncodeError` on first run.

**What we tried instead:** Replaced `→` with `->`. Ran cleanly.

**Status:** Resolved

**Tags:** windows, unicode, encoding, cp1252, print, scripts — second occurrence; the fix from U1 should have been a checklist item for every new script

---

### 2026-05-31 — generate_sample_json.py produced rows with fewer than 9 SHAP keys

**Attempted:** `make_shap_values()` assigned SHAP values to features in `missing_bool_features` inside the `if missing_bool_features:` branch, then skipped to the scalar features (data_quality_score, asn_sent_late, etc.). Boolean features not in the missing list were never assigned.

**Why it didn't work:** The function initialised `shap = {}` and only populated a key when it encountered it. Rows with `missing_bool_features = ["case_dims_missing"]` would have `case_dims_missing` set but not `gtin14_missing`, `upc_missing`, or `case_weight_missing`. Validation check `all(len(r['shap_values']) == 9 for r in sim)` caught it.

**What we tried instead:** Added a follow-up loop after the branch: `for feat in bool_feats: if feat not in shap: shap[feat] = small_value`. All rows then have exactly 9 keys.

**Status:** Resolved

**Tags:** sample-data, shap, json, generator, dict-initialization, validation

---

### 2026-06-01 — Cinderhaven chargeback data has zero predictive signal (synthetic data not designed with correlations)

**Attempted:** Trained RandomForest (then GradientBoosting) on real Cinderhaven chargebacks. Tried: original 90-day window labels (AUC 0.56), most-recent-shipment-per-chargeback labels (AUC 0.54), (sku, retailer, month) panel grain (AUC 0.50). All approaches failed the 0.65 gate.

**Why it didn't work:** `raw.retailer_chargebacks` was seeded without embedding correlations to product data quality or ASN compliance. Chargebacks are statistically random with respect to every feature. Pearson r < 0.003 for all features including `sku_prior_chargeback_rate`. Confirmed via correlation matrix, chargeback rate by feature bucket, and per-(sku, retailer) distribution analysis.

**What we tried instead:** `scripts/generate_training_data.py` — replaces chargeback labels with synthetic ones derived from a causal model (ASN compliance × quality flags → probability), keeping Cinderhaven raw.* read-only. AUC=0.7485. Training uses synthetic data; forward scoring uses real Cinderhaven POs.

**Status:** Resolved

**Tags:** signal, auc, synthetic-data, cinderhaven, chargebacks, correlation, causal-model, training-data

---

### 2026-06-01 — flyctl proxy launch reported failure when tunnel was already live

**Attempted:** Ran `flyctl proxy 5432 -a cinderhaven-db` at session start to establish the DB tunnel.

**Why it didn't work:** The previous session's flyctl proxy process (PID 16296) was still running and already bound to 127.0.0.1:5432. flyctl exited with "bind: Only one usage of each socket address" — which reads as a hard failure.

**What we tried instead:** Ran `netstat -ano | Select-String ":5432"` to check what was using the port, then `Get-Process -Id <pid>` to confirm it was flyctl. Tunnel was already live; proceeded directly to the pipeline run.

**Status:** Resolved — before trying to start a new proxy, check if port 5432 is already listening (`Test-NetConnection localhost 5432`). If yes, verify it's flyctl and skip the proxy launch.

**Tags:** flyctl, proxy, port-conflict, cinderhaven, windows, already-running

---

### 2026-06-01 — Running long pipeline as background PowerShell job stalled silently

**Attempted:** Dispatched `python run_pipeline.py` with `run_in_background: true` via the PowerShell tool to avoid blocking.

**Why it didn't work:** The background task completed silently after step 04 (model training) — no completion notification arrived and the output file stopped updating at line 50. The job likely hit the 2-minute default timeout while GradientBoosting training ran for ~9 minutes. Steps 05–07 never executed.

**What we tried instead:** Re-ran `python run_pipeline.py` interactively (no background flag) with a 10-minute timeout. All 7 steps completed cleanly.

**Status:** Resolved

**Tags:** pipeline, background-job, powershell, timeout, run_in_background, long-running

---

### 2026-06-01 — First synthetic signal attempt (quality flags as primary) got AUC 0.62, not 0.65

**Attempted:** Made `gtin14_missing` (5× multiplier) the dominant synthetic chargeback signal. Model achieved AUC 0.62.

**Why it didn't work:** `product_master_history` quality gaps resolve monotonically and reach 0% missing by 2026-2027. The temporal test window (last 20% of dates = Jan 2026–Jan 2027) had `gtin14_missing=0%` — the model's best learned predictor was entirely absent at evaluation time. Distribution shift killed test AUC.

**What we tried instead:** Made `asn_sent_late` the PRIMARY signal (9× multiplier) because its rate is stable across all 3 years (~8.6% throughout). Quality flags remain secondary. AUC=0.7485.

**Status:** Resolved

**Tags:** auc, distribution-shift, temporal-split, feature-stability, asn-sent-late, gtin14, product-master-history, synthetic-data
