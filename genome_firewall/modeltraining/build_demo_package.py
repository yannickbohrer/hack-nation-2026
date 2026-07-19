"""
Builds the final demo model package from an already-executed superbugs_model.ipynb
run (SPLIT_VARIANT = "mash_002"). Does not train or re-evaluate anything — reads
model_outputs_final_mash_002/ and repackages a small, demo-usable subset.

Strict research criteria (MIN_BALANCED_ACCURACY etc., set in the notebook) are left
untouched. This script ONLY adds a separate, explicitly-labeled "demo candidate"
tier for hackathon-demo purposes, plus an experimental_demo_only fallback ranking
if literally nothing clears any demo threshold rung.
"""
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
SOURCE_DIR = BASE_DIR / "model_outputs_final_mash_002"
OUTPUT_DIR = BASE_DIR / "model_outputs_demo_mash_002"

# Suggested demo criteria (rung 0 = as given, unrelaxed). Explicitly NOT clinical
# or deployment criteria — see DEMO_CRITERIA_LABEL below and the documentation file.
DEMO_CRITERIA_RUNGS = [
    {"balanced_accuracy": 0.55, "resistant_recall": 0.40, "coverage": 0.20, "called_accuracy": 0.80},
    {"balanced_accuracy": 0.53, "resistant_recall": 0.35, "coverage": 0.15, "called_accuracy": 0.75},
    {"balanced_accuracy": 0.52, "resistant_recall": 0.30, "coverage": 0.10, "called_accuracy": 0.70},
    {"balanced_accuracy": 0.50, "resistant_recall": 0.25, "coverage": 0.05, "called_accuracy": 0.65},
]
DEMO_CRITERIA_LABEL = "demo_candidate — hackathon demo selection only, NOT a clinical or deployment claim"

# Experimental fallback ranking weights (used only if no rung produces any candidate).
# Weighted toward balanced_accuracy and resistant_recall (the two metrics that most
# directly reflect "does this model know anything useful"), PR-AUC as a class-imbalance
# -robust discrimination check, Brier score inverted (lower is better), coverage and
# called_accuracy given the smallest weight since an experimental-tier model's
# calibration/threshold behavior isn't trusted yet. Test sample size is NOT part of
# the weighted score — it is reported alongside as a reliability signal for the human
# reviewer, and used only as the final tie-breaker.
EXPERIMENTAL_RANK_WEIGHTS = {
    "balanced_accuracy": 0.30,
    "resistant_recall": 0.25,
    "pr_auc": 0.20,
    "brier_score_inverted": 0.15,  # (1 - min(brier_score, 1))
    "coverage": 0.05,
    "called_accuracy": 0.05,
}
EXPERIMENTAL_TOP_N = 3


def experimental_rank_score(row: pd.Series) -> float:
    brier = row["brier_score"] if pd.notna(row["brier_score"]) else 1.0
    parts = {
        "balanced_accuracy": row["balanced_accuracy"] if pd.notna(row["balanced_accuracy"]) else 0.0,
        "resistant_recall": row["resistant_recall"] if pd.notna(row["resistant_recall"]) else 0.0,
        "pr_auc": row["pr_auc"] if pd.notna(row["pr_auc"]) else 0.0,
        "brier_score_inverted": 1 - min(brier, 1.0),
        "coverage": row["coverage"] if pd.notna(row["coverage"]) else 0.0,
        "called_accuracy": row["called_accuracy"] if pd.notna(row["called_accuracy"]) else 0.0,
    }
    return float(sum(EXPERIMENTAL_RANK_WEIGHTS[k] * v for k, v in parts.items()))


def meets_rung(row: pd.Series, rung: dict) -> bool:
    both_classes_in_test = row["test_resistant_count"] > 0 and row["test_susceptible_count"] > 0
    return bool(
        row["model_status"] == "calibrated"
        and both_classes_in_test
        and pd.notna(row["balanced_accuracy"]) and row["balanced_accuracy"] >= rung["balanced_accuracy"]
        and pd.notna(row["resistant_recall"]) and row["resistant_recall"] >= rung["resistant_recall"]
        and pd.notna(row["coverage"]) and row["coverage"] >= rung["coverage"]
        and pd.notna(row["called_accuracy"]) and row["called_accuracy"] >= rung["called_accuracy"]
    )


def select_demo_candidates(summary_df: pd.DataFrame):
    for rung_index, rung in enumerate(DEMO_CRITERIA_RUNGS):
        mask = summary_df.apply(lambda r: meets_rung(r, rung), axis=1)
        if mask.any():
            return summary_df[mask].copy(), rung_index, rung, "threshold_rung"
    return pd.DataFrame(), None, None, "none"


