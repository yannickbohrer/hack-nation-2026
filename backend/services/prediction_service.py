import os
import json
from pathlib import Path
from typing import Dict, Any, List
from services.score_resistance import ResistanceScorer

# The path where we placed the model package
PACKAGE_DIR = Path(__file__).resolve().parent.parent / "models" / "model_outputs_demo_mash_002"

class PredictionServiceWrapper:
    def __init__(self):
        self.scorer = None
        try:
            self.scorer = ResistanceScorer(package_dir=PACKAGE_DIR)
        except Exception as e:
            print(f"Error initializing ResistanceScorer: {e}")

    def predict(self, feature_dict: Dict[str, Any]) -> Any:
        if not self.scorer:
            return {"error": "Models not loaded or package missing."}
            
        if not feature_dict:
            return {"error": "Feature input is empty."}
            
        try:
            raw_results = self.scorer.predict_all_supported(feature_dict)
            
            formatted_results = []
            for res in raw_results:
                is_no_call = (res["prediction"] == "no_call")
                metrics = res.get("historical_model_metrics", {})
                
                formatted_res = {
                    "antibiotic": res["antibiotic"],
                    "probability_resistant": res["probability_resistant"],
                    "prediction": res["prediction"],
                    "confidence": res["confidence"],
                    "susceptible_threshold": res["susceptible_threshold"],
                    "resistant_threshold": res["resistant_threshold"],
                    "no_call": is_no_call,
                    "model_status": "demo_candidate",
                    "balanced_accuracy": metrics.get("balanced_accuracy"),
                    "resistant_recall": metrics.get("resistant_recall"),
                    "coverage": metrics.get("coverage"),
                    "called_accuracy": metrics.get("called_accuracy"),
                    "warning": res["warning"]
                }
                formatted_results.append(formatted_res)
                
            return formatted_results
        except ValueError as ve:
            return {"error": f"Value Error: {str(ve)}"}
        except Exception as e:
            return {"error": str(e)}

prediction_service = PredictionServiceWrapper()
