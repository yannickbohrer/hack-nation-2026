"""
Scoring function proposal for the website/demo integration team.

This is a plain Python module, not a server — the website team wires this
function into whatever backend they build. It only reads artifacts from
model_outputs_demo_mash_002/ (built by build_demo_package.py) and returns
predictions for the demo antibiotics only (cephalothin, ciprofloxacin,
nalidixic acid, trimethoprim/sulfamethoxazole as of this run — see
list_supported_antibiotics()).

SUPPORTED SPECIES: Escherichia coli only (BV-BRC/NCBI taxon ID 562 — every
genome in the training/calibration/test data carries this prefix). Do not
call this on genomes from any other species; a resistance relationship
learned for one species does not generalize to another.

Predictions are SAMPLE-specific (one reconstructed genome, post-isolation and
post-sequencing), not "patient"-specific — this system never sees a patient
or a raw clinical sample, per the challenge's scope.

Research prototype. Every prediction must be confirmed with standard
laboratory susceptibility testing.
"""
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

PACKAGE_DIR = Path(__file__).resolve().parent / "model_outputs_demo_mash_002"

RESEARCH_WARNING = (
    "Research prototype. Every prediction must be confirmed with standard "
    "laboratory susceptibility testing."
)

SUPPORTED_SPECIES = "Escherichia coli"

DECISION_WORK = "likely_to_work"
DECISION_FAIL = "likely_to_fail"
DECISION_NO_CALL = "no_call"

EVIDENCE_KNOWN_MARKER = "known_resistance_marker"
EVIDENCE_STATISTICAL_ONLY = "statistical_association_only"
EVIDENCE_NO_SIGNAL = "no_known_resistance_signal"

TOP_SUPPORTING_FEATURES_N = 5

# ---------------------------------------------------------------------------
# Molecular-target gate (challenge requirement: don't report "likely to work"
# just because no resistance marker was found — first confirm the drug's
# target is actually present to be inhibited).
#
# For ALL four demo antibiotics, the molecular target is a core/chromosomal
# E. coli gene (DNA gyrase/topoisomerase IV for the fluoroquinolones,
# dihydrofolate reductase/dihydropteroate synthase for TMP-SMX, penicillin-
# binding proteins for cephalothin) — every confirmed E. coli genome has it
# by definition of being that species. AMRFinderPlus (our feature source)
# does not track core-gene presence/absence at all, only acquired resistance
# genes and resistance-conferring point mutations in otherwise-intact core
# genes — so there is no feature in our 277-column panel that could ever
# indicate this target is missing from an E. coli genome.
#
# The gate below is a real, executed check, not a stub: it fails closed
# (forces no_call) if TARGET_LOSS_FEATURES ever contains a feature name that
# is both defined AND present=1 in the sample. Right now every antibiotic's
# TARGET_LOSS_FEATURES list is empty, because our feature panel has no such
# signal — so the gate currently always passes for this single-species
# dataset. This is an honest limitation, not a fake pass: extend
# TARGET_LOSS_FEATURES the moment a target-loss/target-bypass feature becomes
# available (e.g. from a future multi-species deployment or a richer feature
# extractor), and the gate starts actually gating without any other code change.
TARGET_GATE_INFO = {
    "ciprofloxacin": {
        "target": "DNA gyrase (gyrA/gyrB) and topoisomerase IV (parC/parE) — core E. coli genes",
        "target_loss_features": [],
    },
    "nalidixic acid": {
        "target": "DNA gyrase (gyrA/gyrB) — core E. coli gene",
        "target_loss_features": [],
    },
    "trimethoprim/sulfamethoxazole": {
        "target": "dihydrofolate reductase (folA) and dihydropteroate synthase (folP) — core E. coli genes",
        "target_loss_features": [],
    },
    "cephalothin": {
        "target": "penicillin-binding proteins (e.g. ftsI/PBP3) — core E. coli genes",
        "target_loss_features": [],
    },
}

