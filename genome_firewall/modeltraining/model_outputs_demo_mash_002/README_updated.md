# Genome Firewall — demo model package (mash_002)

> **Research prototype. Every prediction must be confirmed with standard laboratory susceptibility testing.**

## Supported scope

- **Bacterial species: *Escherichia coli* only.** Every genome in the training, calibration, and
  hidden-test data carries BV-BRC/NCBI taxon prefix `562.*`. **Do not apply these models to genomes
  from any other species** — a resistance relationship learned for one species does not
  automatically generalize to another; a different species can have a different (or absent) target
  gene, different baseline gene content, and different resistance mechanisms entirely.
- **Supported demo antibiotics:**
  - `ciprofloxacin`
  - `trimethoprim/sulfamethoxazole`
  - `cephalothin`
  - `nalidixic acid`

`scorer.list_supported_antibiotics()` in `score_resistance.py` is the single source of truth for
this list — it reads directly from the packaged models, so it can never drift out of sync with this
document.

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

**`no_call` is a calibration-tuned probability band, not an out-of-distribution (novelty) detector.**
It says nothing about whether the input genome resembles the training data — it only means the
calibrated probability landed between the two thresholds, where called predictions weren't reliable
enough on the calibration set. A genome wildly unlike anything in training could still land outside
the no-call band and receive a confident (and potentially wrong) called prediction. No separate
novelty/OOD check is implemented in this package.

## Molecular-target gate

The challenge requires a deterministic check that the antibiotic's molecular target is actually
present before reporting `likely_to_work` — the system should never call a drug "likely to work"
purely because no resistance marker was detected; it should also confirm there's something for the
drug to act on. This is implemented in `score_resistance.py` (`_check_target_gate`), not just
described:

| Antibiotic | Molecular target |
|---|---|
| ciprofloxacin, nalidixic acid | DNA gyrase (gyrA/gyrB) + topoisomerase IV (parC/parE) |
| trimethoprim/sulfamethoxazole | dihydrofolate reductase (folA) + dihydropteroate synthase (folP) |
| cephalothin | penicillin-binding proteins (e.g. ftsI/PBP3) |

**Honest limitation:** all four targets above are core/chromosomal *E. coli* genes — every genome in
this single-species dataset has them by definition of being *E. coli*. AMRFinderPlus (our feature
source) only reports acquired resistance genes and resistance-conferring point mutations in
otherwise-intact core genes; it does not track core-gene presence/absence at all. So there is
currently no feature in the 277-column panel that could ever indicate a target is missing. The gate
is fully implemented and runs on every prediction (`target_gate` field in the output), but on
today's data it always passes — it is real, executed logic with an empty rule set
(`TARGET_GATE_INFO[antibiotic]["target_loss_features"] == []`), not a fake stub. The moment a
target-loss/target-bypass feature becomes available (e.g. a future multi-species deployment), add it
to that list and the gate starts actually gating with no other code change. If the gate ever does
fail, the prediction is forced to `no_call` regardless of what the resistance-probability model says.

## Evidence categories

Every prediction includes an `evidence_category` field distinguishing three cases, per the challenge
brief:

- `known_resistance_marker` — at least one feature present in this sample is a resistance
  determinant *directly relevant to this antibiotic's mechanism* (e.g. a gyrA/parC mutation for
  ciprofloxacin, a dfrA/sul gene for trimethoprim/sulfamethoxazole, a bla* gene for cephalothin).
- `statistical_association_only` — the model's prediction was driven by features present in this
  sample, but none of them are a direct mechanistic marker for *this* antibiotic — e.g. a
  beta-lactamase gene showing up as predictive of fluoroquinolone resistance because multidrug-
  resistant strains tend to carry both, not because it causes fluoroquinolone resistance.
  `top_supporting_features`/`model_coefficients.csv` already carry the explicit "does not prove
  causation" wording — this field makes the causal-vs-correlational distinction machine-readable.
- `no_known_resistance_signal` — no direct or model-used resistance feature for this
  antibiotic was detected in the available AMRFinderPlus-derived feature panel. This does **not**
  prove that the genome contains no resistance mechanism at all; it only means that no relevant
  signal was represented and detected in the features available to this model.

