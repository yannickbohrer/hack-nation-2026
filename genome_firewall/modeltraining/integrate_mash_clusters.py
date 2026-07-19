"""
Integrates Mash whole-genome cluster assignments into the modeltraining pipeline.

Input:
  mash_preprocessed_data/mash_cluster_002.csv   (genome_id, cluster_id) — Mash distance <= 0.02
  processed_data/final_training_dataset.csv     (genome_id, antibiotic, is_resistant, <277 features>)

Does NOT touch AMRFinderPlus output or the feature matrix — only maps existing genome_id
values onto a cluster_id and re-splits by cluster.

Steps (see module docstring sections below): validate mapping -> join -> diagnostics ->
trade-off notes -> cluster-level train/calibration/hidden_test split -> integrity checks.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

RANDOM_SEED = 42
TRAIN_FRACTION = 0.60
CALIBRATION_FRACTION = 0.20
# hidden_test gets the remainder (~0.20)

BASE_DIR = Path(__file__).resolve().parent
FINAL_DATASET_PATH = BASE_DIR / "processed_data" / "final_training_dataset.csv"
MASH_DIR = BASE_DIR / "mash_preprocessed_data"

# threshold_label -> mash cluster CSV. Only the 0.02 file exists on disk right now;
# if a 0.05 file is added later (e.g. mash_cluster_005.csv) it will be picked up
# automatically by MASH_THRESHOLDS below without code changes.
MASH_THRESHOLDS = {}
for candidate in MASH_DIR.glob("mash_cluster_*.csv"):
    label = candidate.stem.replace("mash_cluster_", "mash_")  # mash_cluster_002.csv -> mash_002
    MASH_THRESHOLDS[label] = candidate


def load_final_dataset() -> pd.DataFrame:
    df = pd.read_csv(FINAL_DATASET_PATH, dtype={"genome_id": str})
    df["genome_id"] = df["genome_id"].astype(str).str.strip()
    return df


def load_mash_mapping(path: Path) -> pd.DataFrame:
    mapping = pd.read_csv(path, dtype=str)
    assert set(mapping.columns) >= {"genome_id", "cluster_id"}, (
        f"{path.name}: expected columns genome_id, cluster_id — found {mapping.columns.tolist()}"
    )
    mapping["genome_id"] = mapping["genome_id"].astype(str).str.strip()
    mapping["cluster_id"] = mapping["cluster_id"].astype(str).str.strip()
    return mapping[["genome_id", "cluster_id"]]


# ---------------------------------------------------------------------------
# Step 2: validate the mapping
# ---------------------------------------------------------------------------
def validate_mapping(final_df: pd.DataFrame, mapping: pd.DataFrame, label: str) -> dict:
    final_ids = set(final_df["genome_id"].unique())
    mash_ids = set(mapping["genome_id"].unique())

    duplicated = mapping[mapping["genome_id"].duplicated(keep=False)].sort_values("genome_id")
    if not duplicated.empty:
        conflicting = duplicated.groupby("genome_id")["cluster_id"].nunique()
        conflicting = conflicting[conflicting > 1]
        if not conflicting.empty:
            raise ValueError(
                f"[{label}] {len(conflicting)} genome_id map to MORE THAN ONE cluster_id: "
                f"{conflicting.index.tolist()[:10]}"
            )

    matched = final_ids & mash_ids
    unmatched_final = sorted(final_ids - mash_ids)
    extraneous_mash = sorted(mash_ids - final_ids)

    report = {
        "threshold_label": label,
        "mash_file": str(MASH_THRESHOLDS[label]),
        "n_unique_genomes_final_dataset": len(final_ids),
        "n_unique_genomes_mash_mapping": len(mash_ids),
        "n_matched": len(matched),
        "pct_matched": round(100 * len(matched) / len(final_ids), 4),
        "n_unmatched_final_dataset_genomes": len(unmatched_final),
        "unmatched_final_dataset_genomes": unmatched_final,
        "n_extraneous_mash_genomes": len(extraneous_mash),
        "extraneous_mash_genomes_sample": extraneous_mash[:50],
        "n_duplicated_or_conflicting_genome_id_rows": int(mapping["genome_id"].duplicated().sum()),
    }

    if unmatched_final:
        print(
            f"WARNING [{label}]: {len(unmatched_final)} genomes in final_training_dataset.csv "
            f"have NO Mash cluster assignment. These genomes cannot be placed by a cluster-based "
            f"split and will be dropped from the mash-based splits for this threshold."
        )

    return report


# ---------------------------------------------------------------------------
# Step 3: join
# ---------------------------------------------------------------------------
def join_clusters(final_df: pd.DataFrame, mapping: pd.DataFrame, cluster_col_name: str) -> pd.DataFrame:
    mapping_renamed = mapping.rename(columns={"cluster_id": cluster_col_name})
    merged = final_df.merge(
        mapping_renamed, on="genome_id", how="left", validate="many_to_one"
    )
    return merged


# ---------------------------------------------------------------------------
# Step 4: diagnostics + plots
# ---------------------------------------------------------------------------
IMPORTANT_ANTIBIOTIC_TOP_N = 15


def cluster_diagnostics(df_with_clusters: pd.DataFrame, cluster_col: str, label: str, out_dir: Path) -> pd.DataFrame:
    genome_clusters = df_with_clusters.dropna(subset=[cluster_col])[["genome_id", cluster_col]].drop_duplicates()
    sizes = genome_clusters[cluster_col].value_counts()

    n_genomes_mapped = genome_clusters["genome_id"].nunique()
    n_genomes_total = df_with_clusters["genome_id"].nunique()

    diagnostics = {
        "threshold_label": label,
        "n_clusters": int(sizes.shape[0]),
        "n_singleton_clusters": int((sizes == 1).sum()),
        "median_cluster_size_genomes": float(sizes.median()),
        "mean_cluster_size_genomes": float(sizes.mean()),
        "max_cluster_size_genomes": int(sizes.max()),
        "pct_genomes_in_largest_cluster": round(100 * sizes.max() / n_genomes_mapped, 4),
        "pct_genomes_successfully_mapped": round(100 * n_genomes_mapped / n_genomes_total, 4),
        "n_genomes_total": int(n_genomes_total),
        "n_genomes_mapped": int(n_genomes_mapped),
    }
    diagnostics_df = pd.DataFrame([diagnostics])

    size_dist = sizes.value_counts().sort_index()
    size_dist_df = size_dist.rename("n_clusters_of_this_size").rename_axis("cluster_size_in_genomes").reset_index()
    size_dist_df.to_csv(out_dir / f"cluster_size_distribution_{label}.csv", index=False)

    rows_per_cluster = df_with_clusters.dropna(subset=[cluster_col]).groupby(cluster_col).size()
    rows_per_cluster.rename("n_antibiotic_rows").to_csv(out_dir / f"antibiotic_rows_per_cluster_{label}.csv")

    top_antibiotics = (
        df_with_clusters["antibiotic"].value_counts().head(IMPORTANT_ANTIBIOTIC_TOP_N).index.tolist()
    )
    class_balance_rows = []
    subset = df_with_clusters.dropna(subset=[cluster_col])
    for antibiotic in top_antibiotics:
        ab_df = subset[subset["antibiotic"] == antibiotic]
        counts = (
            ab_df.groupby(cluster_col)["is_resistant"]
            .agg(n_resistant=lambda s: int((s == 1).sum()), n_susceptible=lambda s: int((s == 0).sum()))
            .reset_index()
        )
        counts.insert(0, "antibiotic", antibiotic)
        class_balance_rows.append(counts)
    class_balance_df = pd.concat(class_balance_rows, ignore_index=True) if class_balance_rows else pd.DataFrame()
    class_balance_df.to_csv(out_dir / f"class_balance_per_antibiotic_cluster_{label}.csv", index=False)

    # Plots
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.bar(size_dist_df["cluster_size_in_genomes"].astype(str), size_dist_df["n_clusters_of_this_size"])
    ax.set_xlabel("Cluster size (genomes)")
    ax.set_ylabel("Number of clusters")
    ax.set_title(f"Cluster size distribution — {label}\n"
                 f"{diagnostics['n_clusters']} clusters, {diagnostics['n_singleton_clusters']} singletons")
    fig.tight_layout()
    fig.savefig(out_dir / f"cluster_size_distribution_{label}.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.hist(rows_per_cluster.to_numpy(), bins=30)
    ax.set_xlabel("Antibiotic rows per cluster")
    ax.set_ylabel("Number of clusters")
    ax.set_title(f"Antibiotic rows per cluster — {label}")
    fig.tight_layout()
    fig.savefig(out_dir / f"antibiotic_rows_per_cluster_{label}.png", dpi=160)
    plt.close(fig)

    return diagnostics_df


# ---------------------------------------------------------------------------
# Step 6: cluster-level split
# ---------------------------------------------------------------------------
def greedy_balanced_cluster_split(cluster_row_counts: pd.Series, seed: int = RANDOM_SEED) -> dict:
    order = cluster_row_counts.sample(frac=1.0, random_state=seed).sort_values(ascending=False).index
    total_rows = cluster_row_counts.sum()
    targets = {
        "train": TRAIN_FRACTION * total_rows,
        "calibration": CALIBRATION_FRACTION * total_rows,
        "hidden_test": (1 - TRAIN_FRACTION - CALIBRATION_FRACTION) * total_rows,
    }
    assigned_rows = {"train": 0, "calibration": 0, "hidden_test": 0}
    assignment = {}
    for cluster_id in order:
        size = cluster_row_counts[cluster_id]
        deficits = {name: targets[name] - assigned_rows[name] for name in targets}
        chosen = max(deficits, key=deficits.get)
        assignment[cluster_id] = chosen
        assigned_rows[chosen] += size
    return assignment


def build_split(df_with_clusters: pd.DataFrame, cluster_col: str, label: str, out_dir: Path) -> dict:
    df = df_with_clusters.dropna(subset=[cluster_col]).copy()
    n_dropped = len(df_with_clusters) - len(df)
    if n_dropped:
        print(f"[{label}] Dropping {n_dropped} rows whose genome has no Mash cluster assignment.")

    cluster_row_counts = df.groupby(cluster_col).size()
    assignment = greedy_balanced_cluster_split(cluster_row_counts, seed=RANDOM_SEED)
    df["split"] = df[cluster_col].map(assignment)

    splits_dir = out_dir / "splits"
    splits_dir.mkdir(parents=True, exist_ok=True)

    split_frames = {}
    for split_name in ["train", "calibration", "hidden_test"]:
        split_df = df[df["split"] == split_name].drop(columns=["split"])
        split_df.to_csv(splits_dir / f"{split_name}.csv", index=False)
        split_frames[split_name] = split_df

    assignment_df = pd.DataFrame(
        [{"cluster_id": c, "split": s, "n_rows": int(cluster_row_counts[c])} for c, s in assignment.items()]
    ).sort_values("cluster_id")
    assignment_df.to_csv(out_dir / "cluster_split_assignments.csv", index=False)

    diag_rows = []
    for split_name, split_df in split_frames.items():
        diag_rows.append({
            "split": split_name,
            "n_rows": len(split_df),
            "n_genomes": split_df["genome_id"].nunique(),
            "n_clusters": split_df[cluster_col].nunique(),
            "pct_of_total_rows": round(100 * len(split_df) / len(df), 2),
            "max_cluster_share_of_split_rows_pct": round(
                100 * split_df.groupby(cluster_col).size().max() / len(split_df), 2
            ) if len(split_df) else 0.0,
        })
    diagnostics_df = pd.DataFrame(diag_rows)
    diagnostics_df.to_csv(out_dir / "split_diagnostics.csv", index=False)

    return {"assignment": assignment, "split_frames": split_frames, "diagnostics_df": diagnostics_df}


# ---------------------------------------------------------------------------
# Step 7: integrity verification
# ---------------------------------------------------------------------------
def verify_split_integrity(split_frames: dict, cluster_col: str, label: str, out_dir: Path) -> dict:
    cluster_sets = {name: set(df[cluster_col].unique()) for name, df in split_frames.items()}
    genome_sets = {name: set(df["genome_id"].unique()) for name, df in split_frames.items()}
    pair_sets = {
        name: set(map(tuple, df[["genome_id", "antibiotic"]].astype(str).to_numpy()))
        for name, df in split_frames.items()
    }

    pairs = [("train", "calibration"), ("train", "hidden_test"), ("calibration", "hidden_test")]
    overlap_rows = []
    all_zero = True
    for a, b in pairs:
        cluster_overlap = len(cluster_sets[a] & cluster_sets[b])
        genome_overlap = len(genome_sets[a] & genome_sets[b])
        pair_overlap = len(pair_sets[a] & pair_sets[b])
        all_zero = all_zero and cluster_overlap == 0 and genome_overlap == 0 and pair_overlap == 0
        overlap_rows.append({
            "split_a": a, "split_b": b,
            "cluster_overlap": cluster_overlap,
            "genome_overlap": genome_overlap,
            "genome_antibiotic_pair_overlap": pair_overlap,
        })
    overlap_df = pd.DataFrame(overlap_rows)
    overlap_df.to_csv(out_dir / "cluster_overlap_check.csv", index=False)

    # every genome must be assigned to exactly one split (no genome split across splits at row level)
    genome_to_splits = {}
    for name, ids in genome_sets.items():
        for g in ids:
            genome_to_splits.setdefault(g, set()).add(name)
    genomes_in_multiple_splits = {g: s for g, s in genome_to_splits.items() if len(s) > 1}

    excluded_from_features = {"genome_id", "antibiotic", "is_resistant", cluster_col}

    report = {
        "threshold_label": label,
        "zero_overlap_confirmed": bool(all_zero),
        "genomes_in_multiple_splits": len(genomes_in_multiple_splits),
        "genomes_in_multiple_splits_sample": list(genomes_in_multiple_splits.keys())[:20],
        "columns_excluded_from_model_features": sorted(excluded_from_features),
    }
    if genomes_in_multiple_splits:
        raise ValueError(
            f"[{label}] {len(genomes_in_multiple_splits)} genomes have rows split across "
            f"multiple splits — cluster-split invariant violated."
        )
    if not all_zero:
        raise ValueError(f"[{label}] Non-zero cluster/genome/pair overlap detected: {overlap_rows}")

    return report


def main():
    if not MASH_THRESHOLDS:
        raise FileNotFoundError(f"No mash_cluster_*.csv files found in {MASH_DIR}")

    print(f"Discovered Mash cluster files: {list(MASH_THRESHOLDS.keys())}")
    if set(MASH_THRESHOLDS.keys()) != {"mash_002"}:
        print("NOTE: expected only mash_002 based on current repo contents — proceeding with what's found.")

    final_df = load_final_dataset()
    print(f"final_training_dataset.csv: {len(final_df)} rows, {final_df['genome_id'].nunique()} unique genomes")

    validation_reports = {}
    diagnostics_frames = {}
    integrity_reports = {}

    for label, path in MASH_THRESHOLDS.items():
        print(f"\n=== {label} ({path.name}) ===")
        mapping = load_mash_mapping(path)

        validation_report = validate_mapping(final_df, mapping, label)
        validation_reports[label] = validation_report
        print(json.dumps(validation_report, indent=2)[:1500])

        cluster_col = "cluster_id"
        joined = join_clusters(final_df, mapping, cluster_col)

        threshold_out_dir = BASE_DIR / "processed_data" / label
        threshold_out_dir.mkdir(parents=True, exist_ok=True)

        diag_df = cluster_diagnostics(joined, cluster_col, label, MASH_DIR)
        diagnostics_frames[label] = diag_df
        diag_df.to_csv(MASH_DIR / f"cluster_diagnostics_{label}.csv", index=False)
        print(diag_df.to_string(index=False))

        split_result = build_split(joined, cluster_col, label, threshold_out_dir)
        print(split_result["diagnostics_df"].to_string(index=False))

        integrity_report = verify_split_integrity(
            split_result["split_frames"], cluster_col, label, threshold_out_dir
        )
        integrity_reports[label] = integrity_report
        print(json.dumps(integrity_report, indent=2))

    # Save combined validation report and the fully-clustered dataset (uses the
    # single available threshold's cluster_id; if more thresholds are added later,
    # each gets its own <label>-suffixed column here instead of overwriting).
    with open(MASH_DIR / "mapping_validation_report.json", "w", encoding="utf-8") as f:
        json.dump(validation_reports, f, indent=2)

    with open(BASE_DIR / "processed_data" / "mash_split_integrity_report.json", "w", encoding="utf-8") as f:
        json.dump(integrity_reports, f, indent=2)

    combined = final_df.copy()
    for label, path in MASH_THRESHOLDS.items():
        mapping = load_mash_mapping(path)
        combined = combined.merge(
            mapping.rename(columns={"cluster_id": f"cluster_id_{label}"}),
            on="genome_id", how="left", validate="many_to_one",
        )
    combined_path = BASE_DIR / "processed_data" / "final_training_dataset_with_mash_clusters.csv"
    combined.to_csv(combined_path, index=False)
    print(f"\nSaved {combined_path} ({len(combined)} rows, columns: {list(combined.columns[-len(MASH_THRESHOLDS):])})")

    print("\nAll Mash integration steps complete.")


if __name__ == "__main__":
    main()
