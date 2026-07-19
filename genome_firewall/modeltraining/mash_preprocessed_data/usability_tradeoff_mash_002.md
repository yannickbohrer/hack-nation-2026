# Mash clustering usability assessment — mash_002 (Mash distance ≤ 0.02)

Only one Mash threshold file exists on disk (`mash_cluster_002.csv`). The 0.05 version referenced
in earlier planning was never generated, so this is an assessment of mash_002 alone, not a
comparison. Numbers below come from `integrate_mash_clusters.py` (see `cluster_diagnostics_mash_002.csv`,
`processed_data/mash_002/split_diagnostics.csv`, `cluster_overlap_check.csv`).

## Usability checklist (per the criteria requested, not test accuracy)

| Criterion | Result | Verdict |
|---|---|---|
| Enough distinct clusters for train/calibration/test | 2,651 clusters across 3,003 genomes (1,231 / 710 / 710 clusters per split) | Pass — plenty of granularity |
| No cluster crossing splits | `cluster_overlap_check.csv`: 0 cluster/genome/pair overlap on all 3 split-pairs | Pass |
| Sufficient resistant/susceptible examples for main antibiotics | Not fully checked here — see `class_balance_per_antibiotic_cluster_mash_002.csv`, needs a pass through the notebook's per-antibiotic class-count table once run against this split | Needs notebook run to confirm (next step) |
| No single cluster dominating a split | Largest cluster is 15 genomes; max cluster share of any split's rows is 1.04% (train), 0.27% (calibration/test) | Pass — no domination |
| Reasonable singleton count | 2,423 / 2,651 clusters (91%) are singletons | Borderline — see caveat below |
| Meaningful held-out genetic groups | 580 genomes (19.3%) sit in a multi-genome cluster; the rest are singletons | Weaker signal than the caveat-free ideal — see below |

## The singleton caveat

At Mash distance ≤ 0.02, 91% of clusters are singletons — i.e. for the large majority of genomes,
Mash found no other genome in the dataset within that tight a distance. This is expected at a strict
threshold: it does successfully catch true near-clones (the 580 genomes in multi-member clusters,
up to 15-genome clusters — almost certainly outbreak-related or repeatedly-sequenced strains), but a
singleton genome contributes no more "leakage protection" than a plain random genome-level split
would for that genome specifically. In other words: mash_002 is a real, working de-duplication step —
it correctly isolates the near-identical strains that matter — but for the ~80% of genomes with no
close relative in the dataset, this split behaves like the (already-implemented) genome-level random
split. That's not a flaw, it's what a correct clustering *should* do when most genomes genuinely
aren't near-duplicates of each other — but it means most of the "harder generalization test" framing
below doesn't come from mash_002 itself, it would come from a looser threshold.

## Expected effect of a broader threshold (0.05), if generated

Not measured — stated for planning purposes only, based on general clustering behavior, not this
dataset's actual numbers:
- A distance-0.05 cutoff merges more genomes per cluster (looser similarity bar), producing **fewer,
  larger clusters** and likely a **lower singleton fraction**.
- That would make the held-out test set genuinely harder (larger genetic "distance" enforced between
  train and test groups), at the cost of **less fine-grained control** over the 60/20/20 row-count
  target (bigger clusters are lumpier to distribute) and a higher chance some smaller antibiotics lose
  class balance in a given split, since whole clusters can't be split to fix that.
- Recommend generating `mash_cluster_005.csv` through the same Mash + hierarchical-clustering pipeline
  proposed earlier, then rerunning `integrate_mash_clusters.py` (it already loops over any
  `mash_cluster_*.csv` file present, no code change needed) to get a real, measured comparison instead
  of this qualitative expectation.

## Recommendation

mash_002 is usable for splitting as-is: verified zero leakage across all three overlap dimensions,
proportions land almost exactly on 60/20/20 by construction, and no split is dominated by one cluster.
Treat it as a *stricter, higher-confidence* de-duplication than the AMR-profile-Jaccard clustering used
previously (independent method, same order of magnitude of near-duplicate genomes found — 19.3% here
vs ~20% from the AMR-profile proxy — cross-validates that estimate). It is not, on its own, the
"harder generalization test" a broader threshold would provide; that requires generating and comparing
against mash_005.
