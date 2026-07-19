# Genome Firewall — demo model package (mash_002)

> **Research prototype. Every prediction must be confirmed with standard laboratory susceptibility testing.**

## What the model takes as input

One row of **binary AMR gene/mutation presence-absence features** (0/1) per genome, produced by
Pipeline 1 (AMRFinderPlus-style feature extraction). The model input is **only** this feature
vector. These columns are never used as model input, even if present in the source row:
`genome_id`, `antibiotic`, `is_resistant`, `cluster_id`, `split`. The exact feature list and order
required per antibiotic is in `feature_columns.json` — `score_resistance.py` enforces this
automatically (raises if a required feature is missing, ignores extra columns).

`antibiotic` is a *lookup key only* — it selects which of the per-antibiotic models to run. It is
never fed into the model as a feature.

## Which antibiotics are included

Three tiers, all in `per_antibiotic_metrics.csv` (`model_tier` column):

- **strict** — meets the notebook's unchanged research/deployment criteria (`MIN_BALANCED_ACCURACY
  0.60, MIN_RESISTANT_RECALL 0.50, MIN_DEPLOYMENT_COVERAGE 0.30, MIN_DEPLOYMENT_CALLED_ACCURACY
  0.90`, plus a valid no-call threshold and full hidden-test evaluability). **0 antibiotics
  currently meet this bar** — see `strict_candidates.csv` (empty). This is an honest result, not a
  bug: the baseline model genuinely isn't strong enough yet for any antibiotic under the strict bar.
- **demo** — a separate, explicitly-labeled, looser bar for hackathon demo purposes only (see
  below). **4 antibiotics currently qualify**: `ciprofloxacin`, `trimethoprim/sulfamethoxazole`,
  `cephalothin`, `nalidixic acid`. See `demo_candidates.csv`.
- **experimental_demo_only** — fallback ranking used only if zero antibiotics clear any demo
  threshold rung. Not triggered this run (`experimental_demo_only.csv` is empty) — demo criteria
  were met outright.

Everything else is `unsupported_antibiotics.csv` (40 antibiotics — insufficient class diversity in
train or calibration, or too few hidden-test samples to evaluate).

**The website should only offer the demo-tier antibiotics for the demo** (`calibrated_models.joblib`
only contains these 4 — nothing outside that list can even be scored, `predict()` raises for
anything else).

## Demo criteria — explicitly NOT clinical or deployment criteria

```
balanced_accuracy >= 0.55
resistant_recall  >= 0.40
coverage          >= 0.20
called_accuracy   >= 0.80
both classes present in train, calibration, AND hidden_test
```

These are a **hackathon-demo selection bar**, chosen to be *usable*, not *clinically defensible*.
Never present a `demo`-tier or `experimental_demo_only`-tier result as validated for real use — the
mandatory warning must always accompany it (enforced in `score_resistance.py`'s output).

If no antibiotic had cleared this bar, the build script (`build_demo_package.py`) would have
progressively relaxed it through 3 further rungs (documented in `metadata.json` →
`demo_criteria_rungs`) before falling back to ranking the best 1–3 calibrated models by a documented
composite formula (`metadata.json` → `experimental_rank_formula`) and labeling them
`experimental_demo_only`. That fallback did not trigger this run — the original, unrelaxed bar
already produced 4 candidates.

## How the Mash cluster split works

Genomes were clustered by **whole-genome Mash distance ≤ 0.02** (not by feature-vector similarity —
this is an actual sequence-based clustering, done externally via Mash and joined onto the dataset).
`train.csv` / `calibration.csv` / `hidden_test.csv` under `processed_data/mash_002/splits/` are split
**by whole cluster**, never by individual genome or row — every genome in a Mash cluster stays in
exactly one split, and every antibiotic-row for a genome stays with that genome. Verified zero
cluster, genome, and genome-antibiotic-pair overlap across all three splits
(`cluster_overlap_check.csv` in `processed_data/mash_002/`). This is what makes hidden-test
performance a genuine held-out-strain generalization test rather than an inflated same-strain score.

## How calibration and no-call thresholds work

Each antibiotic gets its own logistic-regression model, trained on `train.csv` only, then calibrated
(sigmoid/Platt scaling) on `calibration.csv` only — never on hidden_test. The calibrated probability
`probability_resistant` is then compared against two antibiotic-specific thresholds
(`thresholds.json`), tuned on the calibration split to hit a target called-accuracy at maximum
coverage:

```
probability <= susceptible_threshold  ->  likely_to_work
probability >= resistant_threshold    ->  likely_to_fail
otherwise                             ->  no_call
```

`no_call` is a deliberate output, not a failure — it means the evidence doesn't clear the accuracy
bar this antibiotic's thresholds were tuned to, and no confidence value is returned for it.

## What each metric means

- **balanced_accuracy** — average of resistant recall and susceptible recall (fair under class imbalance).
- **resistant_recall** — of samples that were truly resistant, fraction correctly identified as resistant.
- **susceptible_recall** — same, for truly susceptible samples.
- **F1 (resistant class)** — harmonic mean of precision and recall for the resistant class.
- **AUROC** — overall ranking quality between resistant/susceptible, threshold-independent.
- **PR-AUC** — like AUROC but more informative under class imbalance (most antibiotics here are imbalanced).
- **Brier score** — mean squared error of the probability itself; lower is better calibration.
- **coverage** — fraction of hidden-test samples the model was willing to call at all (not no_call).
- **called_accuracy** — accuracy only among the samples it *did* call (excludes no_calls).

All of these are **historical, model-level statistics** describing how the model performed on the
held-out test set — they are NOT specific to any one patient's prediction. `score_resistance.py`
returns them separately from `probability_resistant` (which IS patient-specific) for exactly this
reason — never blend the two in the UI.

## Files your teammate needs

```
model_outputs_demo_mash_002/
  calibrated_models.joblib       # sklearn CalibratedClassifierCV per antibiotic (4 demo antibiotics)
  feature_columns.json           # {antibiotic: [ordered feature names]} — required for alignment
  thresholds.json                # {antibiotic: {susceptible_threshold, resistant_threshold, ...}}
  per_antibiotic_metrics.csv     # full metrics table, all 63 antibiotics, tagged by model_tier
  demo_candidates.csv            # the 4 demo-tier antibiotics and their metrics
  strict_candidates.csv          # empty this run — no antibiotic met the strict bar
  experimental_demo_only.csv     # empty this run — fallback wasn't needed
  unsupported_antibiotics.csv    # antibiotics with no usable model at all, and why
  model_coefficients.csv         # per-antibiotic feature coefficients (statistical association,
                                  # NOT causation — see causation_warning column)
  metadata.json                  # provenance, criteria used, counts, timestamps
  README.md                      # this file