def main():
    if not SOURCE_DIR.exists():
        raise FileNotFoundError(f"{SOURCE_DIR} not found — run superbugs_model.ipynb with SPLIT_VARIANT='mash_002' first.")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    summary_df = pd.read_csv(SOURCE_DIR / "metrics" / "final_summary_report.csv")

    # --- strict candidates: unchanged research criteria, straight from the notebook ---
    strict_df = summary_df[summary_df["deployment_candidate"].fillna(False)].copy()
    strict_df.to_csv(OUTPUT_DIR / "strict_candidates.csv", index=False)

    # --- unsupported antibiotics: pass through as-is ---
    unsupported_df = summary_df[summary_df["model_status"] == "unsupported"].copy()
    unsupported_df.to_csv(OUTPUT_DIR / "unsupported_antibiotics.csv", index=False)

    # --- demo candidates: separate, explicitly-labeled tier ---
    demo_df, rung_index, rung_used, selection_mode = select_demo_candidates(summary_df)
    experimental_df = pd.DataFrame()

    if demo_df.empty:
        print("No antibiotic met any demo-criteria rung — falling back to experimental_demo_only ranking.")
        calibrated = summary_df[summary_df["model_status"] == "calibrated"].copy()
        calibrated = calibrated[
            (calibrated["test_resistant_count"] > 0) & (calibrated["test_susceptible_count"] > 0)
        ]
        calibrated["experimental_rank_score"] = calibrated.apply(experimental_rank_score, axis=1)
        experimental_df = calibrated.sort_values(
            ["experimental_rank_score", "n_test"], ascending=[False, False]
        ).head(EXPERIMENTAL_TOP_N).copy()
        experimental_df["model_tier"] = "experimental_demo_only"
        selection_mode = "experimental_ranking_fallback"
    else:
        demo_df["model_tier"] = "demo_candidate"

    demo_df.to_csv(OUTPUT_DIR / "demo_candidates.csv", index=False)
    experimental_df.to_csv(OUTPUT_DIR / "experimental_demo_only.csv", index=False)

    strict_antibiotics = set(strict_df["antibiotic"]) if not strict_df.empty else set()
    demo_antibiotics = set(demo_df["antibiotic"]) if not demo_df.empty else set()
    experimental_antibiotics = set(experimental_df["antibiotic"]) if not experimental_df.empty else set()
    usable_antibiotics = sorted(strict_antibiotics | demo_antibiotics | experimental_antibiotics)

    # --- per_antibiotic_metrics.csv: full metrics table, tagged with tier ---
    tier_map = {a: "strict" for a in strict_antibiotics}
    for a in demo_antibiotics:
        tier_map.setdefault(a, "demo")
    for a in experimental_antibiotics:
        tier_map.setdefault(a, "experimental_demo_only")
    per_antibiotic = summary_df.copy()
    per_antibiotic["model_tier"] = per_antibiotic["antibiotic"].map(tier_map).fillna("not_selected")
    per_antibiotic.to_csv(OUTPUT_DIR / "per_antibiotic_metrics.csv", index=False)

    # --- copy model artifacts, restricted to usable antibiotics only ---
    calibrated_models = joblib.load(SOURCE_DIR / "models" / "calibrated_models.joblib")
    feature_lists = joblib.load(SOURCE_DIR / "features" / "feature_lists.joblib")
    with open(SOURCE_DIR / "thresholds" / "thresholds.json", encoding="utf-8") as f:
        all_thresholds = json.load(f)

    demo_calibrated_models = {a: m for a, m in calibrated_models.items() if a in usable_antibiotics}
    demo_feature_lists = {a: f for a, f in feature_lists.items() if a in usable_antibiotics}
    demo_thresholds = {a: t for a, t in all_thresholds.items() if a in usable_antibiotics}

    joblib.dump(demo_calibrated_models, OUTPUT_DIR / "calibrated_models.joblib")
    with open(OUTPUT_DIR / "feature_columns.json", "w", encoding="utf-8") as f:
        json.dump(demo_feature_lists, f, indent=2, sort_keys=True)
    with open(OUTPUT_DIR / "thresholds.json", "w", encoding="utf-8") as f:
        json.dump(demo_thresholds, f, indent=2, sort_keys=True)

    # --- coefficients, restricted to usable antibiotics ---
    coefficients_df = pd.read_csv(SOURCE_DIR / "explanations" / "calibrated_model_coefficients.csv")
    coefficients_df = coefficients_df[coefficients_df["antibiotic"].isin(usable_antibiotics)]
    coefficients_df.to_csv(OUTPUT_DIR / "model_coefficients.csv", index=False)

    # --- reliability (calibration) plots, restricted to usable antibiotics ---
    reliability_src_dir = SOURCE_DIR / "plots" / "reliability"
    reliability_dst_dir = OUTPUT_DIR / "plots" / "reliability"
    reliability_dst_dir.mkdir(parents=True, exist_ok=True)
    copied_plots = []
    for antibiotic in usable_antibiotics:
        safe_name = antibiotic.replace("/", "_")
        src = reliability_src_dir / f"reliability_{safe_name}.png"
        if src.exists():
            shutil.copy2(src, reliability_dst_dir / src.name)
            copied_plots.append(src.name)
        else:
            print(f"WARNING: no reliability plot found for {antibiotic!r} at {src}")

    # --- per-genetic-cluster metrics, restricted to usable antibiotics ---
    # Per-cluster breakdown fulfills the brief's "report performance broken down by
    # genetically related groups" requirement. Most Mash clusters are singletons or
    # very small (see mash_preprocessed_data/usability_tradeoff_mash_002.md) so most
    # rows here are NOT individually statistically stable — that's why
    # small_group_warning (n_samples < 10) is carried through rather than filtered
    # out silently. Use it to decide whether to trust a given row.
    group_metrics_path = SOURCE_DIR / "metrics" / "per_genetic_group_metrics.csv"
    if group_metrics_path.exists():
        group_metrics_df = pd.read_csv(group_metrics_path)
        group_metrics_df = group_metrics_df[group_metrics_df["antibiotic"].isin(usable_antibiotics)]
        group_metrics_df.to_csv(OUTPUT_DIR / "metrics_by_cluster.csv", index=False)
    else:
        print(f"WARNING: {group_metrics_path} not found — metrics_by_cluster.csv not written.")
        group_metrics_df = pd.DataFrame()

    # --- metadata ---
    metadata = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_run": str(SOURCE_DIR),
        "split_variant": "mash_002",
        "strict_criteria_unchanged": True,
        "demo_criteria_label": DEMO_CRITERIA_LABEL,
        "demo_criteria_rungs": DEMO_CRITERIA_RUNGS,
        "demo_criteria_rung_used_index": rung_index,
        "demo_criteria_rung_used_values": rung_used,
        "demo_selection_mode": selection_mode,
        "experimental_rank_weights": EXPERIMENTAL_RANK_WEIGHTS,
        "experimental_rank_formula": (
            "score = 0.30*balanced_accuracy + 0.25*resistant_recall + 0.20*pr_auc "
            "+ 0.15*(1 - min(brier_score, 1)) + 0.05*coverage + 0.05*called_accuracy; "
            "ties broken by larger n_test. Missing metrics treated as 0 (or brier=1.0, "
            "i.e. worst case) rather than dropped."
        ),
        "n_total_antibiotics": int(len(summary_df)),
        "n_base_models_trained": int((summary_df["model_status"] == "calibrated").sum()),
        "n_calibrated_models": int((summary_df["model_status"] == "calibrated").sum()),
        "n_strict_candidates": int(len(strict_df)),
        "n_demo_candidates": int(len(demo_df)),
        "n_experimental_demo_only": int(len(experimental_df)),
        "usable_antibiotics": usable_antibiotics,
        "excluded_from_model_features": ["genome_id", "antibiotic", "is_resistant", "cluster_id", "split"],
        "supported_species": "Escherichia coli",
        "reliability_plots_copied": copied_plots,
        "metrics_by_cluster_written": bool(not group_metrics_df.empty),
        "safety_warning": (
            "Research prototype. Every prediction must be confirmed with standard "
            "laboratory susceptibility testing."
        ),
    }
    with open(OUTPUT_DIR / "metadata.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    print("\n=== Demo package build complete ===")
    print(f"Output: {OUTPUT_DIR}")
    print(f"Strict candidates: {len(strict_df)} -> {strict_df['antibiotic'].tolist()}")
    print(f"Demo candidates (rung {rung_index}, mode={selection_mode}): {len(demo_df)} -> {demo_df['antibiotic'].tolist() if not demo_df.empty else []}")
    print(f"Experimental demo-only fallback: {len(experimental_df)} -> {experimental_df['antibiotic'].tolist() if not experimental_df.empty else []}")
    print(f"Total usable antibiotics packaged: {len(usable_antibiotics)}")


if __name__ == "__main__":
    main()
