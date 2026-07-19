"""
Module 02: Train & Export for Production
========================================
Trains per-antibiotic logistic regression models from the existing data splits,
computes evaluation metrics, calibration thresholds, and serializes everything
needed by the backend prediction service.

Output structure (in --output-dir):
  models/
    manifest.json               ← registry of all trained models
    ampicillin/
      model.joblib              ← trained LogisticRegression
      metadata.json             ← features, metrics, thresholds
    ciprofloxacin/
      ...

Usage:
  python train_and_export.py
  python train_and_export.py --splits-dir ../pipeline-02_outputs/splits --output-dir ./exported_models
"""

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import joblib
from sklearn.linear_model import LogisticRegression
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import (
    roc_auc_score,
    precision_recall_curve,
    auc as sk_auc,
    brier_score_loss,
    balanced_accuracy_score,
    f1_score,
    recall_score,
    precision_score,
    confusion_matrix,
)


# ── Thresholds for the "no-call" zone ──────────────────────────────
# Predictions with probabilities inside [lo, hi] are uncertain → no-call
DEFAULT_NOCALL_LO = 0.35
DEFAULT_NOCALL_HI = 0.65


def _feature_cols(df: pd.DataFrame) -> list[str]:
    """Return all binary AMR feature columns (gene_* and mut_*)."""
    return sorted(
        c for c in df.columns
        if c.startswith("gene_") or c.startswith("point_") or c.startswith("mut_")
    )


def _compute_metrics(y_true, y_pred, y_prob) -> dict:
    """Compute the full metric suite required by the challenge."""
    metrics = {}
    unique = np.unique(y_true)

    metrics["n_samples"] = int(len(y_true))
    metrics["n_resistant"] = int(np.sum(y_true == 1))
    metrics["n_susceptible"] = int(np.sum(y_true == 0))
    metrics["balanced_accuracy"] = float(balanced_accuracy_score(y_true, y_pred))
    metrics["f1"] = float(f1_score(y_true, y_pred, zero_division=0))
    metrics["precision"] = float(precision_score(y_true, y_pred, zero_division=0))
    metrics["recall_resistant"] = float(recall_score(y_true, y_pred, pos_label=1, zero_division=0))
    metrics["recall_susceptible"] = float(recall_score(y_true, y_pred, pos_label=0, zero_division=0))
    metrics["brier_score"] = float(brier_score_loss(y_true, y_prob))

    if len(unique) > 1:
        metrics["auroc"] = float(roc_auc_score(y_true, y_prob))
        prec_curve, rec_curve, _ = precision_recall_curve(y_true, y_prob)
        metrics["pr_auc"] = float(sk_auc(rec_curve, prec_curve))
    else:
        metrics["auroc"] = None
        metrics["pr_auc"] = None

    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    metrics["confusion_matrix"] = {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)}

    return metrics


def _top_features(model, feature_cols: list[str], n: int = 10) -> dict:
    """Extract the top positive and negative coefficient features."""
    coefs = model.coef_[0]
    feat_df = pd.DataFrame({"feature": feature_cols, "weight": coefs})
    feat_df = feat_df.sort_values("weight", ascending=False)

    top_resistance = feat_df.head(n).to_dict(orient="records")
    top_susceptibility = feat_df.tail(n).to_dict(orient="records")

    return {
        "top_resistance_drivers": top_resistance,
        "top_susceptibility_drivers": top_susceptibility,
    }


