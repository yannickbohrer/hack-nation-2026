"""
Splits the final training dataset into Train, Calibration, and Hidden Test sets.

Genome-level grouping alone (keeping a genome_id's antibiotic rows together) does
NOT prevent near-identical/clonal genomes from being split across train and test —
a plain random split over genome_id still lets near-duplicate strains leak across
the boundary. This version builds genetic-similarity clusters first, using the
AMR gene/mutation presence-absence profile as a similarity proxy (no raw FASTA is
available for the full genome set, only AMRFinderPlus-style calls), then splits at
the CLUSTER level so no near-identical genome pair crosses a split.

Similarity threshold: Jaccard >= 0.98 on the binary feature vector, requiring the
union of positive features to be >= 2 (so two genomes that merely share zero genes,
or a single coincidental gene, are not treated as clones). This is deliberately
conservative — it catches clonal/outbreak-level near-duplicates without merging
distinct genomes that happen to share one common resistance gene. Threshold choice
is a team judgment call per the challenge brief; documented here for that reason.
"""
import numpy as np
import pandas as pd
from pathlib import Path

INPUT_PATH = Path(__file__).resolve().parent.parent / "modeltraining" / "processed_data" / "final_training_dataset.csv"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "modeltraining" / "processed_data" / "splits"

JACCARD_THRESHOLD = 0.98
MIN_UNION_FOR_SIMILARITY = 2
RANDOM_SEED = 42
TRAIN_FRACTION = 0.60
CALIBRATION_FRACTION = 0.20
# hidden_test gets the remainder (~0.20)


def build_genetic_clusters(per_genome: pd.DataFrame) -> pd.Series:
    """Union-find over genomes whose AMR profile Jaccard similarity >= JACCARD_THRESHOLD."""
    genome_ids = per_genome.index.to_numpy()
    X = per_genome.to_numpy(dtype=np.uint8)
    n = len(genome_ids)

    parent = list(range(n))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i, j):
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[rj] = ri

    chunk = 300
    for i0 in range(0, n, chunk):
        A = X[i0:i0 + chunk]
        inter = A @ X.T
        a_sum = A.sum(axis=1, keepdims=True)
        b_sum = X.sum(axis=1, keepdims=True).T
        union_counts = a_sum + b_sum - inter
        jaccard = np.zeros(union_counts.shape, dtype=float)
        valid = union_counts >= MIN_UNION_FOR_SIMILARITY
        jaccard[valid] = inter[valid] / union_counts[valid]
        for ii in range(A.shape[0]):
            gi = i0 + ii
            hits = np.where(jaccard[ii, gi + 1:] >= JACCARD_THRESHOLD)[0] + gi + 1
            for gj in hits:
                union(gi, int(gj))

    roots = np.array([find(i) for i in range(n)])
    _, cluster_ids = np.unique(roots, return_inverse=True)
    return pd.Series(cluster_ids, index=genome_ids, name="cluster_id")


def greedy_balanced_cluster_split(cluster_sizes: pd.Series, seed: int = RANDOM_SEED):
    """Assign whole clusters to train/calibration/hidden_test, biggest clusters first,
    always to whichever bucket is furthest below its target row-count share. Keeps
    row proportions close to target while never splitting a cluster."""
    rng = np.random.default_rng(seed)
    order = cluster_sizes.sample(frac=1.0, random_state=seed).sort_values(ascending=False).index

    total_rows = cluster_sizes.sum()
    targets = {
        "train": TRAIN_FRACTION * total_rows,
        "calibration": CALIBRATION_FRACTION * total_rows,
        "hidden_test": (1 - TRAIN_FRACTION - CALIBRATION_FRACTION) * total_rows,
    }
    assigned_rows = {"train": 0, "calibration": 0, "hidden_test": 0}
    assignment = {}

    for cluster_id in order:
        size = cluster_sizes[cluster_id]
        deficits = {name: targets[name] - assigned_rows[name] for name in targets}
        chosen = max(deficits, key=deficits.get)
        assignment[cluster_id] = chosen
        assigned_rows[chosen] += size

    return assignment


def main():
    print("Loading finalized dataset...")
    df = pd.read_csv(INPUT_PATH, dtype={"genome_id": str})
    print(f"Total rows before split: {len(df)}")

    feature_cols = [c for c in df.columns if c not in ("genome_id", "antibiotic", "is_resistant")]
    per_genome = df.groupby("genome_id")[feature_cols].first()
    n_genomes = len(per_genome)
    print(f"Unique genomes: {n_genomes}")

    print("Building genetic-similarity clusters (Jaccard >= "
          f"{JACCARD_THRESHOLD}, min shared features {MIN_UNION_FOR_SIMILARITY})...")
    genome_to_cluster = build_genetic_clusters(per_genome)
    n_clusters = genome_to_cluster.nunique()
    cluster_genome_counts = genome_to_cluster.value_counts()
    print(f"Genetic clusters found: {n_clusters} "
          f"(largest cluster: {int(cluster_genome_counts.max())} genomes, "
          f"singletons: {int((cluster_genome_counts == 1).sum())})")

    df = df.merge(
        genome_to_cluster.rename("cluster_id"),
        left_on="genome_id", right_index=True, how="left",
    )

    cluster_row_counts = df.groupby("cluster_id").size()
    assignment = greedy_balanced_cluster_split(cluster_row_counts)
    df["split"] = df["cluster_id"].map(assignment)

    train_df = df[df["split"] == "train"].drop(columns=["split"])
    calib_df = df[df["split"] == "calibration"].drop(columns=["split"])
    test_df = df[df["split"] == "hidden_test"].drop(columns=["split"])

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    train_df.to_csv(OUTPUT_DIR / "train.csv", index=False)
    calib_df.to_csv(OUTPUT_DIR / "calibration.csv", index=False)
    test_df.to_csv(OUTPUT_DIR / "hidden_test.csv", index=False)

    genome_to_cluster.rename("cluster_id").to_csv(OUTPUT_DIR / "genome_cluster_map.csv")

    print("\nDataset successfully split at the genetic-cluster level!")
    for name, split_df in [("Train", train_df), ("Calibration", calib_df), ("Hidden Test", test_df)]:
        n_split_genomes = split_df["genome_id"].nunique()
        n_split_clusters = split_df["cluster_id"].nunique()
        print(f"  {name:12s}: {len(split_df):5d} rows, {n_split_genomes:4d} genomes, {n_split_clusters:4d} clusters")

    # Sanity check: no cluster should ever appear in more than one split.
    cluster_split_counts = df.groupby("cluster_id")["split"].nunique()
    leaking_clusters = int((cluster_split_counts > 1).sum())
    print(f"\nClusters spanning more than one split (should be 0): {leaking_clusters}")
    assert leaking_clusters == 0, "Cluster-level split invariant violated."


if __name__ == "__main__":
    main()
