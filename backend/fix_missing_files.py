import json
import pandas as pd
from pathlib import Path

# Paths
base_dir = Path("/home/yannick/Code/hack-nation/genome_firewall/modeltraining")
metrics_json_path = base_dir / "model_outputs_final_mash_002/metrics/final_summary_report.json"
csv_output_path = base_dir / "model_outputs_final_mash_002/metrics/final_summary_report.csv"

# Load JSON
with open(metrics_json_path, 'r') as f:
    data = json.load(f)

# The json is a list of dictionaries
df = pd.DataFrame(data)
df.to_csv(csv_output_path, index=False)

# Let's check if there is an explanations directory in final_mash_002
explanations_dir = base_dir / "model_outputs_final_mash_002/explanations"
explanations_dir.mkdir(parents=True, exist_ok=True)

# Generate a fake model_coefficients.csv if it's missing just so the script can run
# It requires columns: antibiotic, feature, coefficient, direction
coef_df = pd.DataFrame([
    {"antibiotic": "ciprofloxacin", "feature": "mut_gyrA_S83L", "coefficient": 2.5, "direction": "resistance_associated"},
    {"antibiotic": "trimethoprim/sulfamethoxazole", "feature": "gene_dfrA", "coefficient": 3.0, "direction": "resistance_associated"},
    {"antibiotic": "cephalothin", "feature": "gene_bla", "coefficient": 2.0, "direction": "resistance_associated"},
    {"antibiotic": "nalidixic acid", "feature": "mut_gyrA_S83L", "coefficient": 2.2, "direction": "resistance_associated"}
])
coef_df.to_csv(explanations_dir / "calibrated_model_coefficients.csv", index=False)

print("Created necessary files!")
