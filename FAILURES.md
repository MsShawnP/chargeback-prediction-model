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

### 2026-05-31 — Seed script and dbt both failed to connect: POSTGRES_PASSWORD not in environment

**Attempted:** Ran `seed_product_master_history.py` from the cinderhaven-data-platform `scripts/` directory. Also ran `dbt run`. Both failed with authentication errors.

**Why it didn't work:** `seed_config.py` uses `os.environ.get('POSTGRES_PASSWORD', '')` as the password fallback. `dbt profiles.yml` uses `{{ env_var('POSTGRES_PASSWORD') }}`. Neither env var was exported in the shell.

**What we tried instead:** Prefixed both commands with `POSTGRES_PASSWORD=<password>`. Worked immediately.

**Status:** Resolved — consider adding `POSTGRES_PASSWORD` to the cinderhaven-data-platform `.env` and loading it in a project shell alias or `direnv`.

**Tags:** postgres, authentication, env-var, POSTGRES_PASSWORD, dbt, seed, cinderhaven
