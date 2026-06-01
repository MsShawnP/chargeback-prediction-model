---
title: "Synthetic Training Labels for Lailara Portfolio ML Models Without Real Causal Signal"
date: "2026-06-01"
category: "docs/solutions/architecture-patterns"
module: "pipeline/model"
problem_type: architecture_pattern
component: development_workflow
severity: high
root_cause: incomplete_setup
resolution_type: code_fix
applies_when:
  - "Portfolio project trains an ML model on a synthetic database (e.g., Cinderhaven Data Platform) where outcome records were generated independently of feature records"
  - "Baseline model achieves AUC at or below 0.55 despite a healthy join rate (above 85%), indicating absent rather than weak signal"
  - "Deliverable requires a demonstrable, interpretable model on a database not designed around a prediction task"
symptoms:
  - "Model trains without error but achieves AUC near 0.50 — no better than random baseline"
  - "SHAP values are near-zero or uniformly distributed across all features"
  - "Precision and recall are both low regardless of threshold or hyperparameter tuning"
  - "Feature importances are roughly equal across all features"
tags:
  - synthetic-data
  - ml-pipeline
  - training-labels
  - auc
  - cinderhaven
  - portfolio
  - gradient-boosting
  - shap
---

# Synthetic Training Labels for Lailara Portfolio ML Models Without Real Causal Signal

## Context

Synthetic portfolio databases do not embed causal relationships between upstream conditions and downstream outcomes by default. Cinderhaven Provisions, the reference database used across Lailara LLC portfolio projects, generates chargebacks independently of data quality features. When a RandomForestClassifier was trained on raw Cinderhaven features — missing GTIN-14, missing UPC, missing case dimensions, late ASN submissions — the model achieved AUC=0.50, indistinguishable from random guessing.

The investigation confirmed this was not a data pipeline problem. The chargeback-to-shipment join rate was 96.5%, ruling out join failures. Feature distributions were healthy. The issue was structural: the synthetic Postgres data has no causal path from quality defects to chargebacks. The two tables were generated independently.

This is a known artifact of synthetic portfolio databases. It will recur on any future Lailara project that trains an ML model on Cinderhaven or a similarly constructed synthetic source.

## Guidance

### Step 1: Verify causal signal before investing in feature engineering

Before building feature pipelines, run a baseline model on whatever features you have. If AUC is at or below 0.55 with a simple model (RandomForest, logistic regression), stop. The signal is absent, not weak. Weak signal improves with feature engineering. Absent signal does not.

```python
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
rf = RandomForestClassifier(n_estimators=100, random_state=42)
rf.fit(X_train, y_train)
auc = roc_auc_score(y_test, rf.predict_proba(X_test)[:, 1])
print(f"Baseline AUC: {auc:.4f}")
# If this prints 0.50xx, the database has no causal signal. Proceed to Step 2.
```

### Step 2: Diagnose the source of the zero-signal result

Check the join rate between your outcome table and your feature table. A low join rate (below 85%) means missing records, not absent causality — fix the join first.

```python
join_rate = merged_df.shape[0] / chargebacks_df.shape[0]
print(f"Join rate: {join_rate:.1%}")
# 96.5% or higher → join is not the problem
```

If the join rate is healthy and AUC is still 0.50, the database does not embed the causal relationship the model is meant to demonstrate.

### Step 3: Build a synthetic label generator — do not modify raw data

Lailara portfolio projects treat Cinderhaven Postgres as read-only. Inserting rows or altering existing data is out of scope regardless of the investigation result. The consistent solution is a separate script that reads raw features, computes a deterministic chargeback probability based on the causal model the deliverable is meant to demonstrate, and writes synthetic training labels to the project's output directory.

The script (`scripts/generate_training_data.py`) follows this structure:

```python
import pandas as pd
import numpy as np

SEED = 42       # Fixed seed — pipeline runs must be reproducible
BASE_RATE = 0.014  # ~1.4% base chargeback rate per shipment

# Read raw Cinderhaven features — read-only, no writes back
df = pd.read_parquet("output/frames/training_features.parquet")

# Multiplicative probability model: each defect multiplies base risk.
# ASN compliance is the PRIMARY driver (time-stable, ~8.6% rate throughout).
# Data quality flags are SECONDARY (strong in training window, sparse in test).
p = np.full(len(df), BASE_RATE)
p *= np.where(df["asn_sent_late"].astype(bool),        9.0, 1.0)  # PRIMARY
p *= np.where(df["gtin14_missing"].astype(bool),        4.0, 1.0)  # SECONDARY
p *= np.where(df["upc_missing"].astype(bool),           2.5, 1.0)
p *= np.where(df["case_dims_missing"].astype(bool),     2.0, 1.0)
p *= np.where(df["case_weight_missing"].astype(bool),   1.8, 1.0)
p = np.minimum(p, 0.85)  # cap probability — no shipment exceeds 85% risk

# Sample binary labels from the probability distribution
rng = np.random.default_rng(SEED)
df["chargeback"] = (rng.random(len(df)) < p).astype(int)

# Write to project output only — never back to Cinderhaven
df.to_parquet("output/frames/training_features_synthetic.parquet", index=False)
```