def train_single_antibiotic(
    train_df: pd.DataFrame,
    calib_df: pd.DataFrame,
    test_df: pd.DataFrame,
    antibiotic: str,
    feature_cols: list[str],
    output_dir: Path,
    nocall_lo: float = DEFAULT_NOCALL_LO,
    nocall_hi: float = DEFAULT_NOCALL_HI,
) -> dict | None:
    """Train, calibrate, evaluate, and export a model for one antibiotic."""
    train_sub = train_df[train_df["antibiotic"] == antibiotic].copy()
    calib_sub = calib_df[calib_df["antibiotic"] == antibiotic].copy()
    test_sub = test_df[test_df["antibiotic"] == antibiotic].copy()

    if len(train_sub) < 10:
        print(f"  ⚠ Skipping {antibiotic} — only {len(train_sub)} training samples")
        return None

    X_train = train_sub[feature_cols].fillna(0).values
    y_train = train_sub["is_resistant"].astype(int).values
    X_test = test_sub[feature_cols].fillna(0).values
    y_test = test_sub["is_resistant"].astype(int).values

    # Only keep features that appear in training data
    # (avoids degenerate zero-variance columns)
    active_mask = X_train.sum(axis=0) > 0
    active_features = [f for f, m in zip(feature_cols, active_mask) if m]

    X_train_active = X_train[:, active_mask]
    X_test_active = X_test[:, active_mask]

    # ── Train base model ───────────────────────────────────────────
    base_model = LogisticRegression(
        penalty="l2",
        C=1.0,
        class_weight="balanced",
        solver="liblinear",
        max_iter=1000,
        random_state=42,
    )
    base_model.fit(X_train_active, y_train)

    # ── Calibrate using calibration split (Platt scaling) ──────────
    if len(calib_sub) >= 5 and len(np.unique(calib_sub["is_resistant"])) > 1:
        X_calib = calib_sub[feature_cols].fillna(0).values[:, active_mask]
        y_calib = calib_sub["is_resistant"].astype(int).values

        calibrated_model = CalibratedClassifierCV(
            estimator=base_model,
            method="sigmoid",
            cv="prefit",
        )
        calibrated_model.fit(X_calib, y_calib)
        final_model = calibrated_model
        is_calibrated = True
    else:
        final_model = base_model
        is_calibrated = False

    # ── Evaluate on test split ─────────────────────────────────────
    y_prob = final_model.predict_proba(X_test_active)[:, 1]
    y_pred = (y_prob >= 0.5).astype(int)

    metrics = _compute_metrics(y_test, y_pred, y_prob)

    # No-call metrics: how many fall in the uncertain zone?
    nocall_mask = (y_prob >= nocall_lo) & (y_prob <= nocall_hi)
    call_mask = ~nocall_mask
    metrics["nocall_rate"] = float(nocall_mask.mean()) if len(nocall_mask) > 0 else 0.0
    if call_mask.sum() > 0:
        metrics["accuracy_when_called"] = float(
            (y_pred[call_mask] == y_test[call_mask]).mean()
        )
    else:
        metrics["accuracy_when_called"] = None

    # Feature importance (from uncalibrated base model for interpretability)
    importances = _top_features(base_model, active_features, n=10)

    # ── Serialize ──────────────────────────────────────────────────
    abx_dir = output_dir / antibiotic.replace(" ", "_").lower()
    abx_dir.mkdir(parents=True, exist_ok=True)

    model_path = abx_dir / "model.joblib"
    joblib.dump(final_model, model_path)

    metadata = {
        "antibiotic": antibiotic,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "is_calibrated": is_calibrated,
        "all_feature_cols": feature_cols,
        "active_feature_cols": active_features,
        "active_feature_mask": active_mask.tolist(),
        "nocall_thresholds": {"lo": nocall_lo, "hi": nocall_hi},
        "train_samples": int(len(train_sub)),
        "calib_samples": int(len(calib_sub)),
        "test_samples": int(len(test_sub)),
        "test_metrics": metrics,
        "feature_importances": importances,
    }

    meta_path = abx_dir / "metadata.json"
    with open(meta_path, "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"  ✓ {antibiotic:20s} | bal_acc={metrics['balanced_accuracy']:.3f} "
          f"| auroc={metrics.get('auroc', 'N/A')} "
          f"| brier={metrics['brier_score']:.3f} "
          f"| nocall={metrics['nocall_rate']:.1%} "
          f"| cal={'yes' if is_calibrated else 'no'}")

    return metadata


def main():
    parser = argparse.ArgumentParser(description="Train & export AMR prediction models for production")
    parser.add_argument(
        "--splits-dir",
        type=str,
        default=str(Path(__file__).resolve().parent.parent / "pipeline-02_outputs" / "splits"),
        help="Directory containing train.csv, calibration.csv, hidden_test.csv",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=str(Path(__file__).resolve().parent.parent.parent / "backend" / "models"),
        help="Output directory for exported models (default: backend/models/)",
    )
    parser.add_argument(
        "--antibiotics",
        nargs="+",
        default=["ampicillin", "ciprofloxacin", "meropenem", "tetracycline", "gentamicin"],
        help="List of antibiotics to train models for",
    )
    parser.add_argument("--nocall-lo", type=float, default=DEFAULT_NOCALL_LO)
    parser.add_argument("--nocall-hi", type=float, default=DEFAULT_NOCALL_HI)

    args = parser.parse_args()
    splits_dir = Path(args.splits_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("GENOME FIREWALL — Model Training & Export")
    print("=" * 60)

    # Load splits
    print(f"\nLoading splits from {splits_dir} ...")
    train_df = pd.read_csv(splits_dir / "train.csv")
    calib_df = pd.read_csv(splits_dir / "calibration.csv")
    test_df = pd.read_csv(splits_dir / "hidden_test.csv")
    print(f"  Train: {len(train_df)} rows | Calib: {len(calib_df)} rows | Test: {len(test_df)} rows")

    # Determine feature columns (union across all splits)
    feature_cols = _feature_cols(train_df)
    print(f"  Features: {len(feature_cols)} binary AMR columns\n")

    # Train per-antibiotic models
    manifest = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "feature_cols": feature_cols,
        "models": {},
    }

    for abx in args.antibiotics:
        meta = train_single_antibiotic(
            train_df, calib_df, test_df,
            antibiotic=abx,
            feature_cols=feature_cols,
            output_dir=output_dir,
            nocall_lo=args.nocall_lo,
            nocall_hi=args.nocall_hi,
        )
        if meta is not None:
            manifest["models"][abx] = {
                "model_path": f"{abx.replace(' ', '_').lower()}/model.joblib",
                "metadata_path": f"{abx.replace(' ', '_').lower()}/metadata.json",
                "test_balanced_accuracy": meta["test_metrics"]["balanced_accuracy"],
                "test_auroc": meta["test_metrics"].get("auroc"),
            }

    # Write manifest
    manifest_path = output_dir / "manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"\n{'=' * 60}")
    print(f"✓ Exported {len(manifest['models'])} models to {output_dir}")
    print(f"  Manifest: {manifest_path}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
