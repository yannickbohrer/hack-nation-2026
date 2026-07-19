import json
import os
from pathlib import Path
import joblib
import pandas as pd
import numpy as np
from typing import Dict, Any, List

class PredictionService:
    def __init__(self, models_dir: str = "models"):
        self.models_dir = Path(models_dir)
        self.manifest_path = self.models_dir / "manifest.json"
        self.manifest = None
        self.models = {}
        self.metadata = {}
        
        self.load_models()

    def load_models(self):
        """Load all models and metadata specified in the manifest."""
        if not self.manifest_path.exists():
            print(f"Warning: Manifest not found at {self.manifest_path}")
            return
            
        with open(self.manifest_path, 'r') as f:
            self.manifest = json.load(f)
            
        for abx, info in self.manifest.get("models", {}).items():
            try:
                model_path = self.models_dir / info["model_path"]
                metadata_path = self.models_dir / info["metadata_path"]
                
                if model_path.exists() and metadata_path.exists():
                    self.models[abx] = joblib.load(model_path)
                    with open(metadata_path, 'r') as f:
                        self.metadata[abx] = json.load(f)
                    print(f"Successfully loaded model for {abx}")
                else:
                    print(f"Warning: Files missing for {abx}")
            except Exception as e:
                print(f"Error loading model for {abx}: {e}")

    def predict(self, feature_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Make predictions for all loaded models based on input features.
        feature_dict should map feature names (e.g., 'gene_aac(3)-IId') to 1 or 0.
        """
        if not self.manifest:
            return {"error": "Models not loaded. Please ensure models are trained and exported."}
            
        results = {}
        # Get the global list of feature columns from the manifest
        all_features = self.manifest.get("feature_cols", [])
        
        # Build the input feature vector (1 if feature is present, 0 otherwise)
        # Using a list comprehension to ensure the order matches exactly with what was used in training
        input_vector = [1 if feature_dict.get(feat, 0) == 1 else 0 for feat in all_features]
        X = np.array([input_vector])

        for abx, model in self.models.items():
            meta = self.metadata[abx]
            active_mask = np.array(meta["active_feature_mask"])
            
            # Filter the input vector for active features for this specific model
            X_active = X[:, active_mask]
            
            try:
                prob_resistant = float(model.predict_proba(X_active)[0, 1])
                
                # Check for no-call zone
                nocall_lo = meta["nocall_thresholds"]["lo"]
                nocall_hi = meta["nocall_thresholds"]["hi"]
                
                if nocall_lo <= prob_resistant <= nocall_hi:
                    prediction = "uncertain (no-call)"
                elif prob_resistant > nocall_hi:
                    prediction = "resistant"
                else:
                    prediction = "susceptible"
                    
                results[abx] = {
                    "prediction": prediction,
                    "probability_resistant": prob_resistant,
                    "confidence_score": max(prob_resistant, 1.0 - prob_resistant),
                    "is_calibrated": meta["is_calibrated"]
                }
                
                # Extract explainability info based on the top features and input
                # which features in the input contribute to resistance?
                active_features = meta["active_feature_cols"]
                top_resistance = meta["feature_importances"]["top_resistance_drivers"]
                
                contributing_features = []
                for feat_info in top_resistance:
                    feat_name = feat_info["feature"]
                    if feature_dict.get(feat_name, 0) == 1:
                        contributing_features.append({
                            "feature": feat_name,
                            "weight": feat_info["weight"]
                        })
                        
                results[abx]["top_contributing_features"] = contributing_features
                
            except Exception as e:
                results[abx] = {"error": str(e)}
                
        return results

prediction_service = PredictionService()