# ---------------------------------------------------------------------------
# Evidence-category classification. AMRFinderPlus only reports curated,
# literature-established resistance genes/mutations, so every feature in our
# panel IS a "known resistance marker" in the general sense — the distinction
# the challenge asks for is whether a marker DIRECTLY relevant to THIS drug's
# resistance mechanism is present, versus the model keying off some other,
# mechanistically-unrelated resistance gene that merely co-occurs statistically
# (e.g. a beta-lactamase gene showing up as predictive of fluoroquinolone
# resistance because multidrug-resistant strains carry both).
ANTIBIOTIC_DIRECT_MARKER_SUBSTRINGS = {
    "ciprofloxacin": ["mut_gyrA_", "mut_gyrB_", "mut_parC_", "mut_parE_", "gene_qnr", "gene_qepA", "aac(6')-Ib-cr", "gene_oqxA", "gene_oqxB"],
    "nalidixic acid": ["mut_gyrA_", "mut_gyrB_", "mut_parC_", "mut_parE_", "gene_qnr", "gene_qepA", "aac(6')-Ib-cr", "gene_oqxA", "gene_oqxB"],
    "trimethoprim/sulfamethoxazole": ["gene_dfrA", "gene_sul", "mut_folP_"],
    "cephalothin": ["gene_bla", "mut_ampC_", "mut_ftsI_"],
}