Key design choices:

- `SEED=42` is fixed. Every pipeline run produces identical labels. This is a reproducibility requirement, not a convention.
- The model is multiplicative, not additive. Each defect multiplies the base risk rather than adding to it, which better reflects how compliance failures compound. Adjust multipliers to match the causal story for the specific deliverable, but document any changes in DECISIONS.md.
- The 0.85 cap prevents implausibly certain predictions on worst-case rows. Natural variability comes from the multiplicative structure, not injected noise.
- The output path is always within the project's `output/` directory. The Cinderhaven schema is never touched.

### Step 4: Switch from RandomForest to GradientBoosting for small datasets

On datasets under roughly 5,000 rows, GradientBoosting is better calibrated than RandomForest. RandomForest overfits early on small samples; GradientBoosting's sequential correction handles the small-sample regime better.

```python
from sklearn.ensemble import GradientBoostingClassifier

model = GradientBoostingClassifier(
    n_estimators=100,
    learning_rate=0.1,
    max_depth=3,
    random_state=42
)
model.fit(X_train, y_train)
```

### Step 5: Document the synthetic label decision immediately

Write to DECISIONS.md before the session ends. Future sessions will encounter the same zero-signal result if they read the raw database without this context. The entry should state: what the problem was, why synthetic labels were created, which script generates them, and that raw Cinderhaven data is unchanged.

## Why This Matters

A model with AUC=0.50 cannot be presented as a predictive deliverable. It produces no business value and demonstrates nothing about the practice's core capability. The alternative — modifying the source database to embed false causal relationships — undermines the integrity of every other project that relies on Cinderhaven as a shared reference dataset.

The synthetic label approach resolves both problems. It produces a model that demonstrates real predictive structure (AUC=0.7485 in the Cinderhaven implementation, precision=0.28, recall=0.39 at default threshold) while leaving the source data unchanged. The causal model embedded in the label generator is the same causal model the deliverable is designed to explain: upstream data quality defects drive downstream chargeback costs.

The result is not a deception. The labels are synthetic and documented as such. The model demonstrates what a correctly structured dataset would look like and how the predictive architecture would behave against it. This is the honest framing for a portfolio piece built on a synthetic database.

## When to Apply

Apply this pattern when all three conditions hold:

1. The project trains an ML model on Cinderhaven Provisions or another synthetic Lailara portfolio database.
2. A baseline model achieves AUC at or below 0.55, and the outcome-to-feature join rate is above 85%.
3. The deliverable is a portfolio piece meant to demonstrate a causal relationship that the raw database does not embed.

Do not apply this pattern to production data. If a client database returns AUC=0.50, that is a data quality or feature engineering problem to diagnose — not a signal to generate synthetic labels over real outcomes.

Do not apply this pattern when the zero-signal result might reflect a genuine null finding (i.e., the proposed causal relationship may not exist). In that case, the finding itself is the deliverable.

## Examples

### Before: Raw Cinderhaven features, RandomForest, AUC=0.50

```
Training set: 3,200 rows
Test set: 800 rows
Baseline AUC: 0.4998

Feature importances:
  asn_sent_late        0.21
  gtin14_missing       0.19
  upc_missing          0.20
  case_dims_missing    0.22
  case_weight_missing  0.18

# Near-equal importances with AUC=0.50 is the signature of absent signal.
# The model learned nothing — it is partitioning random noise.
```

### After: Synthetic labels via generate_training_data.py, GradientBoosting, AUC=0.7485

```
Training set: 3,200 rows (synthetic labels)
Test set: 800 rows (synthetic labels)
AUC: 0.7485
Precision: 0.28
Recall: 0.39

Feature importances (SHAP-consistent ordering):
  asn_sent_late        0.44   ← dominant driver, matches multiplier structure
  gtin14_missing       0.21
  upc_missing          0.19
  case_dims_missing    0.11
  case_weight_missing  0.05
```

The feature importance ordering after synthetic label training matches the multiplier structure in `generate_training_data.py`. This is the expected result: the model learned the causal story embedded in the labels. If importances diverge significantly from multipliers, check for multicollinearity in the raw features or a bug in the label generation logic.

### Architectural constraints that still apply

The Lailara architectural locks from DECISIONS.md remain in effect even when synthetic labels are used:

- **Interpretable model required.** GradientBoosting with SHAP attribution is compliant. A neural network or any black-box model is not, regardless of AUC improvement.
- **Point-in-time join required.** Feature values must reflect what was known at shipment time, not retrospective data. The `generate_training_data.py` script reads from the already-constructed feature frame, which enforces this constraint upstream.

## Related

- `DECISIONS.md` — contains the durable record of the synthetic label decision and the read-only Cinderhaven constraint
- `FAILURES.md` — contains the zero-signal diagnosis and the intermediate failed attempt (quality flags as primary driver, AUC=0.62 before weight rebalancing)
- `scripts/generate_training_data.py` — the label generator for this project
