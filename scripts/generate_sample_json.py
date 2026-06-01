#!/usr/bin/env python3
"""Generate sample JSON data for the React app.

Used when the pipeline hasn't been run against Cinderhaven (requires flyctl proxy).
Produces internally consistent risk_ledger.json, simulator.json, and summary.json
that match the schema expected by the React app.

Run from the project root:
    python scripts/generate_sample_json.py
"""
import json
import random
from pathlib import Path

SEED = 42
random.seed(SEED)

OUTPUT_DIR = Path("frontend/public/json")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

RETAILERS = ["WMT", "TGT", "KGR", "ALB", "ACM"]

SKUS = (
    [f"CHP-AS-{i:03d}" for i in range(1, 21)]   # Ambient Shelf (20)
    + [f"CHP-RF-{i:03d}" for i in range(1, 16)] # Refrigerated (15)
    + [f"CHP-FZ-{i:03d}" for i in range(1, 16)] # Frozen (15)
)

SHAP_FEATURES = [
    "gtin14_missing",
    "case_dims_missing",
    "case_weight_missing",
    "upc_missing",
    "data_quality_score",
    "asn_sent_late",
    "days_late",
    "all_labels_scannable",
    "sku_prior_chargeback_rate",
]

FEATURE_LABELS = {
    "case_dims_missing": "Missing case dimensions",
    "gtin14_missing": "Missing GTIN-14 barcode",
    "upc_missing": "Missing UPC",
    "case_weight_missing": "Missing case weight",
    "asn_sent_late": "Late ASN filing",
    "sku_prior_chargeback_rate": "High historical chargeback rate",
    "data_quality_score": "Poor data quality score",
}

ARCHETYPE_LABELS = {
    "case_dims_missing": "logistics audit",
    "case_weight_missing": "logistics audit",
    "gtin14_missing": "data compliance",
    "upc_missing": "data compliance",
    "asn_sent_late": "ASN timing",
    "sku_prior_chargeback_rate": "item setup",
    "data_quality_score": "data compliance",
}

# Ship dates: upcoming POs Jan–Mar 2027
SHIP_DATES = (
    [f"2027-01-{d:02d}" for d in range(15, 32)]
    + [f"2027-02-{d:02d}" for d in range(1, 29)]
    + [f"2027-03-{d:02d}" for d in range(1, 16)]
)

BASE_RATE = 0.12  # unconditional chargeback probability


def make_shap_values(prob: float, missing_bool_features: list[str], asn_late: bool) -> dict[str, float]:
    """Compute SHAP values that sum to approximately (prob - BASE_RATE)."""
    shap: dict[str, float] = {}
    total_to_allocate = max(0.0, prob - BASE_RATE)

    # Assign largest share to missing boolean features; rest get small values
    bool_feats = ["gtin14_missing", "case_dims_missing", "case_weight_missing", "upc_missing"]
    if missing_bool_features:
        per_feat = total_to_allocate * 0.75 / len(missing_bool_features)
        for feat in missing_bool_features:
            shap[feat] = round(per_feat + random.uniform(-0.01, 0.015), 6)
    for feat in bool_feats:
        if feat not in shap:
            shap[feat] = round(random.uniform(-0.01, 0.02), 6)

    # data_quality_score: count of missing bool features × small weight
    shap["data_quality_score"] = round(len(missing_bool_features) * 0.03 + random.uniform(0, 0.015), 6)

    # asn_sent_late
    shap["asn_sent_late"] = round(0.07 + random.uniform(-0.01, 0.015) if asn_late else random.uniform(-0.005, 0.012), 6)

    # days_late: small positive contribution
    shap["days_late"] = round(random.uniform(0.005, 0.025), 6)

    # all_labels_scannable: always negative (reduces risk)
    shap["all_labels_scannable"] = round(random.uniform(-0.07, -0.02), 6)

    # sku_prior_chargeback_rate: spreads remaining allocation
    allocated = sum(v for v in shap.values() if v > 0)
    remaining = max(0.0, total_to_allocate * 0.85 - allocated)
    shap["sku_prior_chargeback_rate"] = round(remaining + random.uniform(0.005, 0.02), 6)

    return shap


