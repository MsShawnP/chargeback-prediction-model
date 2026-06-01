"""
Pipeline step 4: model training + SHAP attribution (Move 3).

Reads training_features.parquet (produced by 03_features.py), trains the model,
evaluates on the held-out temporal split, and writes:
  output/model/chargeback_model.joblib
  output/frames/shap_values.parquet
  output/frames/attribution_strings.parquet
  output/frames/model_performance.csv

All model logic lives in src/pipeline/model.py (importable module).
This file is the pipeline runner only.
"""

import logging
import sys
from pathlib import Path

import joblib
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.pipeline.model import (  # noqa: E402
    AUC_GATE,
    build_attribution_strings,
    compute_shap_values,
    evaluate_model,
    get_feature_columns,
    temporal_split,
    train_model,
)

logger = logging.getLogger(__name__)

FRAMES_DIR = Path("output/frames")
MODEL_DIR = Path("output/model")


def run(frames_dir: Path = FRAMES_DIR, model_dir: Path = MODEL_DIR) -> None:
    """Train model, compute SHAP, write all output artifacts.

    Prefers training_features_synthetic.parquet when present — the synthetic
    file has chargeback labels generated from the quality/compliance causal
    model (see scripts/generate_training_data.py).  Falls back to the real
    Cinderhaven training features, which have no embedded signal and will not
    meet the AUC gate.
    """
    synthetic_path = frames_dir / "training_features_synthetic.parquet"
    real_path = frames_dir / "training_features.parquet"

    if synthetic_path.exists():
        training_path = synthetic_path
        logger.info("Using synthetic training data: %s", synthetic_path)
    else:
        training_path = real_path
        logger.warning(
            "Synthetic training data not found at %s — "
            "falling back to real data (AUC gate will likely not be met). "
            "Run scripts/generate_training_data.py first.",
            synthetic_path,
        )

    df = pd.read_parquet(training_path)

    train_df, test_df = temporal_split(df)
    feature_cols = get_feature_columns(df)

    X_train = train_df[feature_cols]
    y_train = train_df["chargeback"]
    X_test = test_df[feature_cols]
    y_test = test_df["chargeback"]

    model = train_model(X_train, y_train)

    metrics = evaluate_model(model, X_test, y_test, n_train=len(X_train))
    if metrics["auc"] < AUC_GATE:
        raise RuntimeError(
            f"AUC {metrics['auc']:.4f} is below the {AUC_GATE:.2f} gate. "
            "Investigate model before generating deliverables. "
            "Consider: feature engineering improvements, GradientBoosting upgrade, "
            "or per-SKU-retailer target reframe."
        )

    X_all = df[feature_cols]
    shap_df = compute_shap_values(model, X_all)

    proba_all = pd.Series(
        model.predict_proba(X_all.astype(float))[:, 1],
        index=X_all.index,
        name="chargeback_probability",
    )
    attr_series = build_attribution_strings(proba_all, shap_df)

    frames_dir.mkdir(parents=True, exist_ok=True)
    model_dir.mkdir(parents=True, exist_ok=True)

    shap_df.to_parquet(frames_dir / "shap_values.parquet", index=False)

    attr_df = df[["order_id", "sku", "ship_date"]].copy()
    attr_df["chargeback_probability"] = proba_all.values
    attr_df["attribution"] = attr_series.values
    attr_df.to_parquet(frames_dir / "attribution_strings.parquet", index=False)

    pd.DataFrame([metrics]).to_csv(frames_dir / "model_performance.csv", index=False)

    joblib.dump(model, model_dir / "chargeback_model.joblib")
    logger.info(
        "All artifacts saved. AUC=%.4f  n_train=%d  n_test=%d",
        metrics["auc"], metrics["n_train"], metrics["n_test"],
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    run()