```

Plus, in the parent `modeltraining/` directory: `score_resistance.py` (the scoring script itself).

## How the website should call the scoring function

```python
from score_resistance import ResistanceScorer

scorer = ResistanceScorer()  # loads the package once — do this at process startup, not per-request

# feature_row: dict or one-row DataFrame of binary AMR features for one genome,
# as produced by Pipeline 1. Do not include genome_id/antibiotic/is_resistant/cluster_id.
result = scorer.predict(feature_row, antibiotic="ciprofloxacin")

# result = {
#   "antibiotic": "ciprofloxacin",
#   "probability_resistant": 0.83,              # patient-specific
#   "prediction": "likely_to_fail",              # likely_to_work | likely_to_fail | no_call
#   "confidence": 0.83,                          # null when prediction == "no_call"
#   "susceptible_threshold": 0.20,
#   "resistant_threshold": 0.75,
#   "top_supporting_features": [...],            # patient-specific, genes present in THIS sample
#   "historical_model_metrics": {...},           # model-level, NOT patient-specific
#   "warning": "Research prototype. Every prediction must be confirmed with standard
#               laboratory susceptibility testing."
# }

# To score every supported demo antibiotic for one genome at once:
all_results = scorer.predict_all_supported(feature_row)
```

`scorer.list_supported_antibiotics()` returns exactly the antibiotics the website is allowed to
offer for the demo. Calling `.predict()` with anything else raises `ValueError` with the supported
list in the message — fail loudly rather than silently guessing.

## Mandatory warning

Every prediction returned by `score_resistance.py` includes:

> "Research prototype. Every prediction must be confirmed with standard laboratory susceptibility testing."

The website must display this warning alongside every prediction shown to a user. Do not strip it,
shorten it, or make it optional.