The mapping of which features count as a "direct marker" per antibiotic is a small, hand-curated,
pharmacology-based table (`ANTIBIOTIC_DIRECT_MARKER_SUBSTRINGS` in `score_resistance.py`) — every
feature in our panel is technically a curated AMRFinderPlus resistance determinant (AMRFinderPlus
doesn't report arbitrary statistical predictors), so the distinction here is specifically about
mechanism-relevance to *this* drug, not about database provenance.

The marker rules were checked against the exact feature names present in `feature_columns.json`.
Broad matches such as `bla*` are intentional because they represent beta-lactamase families rather
than one single gene. Any future extension of the feature panel should re-run this validation to
ensure that no newly added feature is classified as a direct marker merely because it contains a
similar substring. Where practical, exact-name or anchored family-prefix matching should be
preferred over unrestricted substring matching.

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
held-out test set — they are NOT specific to any one genome's prediction. `score_resistance.py`
returns them separately from `probability_resistant` (which IS sample-specific — see the note below
on terminology) for exactly this reason — never blend the two in the UI.

Also see `metrics_by_cluster.csv` for the same metrics broken down by genetic (Mash) cluster on the
hidden-test set, fulfilling the brief's request to report generalization by genetically related
group. Most clusters are singletons or very small (see
`mash_preprocessed_data/usability_tradeoff_mash_002.md`) — rows with `small_group_warning == True`
are not individually statistically stable and should be read as directional only, not precise.

**Terminology note:** predictions are **sample-specific** (one reconstructed genome), not
"patient-specific" — this system never sees a patient or a raw clinical sample; the challenge scope
starts only after bacterial isolation, sequencing, and genome reconstruction are already complete.

## Confidence — exact definition

```python
if prediction == "likely_to_fail":
    confidence = probability_resistant
elif prediction == "likely_to_work":
    confidence = 1 - probability_resistant
else:  # no_call
    confidence = None
```

`confidence` is always `null`/`None` for `no_call` — never a number. Without this rule, a
`likely_to_work` call with `probability_resistant = 0.10` could otherwise be misread as
"confidence: 0.10" (low), when it actually means 90% confidence the drug will work.

## Files your teammate needs

```
model_outputs_demo_mash_002/
  calibrated_models.joblib       # sklearn CalibratedClassifierCV per antibiotic (4 demo antibiotics)
  feature_columns.json           # {antibiotic: [ordered feature names]} — required for alignment
  thresholds.json                # {antibiotic: {susceptible_threshold, resistant_threshold, ...}}
  per_antibiotic_metrics.csv     # full metrics table, all 63 antibiotics, tagged by model_tier
  metrics_by_cluster.csv         # same metrics broken down by Mash genetic cluster (demo antibiotics)
  demo_candidates.csv            # the 4 demo-tier antibiotics and their metrics
  strict_candidates.csv          # empty this run — no antibiotic met the strict bar
  experimental_demo_only.csv     # empty this run — fallback wasn't needed
  unsupported_antibiotics.csv    # antibiotics with no usable model at all, and why
  model_coefficients.csv         # per-antibiotic feature coefficients (statistical association,
                                  # NOT causation — see causation_warning column)
  plots/reliability/*.png        # calibration reliability plot per demo antibiotic (Brier score,
                                  # perfect-calibration diagonal, observed vs predicted probability)
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
#   "species": "Escherichia coli",
#   "probability_resistant": 0.83,              # sample-specific
#   "prediction": "likely_to_fail",              # likely_to_work | likely_to_fail | no_call
#   "confidence": 0.83,                          # null when prediction == "no_call"
#   "evidence_category": "known_resistance_marker",   # or statistical_association_only /
#                                                      # no_known_resistance_signal
#   "target_gate": {                             # molecular-target gate result — see above
#       "target_description": "...", "target_gate_passed": true,
#       "target_loss_features_detected": [], "note": "..." },
#   "susceptible_threshold": 0.20,
#   "resistant_threshold": 0.75,
#   "top_supporting_features": [...],            # sample-specific, genes present in THIS genome
#   "historical_model_metrics": {...},           # model-level, NOT sample-specific
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