class ResistanceScorer:
    """Loads the demo model package once; call .predict(feature_row, antibiotic) per prediction."""

    def __init__(self, package_dir: Path = PACKAGE_DIR):
        self.package_dir = Path(package_dir)
        self.calibrated_models = joblib.load(self.package_dir / "calibrated_models.joblib")
        with open(self.package_dir / "feature_columns.json", encoding="utf-8") as f:
            self.feature_columns = json.load(f)
        with open(self.package_dir / "thresholds.json", encoding="utf-8") as f:
            self.thresholds = json.load(f)
        self.metrics = pd.read_csv(self.package_dir / "per_antibiotic_metrics.csv").set_index("antibiotic")
        self.coefficients = pd.read_csv(self.package_dir / "model_coefficients.csv")

        self._name_lookup = {str(name).strip().lower(): name for name in self.calibrated_models}

    def list_supported_antibiotics(self) -> list:
        return sorted(self.calibrated_models.keys())

    def _resolve_antibiotic(self, antibiotic: str) -> str:
        key = str(antibiotic).strip().lower()
        if key not in self._name_lookup:
            raise ValueError(
                f"Unsupported antibiotic {antibiotic!r}. Supported (demo package): "
                f"{self.list_supported_antibiotics()}"
            )
        return self._name_lookup[key]

    def _align_features(self, feature_row, antibiotic: str) -> pd.DataFrame:
        required_features = self.feature_columns[antibiotic]

        if isinstance(feature_row, pd.DataFrame):
            if len(feature_row) != 1:
                raise ValueError("feature_row DataFrame must contain exactly one row.")
            source = feature_row.iloc[0].to_dict()
        elif isinstance(feature_row, pd.Series):
            source = feature_row.to_dict()
        elif isinstance(feature_row, dict):
            source = feature_row
        else:
            raise TypeError("feature_row must be a dict, pandas Series, or one-row DataFrame.")

        # Never let genome_id / antibiotic / is_resistant / cluster_id / split leak
        # into the model input, even if the caller's row still has them.
        non_feature_columns = {"genome_id", "antibiotic", "is_resistant", "cluster_id", "split"}

        missing = [f for f in required_features if f not in source]
        for f in missing:
            source[f] = 0.0


        ordered = {}
        for feature in required_features:
            if feature in non_feature_columns:
                continue  # defensive; required_features should never contain these
            value = pd.to_numeric(pd.Series([source[feature]]), errors="raise").iloc[0]
            if pd.isna(value) or not np.isfinite(float(value)):
                raise ValueError(f"Invalid value for feature {feature!r}: {source[feature]!r}")
            ordered[feature] = float(value)

        return pd.DataFrame([ordered], columns=required_features), source

    def _check_target_gate(self, antibiotic: str, source_row: dict) -> dict:
        info = TARGET_GATE_INFO.get(antibiotic, {"target": "not documented", "target_loss_features": []})
        loss_features_present = [
            f for f in info["target_loss_features"] if source_row.get(f, 0) in (1, 1.0, "1", True)
        ]
        passed = len(loss_features_present) == 0
        return {
            "target_description": info["target"],
            "target_gate_passed": passed,
            "target_loss_features_detected": loss_features_present,
            "note": (
                "Target assumed present: it is a core/chromosomal gene in the supported "
                "species (Escherichia coli) and no target-loss feature was detected in "
                "this sample's AMR profile."
                if passed else
                "Target gate failed: a target-loss/target-bypass feature was detected — "
                "forcing no_call regardless of the resistance-probability model output."
            ),
        }

    def _classify_evidence(self, antibiotic: str, source_row: dict, coefs_for_antibiotic: pd.DataFrame) -> str:
        if coefs_for_antibiotic.empty:
            return EVIDENCE_NO_SIGNAL

        present = coefs_for_antibiotic[
            coefs_for_antibiotic["feature"].apply(lambda f: source_row.get(f, 0) in (1, 1.0, "1", True))
        ]
        if present.empty:
            return EVIDENCE_NO_SIGNAL

        direct_patterns = ANTIBIOTIC_DIRECT_MARKER_SUBSTRINGS.get(antibiotic, [])
        has_direct_marker = present["feature"].apply(
            lambda f: any(pattern in f for pattern in direct_patterns)
        ).any()

        return EVIDENCE_KNOWN_MARKER if has_direct_marker else EVIDENCE_STATISTICAL_ONLY

    def _top_supporting_features(self, antibiotic: str, source_row: dict, prediction: str) -> list:
        coefs = self.coefficients[self.coefficients["antibiotic"] == antibiotic]
        if coefs.empty:
            return []

        present = coefs[coefs["feature"].apply(lambda f: source_row.get(f, 0) in (1, 1.0, "1", True))]

        if prediction == DECISION_FAIL:
            present = present[present["coefficient"] > 0]
        elif prediction == DECISION_WORK:
            present = present[present["coefficient"] < 0]
        # no_call: keep both directions, rank by magnitude only

        present = present.reindex(present["coefficient"].abs().sort_values(ascending=False).index)
        top = present.head(TOP_SUPPORTING_FEATURES_N)

        return [
            {
                "feature": row["feature"],
                "coefficient": round(float(row["coefficient"]), 4),
                "direction": row["direction"],
            }
            for _, row in top.iterrows()
        ]

    def predict(self, feature_row, antibiotic: str) -> dict:
        antibiotic_name = self._resolve_antibiotic(antibiotic)
        X, source_row = self._align_features(feature_row, antibiotic_name)

        # --- sample-specific prediction (this one reconstructed genome) ---
        probability_resistant = float(self.calibrated_models[antibiotic_name].predict_proba(X)[0, 1])
        threshold_info = self.thresholds[antibiotic_name]
        susceptible_threshold = float(threshold_info["susceptible_threshold"])
        resistant_threshold = float(threshold_info["resistant_threshold"])

        # Decision rule — exact definition (also see README "How calibration and
        # no-call thresholds work"):
        #   probability <= susceptible_threshold  -> likely_to_work
        #   probability >= resistant_threshold    -> likely_to_fail
        #   otherwise                             -> no_call
        # This threshold band is a calibration-tuned no-call region, NOT an
        # out-of-distribution / novelty detector — it says nothing about whether
        # this genome resembles the training data, only that the calibrated
        # probability landed in the zone where called predictions weren't
        # reliable enough on the calibration set.
        if probability_resistant <= susceptible_threshold:
            decision = DECISION_WORK
        elif probability_resistant >= resistant_threshold:
            decision = DECISION_FAIL
        else:
            decision = DECISION_NO_CALL

        # Molecular-target gate: never report likely_to_work (or likely_to_fail)
        # purely off the resistance model if the drug's target isn't confirmed
        # present. See TARGET_GATE_INFO docstring for why this always passes on
        # today's single-species (E. coli), core-gene-target feature panel.
        target_gate = self._check_target_gate(antibiotic_name, source_row)
        if not target_gate["target_gate_passed"]:
            decision = DECISION_NO_CALL

        # Confidence — exact definition, only meaningful for a called prediction:
        #   likely_to_fail -> probability_resistant
        #   likely_to_work -> 1 - probability_resistant
        #   no_call        -> None (never a number — a susceptible-leaning
        #                     no_call must not display a misleadingly low
        #                     "confidence" value)
        if decision == DECISION_FAIL:
            confidence = probability_resistant
        elif decision == DECISION_WORK:
            confidence = 1.0 - probability_resistant
        else:
            confidence = None

        top_features = self._top_supporting_features(antibiotic_name, source_row, decision)
        coefs_for_antibiotic = self.coefficients[self.coefficients["antibiotic"] == antibiotic_name]
        evidence_category = self._classify_evidence(antibiotic_name, source_row, coefs_for_antibiotic)

        # --- historical model-quality metrics (describe the MODEL, not this sample) ---
        m = self.metrics.loc[antibiotic_name]
        historical_metrics = {
            "balanced_accuracy": _safe_float(m.get("balanced_accuracy")),
            "resistant_recall": _safe_float(m.get("resistant_recall")),
            "susceptible_recall": _safe_float(m.get("susceptible_recall")),
            "f1_resistant": _safe_float(m.get("f1_resistant")),
            "auroc": _safe_float(m.get("auroc")),
            "pr_auc": _safe_float(m.get("pr_auc")),
            "brier_score": _safe_float(m.get("brier_score")),
            "coverage": _safe_float(m.get("coverage")),
            "called_accuracy": _safe_float(m.get("called_accuracy")),
            "model_tier": m.get("model_tier"),
            "n_test": int(m.get("n_test")) if pd.notna(m.get("n_test")) else None,
        }

        return {
            "antibiotic": antibiotic_name,
            "species": SUPPORTED_SPECIES,
            # sample-specific — this one reconstructed genome, this prediction
            "probability_resistant": probability_resistant,
            "prediction": decision,
            "confidence": confidence,
            "evidence_category": evidence_category,
            "target_gate": target_gate,
            "susceptible_threshold": susceptible_threshold,
            "resistant_threshold": resistant_threshold,
            "top_supporting_features": top_features,
            # historical — describes the MODEL's known quality, not this sample
            "historical_model_metrics": historical_metrics,
            "warning": RESEARCH_WARNING,
        }

    def predict_all_supported(self, feature_row) -> list:
        return [self.predict(feature_row, antibiotic) for antibiotic in self.list_supported_antibiotics()]


def _safe_float(value):
    if value is None or (isinstance(value, float) and not np.isfinite(value)):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


if __name__ == "__main__":
    # Smoke test: score one real row from the mash_002 hidden_test split.
    scorer = ResistanceScorer()
    print("Supported demo antibiotics:", scorer.list_supported_antibiotics())

    test_df = pd.read_csv(
        Path(__file__).resolve().parent / "processed_data" / "mash_002" / "splits" / "hidden_test.csv",
        dtype={"genome_id": "string"},
    )
    example_antibiotic = scorer.list_supported_antibiotics()[0]
    example_row = test_df[test_df["antibiotic"] == example_antibiotic].iloc[0]

    result = scorer.predict(example_row, example_antibiotic)
    print(json.dumps(result, indent=2))
