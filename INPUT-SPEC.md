# INPUT-SPEC — chargeback-prediction-model (client mode)

What to hand the chargeback model in a client engagement. Derived from the code
that consumes the data (`src/pipeline/roadmap.py`, `src/pipeline/model.py`), not
the README. There are two intakes, for the two client-mode commands.

## 1. Chargeback ledger → prevention roadmap (`roadmap`)

The primary paid deliverable. One row per chargeback line as it appears on a
retailer remittance. CSV or XLSX (tolerant reader: UTF-8/BOM/latin-1, comma/
semicolon/tab, Excel dates as ISO, identifiers as text).

### Required

| Canonical | Type | Used for |
|---|---|---|
| `chargeback_id` | identifier (text, unique) | Row key. §1 |
| `amount` | number ≥ 0 | Historical loss per chargeback; summed by root cause. §2 |
| `chargeback_date` | date | Places each charge in the analysis window; annualization. §3 |

### Root-cause resolution (one of these two)

The roadmap groups loss by **root-cause archetype**. Provide the archetype
directly, or a reason code plus a mapping in `engagement.yml`:

| Canonical | Type | Used for |
|---|---|---|
| `root_cause_archetype` | string | Preferred: one of `data_compliance_error`, `item_setup_gap`, `logistics_overage`, `asn_timing_infraction`, `pricing_discrepancy`, `legitimate`. |
| `reason_code` | string | Alternative: the retailer's raw reason code, mapped to an archetype via `engagement.yml` `archetype_map`. Unmapped codes are **disclosed**, never silently dropped. |

If neither resolves to a known archetype for a row, that row is grouped under
`unmapped` and its share of loss is reported with a data-limitation note (it gets
a 0 preventability fraction unless you map it).

### Optional

| Canonical | Type | Unlocks |
|---|---|---|
| `retailer` | string | Per-retailer loss split in the deliverable. |

## 2. Training features → model metrics (`train-evaluate`)

Retrains the interpretable model on the client's own reconstructed history and
produces **every reported metric from ONE evaluate run** (no cherry-picking a
good split). This is the deeper intake: it is the shipment-level feature table
produced by reconstructing data-quality state *at ship time* (see the pipeline's
`03_features` step). CSV or XLSX.

### Required

| Canonical | Type | Used for |
|---|---|---|
| `ship_date` | date | Temporal train/test split (earlier → train, later → test; never shuffled — shuffling leaks future chargeback rates). |
| `chargeback` | integer (0/1) | The label the model predicts. |
| one or more feature columns | number/bool | Any numeric/bool column that isn't `order_id`/`ship_date`/`sku`/`chargeback` is treated as a feature (e.g. `gtin14_missing`, `case_dims_missing`, `sku_prior_chargeback_rate`). |

`evaluate_model` reports AUC, precision, recall, n_train, n_test from a single
held-out temporal split — one row in `model_performance.csv`, and every figure in
the deliverable comes from that one row.

## Basis & window (engagement.yml)

Every dollar figure prints its basis and window; these come from config, never
the wall clock:

```yaml
as_of_date: "2026-01-02"                 # analysis anchor; NEVER today's date
basis:
  window_months: 37
  window_label: "Jan 2023 – Jan 2026"    # printed beside annualized figures
  preventability_fractions:              # optional override of the defaults
    data_compliance_error: 0.80
    logistics_overage: 0.70
    # ...
archetype_map:                           # reason_code -> archetype (client-specific)
  "LBL-01": data_compliance_error
  "DIM-07": item_setup_gap
```

Preventability fractions default to the model's documented values; the roadmap's
`prevention_value = historical_loss × preventability_fraction` is always ≤ the loss.

## Run

```bash
pip install -e ../engagement-template/lib
# prevention roadmap from a client chargeback ledger:
python client_mode.py roadmap --config engagement.yml \
    --input client-data/chargebacks.csv --out client-output [--final]
# model metrics from a client feature table (single evaluate run):
python client_mode.py train-evaluate --config engagement.yml \
    --features client-data/training_features.csv --out client-output
```

Outputs to `client-output/` (gitignored): a branded, provenance-footed,
DRAFT-watermarked HTML deliverable + a `summary.json`, or a **Data Readiness
Report** if a required column is missing.