def make_attribution(shap: dict[str, float], prob: float) -> str:
    """Pick top positive SHAP feature; build attribution string."""
    pos = {k: v for k, v in shap.items() if v > 0.05 and k in FEATURE_LABELS}
    if pos:
        top = max(pos, key=lambda k: pos[k])
    else:
        top = "sku_prior_chargeback_rate"
    label = FEATURE_LABELS[top]
    archetype = ARCHETYPE_LABELS[top]
    return f"{label} → {archetype} → {prob:.0%} probability within 14 days"


def make_row(
    sku: str,
    retailer: str,
    ship_date: str,
    prob: float,
    tier: str,
    missing_bool_features: list[str],
    asn_late: bool,
    order_value: int,
) -> tuple[dict, dict]:
    shap = make_shap_values(prob, missing_bool_features, asn_late)
    attribution = make_attribution(shap, prob)
    dollar_exposure = round(order_value * prob, 2)

    base = {
        "sku": sku,
        "retailer": retailer,
        "ship_date": ship_date,
        "probability": round(prob, 4),
        "dollar_exposure": dollar_exposure,
        "attribution_string": attribution,
        "risk_tier": tier,
    }
    return base, shap


SCENARIO_CONFIGS = [
    # HIGH risk — multiple data quality flags missing
    {"tier": "HIGH", "prob_range": (0.62, 0.85), "missing": ["case_dims_missing", "gtin14_missing"], "asn_rate": 0.40, "n": 6},
    {"tier": "HIGH", "prob_range": (0.52, 0.75), "missing": ["case_dims_missing", "case_weight_missing"], "asn_rate": 0.30, "n": 5},
    {"tier": "HIGH", "prob_range": (0.55, 0.70), "missing": ["gtin14_missing", "upc_missing", "case_dims_missing"], "asn_rate": 0.50, "n": 5},
    # MEDIUM risk — one major flag missing or late ASN
    {"tier": "MEDIUM", "prob_range": (0.30, 0.49), "missing": ["case_dims_missing"], "asn_rate": 0.20, "n": 6},
    {"tier": "MEDIUM", "prob_range": (0.22, 0.45), "missing": ["gtin14_missing"], "asn_rate": 0.15, "n": 5},
    {"tier": "MEDIUM", "prob_range": (0.25, 0.48), "missing": ["case_weight_missing"], "asn_rate": 0.25, "n": 5},
    {"tier": "MEDIUM", "prob_range": (0.20, 0.40), "missing": [], "asn_rate": 0.80, "n": 4},
    # LOW risk — all flags present, on-time ASN
    {"tier": "LOW", "prob_range": (0.06, 0.19), "missing": [], "asn_rate": 0.05, "n": 9},
]

ledger: list[dict] = []
simulator: list[dict] = []

for cfg in SCENARIO_CONFIGS:
    for _ in range(cfg["n"]):
        sku = random.choice(SKUS)
        retailer = random.choice(RETAILERS)
        ship_date = random.choice(SHIP_DATES)
        prob = round(random.uniform(*cfg["prob_range"]), 4)
        asn_late = random.random() < cfg["asn_rate"]
        order_value = random.randint(800, 12_000)

        base, shap = make_row(sku, retailer, ship_date, prob, cfg["tier"], cfg["missing"], asn_late, order_value)
        ledger.append(base)
        simulator.append({**base, "shap_values": shap})

# Sort both by dollar_exposure descending (matches pipeline output)
ledger.sort(key=lambda r: r["dollar_exposure"], reverse=True)
simulator.sort(key=lambda r: r["dollar_exposure"], reverse=True)

# Write JSON — summary.json is written by 07_export from real pipeline data; skip it here.
(OUTPUT_DIR / "risk_ledger.json").write_text(
    json.dumps(ledger, indent=2), encoding="utf-8"
)
(OUTPUT_DIR / "simulator.json").write_text(
    json.dumps(simulator, indent=2), encoding="utf-8"
)

tier_counts = {t: sum(1 for r in ledger if r["risk_tier"] == t) for t in ("HIGH", "MEDIUM", "LOW")}
total_exposure = sum(r["dollar_exposure"] for r in ledger)

print(f"Generated {len(ledger)} rows -> frontend/public/json/")
print(f"  Risk tiers: HIGH={tier_counts['HIGH']}, MEDIUM={tier_counts['MEDIUM']}, LOW={tier_counts['LOW']}")
print(f"  Total forward exposure: ${total_exposure:,.0f}")
print("  (summary.json written by pipeline 07_export — not overwritten)")
