"""
Scoring function proposal for the website/demo integration team.

This is a plain Python module, not a server — the website team wires this
function into whatever backend they build. It only reads artifacts from
model_outputs_demo_mash_002/ (built by build_demo_package.py) and returns
predictions for the demo antibiotics only (cephalothin, ciprofloxacin,
nalidixic acid, trimethoprim/sulfamethoxazole as of this run — see
list_supported_antibiotics()).

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

DECISION_WORK = "likely_to_work"
DECISION_FAIL = "likely_to_fail"
DECISION_NO_CALL = "no_call"

TOP_SUPPORTING_FEATURES_N = 5


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
        if missing:
            raise ValueError(
                f"Missing {len(missing)} required feature(s) for {antibiotic!r}. "
                f"First missing: {missing[:15]}"
            )

        ordered = {}
        for feature in required_features:
            if feature in non_feature_columns:
                continue  # defensive; required_features should never contain these
            value = pd.to_numeric(pd.Series([source[feature]]), errors="raise").iloc[0]
            if pd.isna(value) or not np.isfinite(float(value)):
                raise ValueError(f"Invalid value for feature {feature!r}: {source[feature]!r}")
            ordered[feature] = float(value)

        return pd.DataFrame([ordered], columns=required_features), source

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

        # --- patient-specific prediction ---
        probability_resistant = float(self.calibrated_models[antibiotic_name].predict_proba(X)[0, 1])
        threshold_info = self.thresholds[antibiotic_name]
        susceptible_threshold = float(threshold_info["susceptible_threshold"])
        resistant_threshold = float(threshold_info["resistant_threshold"])

        if probability_resistant <= susceptible_threshold:
            decision = DECISION_WORK
        elif probability_resistant >= resistant_threshold:
            decision = DECISION_FAIL
        else:
            decision = DECISION_NO_CALL

        if decision == DECISION_FAIL:
            confidence = probability_resistant
        elif decision == DECISION_WORK:
            confidence = 1.0 - probability_resistant
        else:
            confidence = None

        top_features = self._top_supporting_features(antibiotic_name, source_row, decision)

        # --- historical model-quality metrics (NOT specific to this patient) ---
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
            # patient-specific — this genome, this prediction
            "probability_resistant": probability_resistant,
            "prediction": decision,
            "confidence": confidence,
            "susceptible_threshold": susceptible_threshold,
            "resistant_threshold": resistant_threshold,
            "top_supporting_features": top_features,
            # historical — describes the MODEL's known quality, not this patient
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
