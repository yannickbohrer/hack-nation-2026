"""
Pipeline 2: Resistance Labels & Data Merger
===========================================
This module processes the BV-BRC Antimicrobial Susceptibility Testing (AST)
data (PATRIC_genomes_AMR.txt) and merges it with the Genome Feature Matrix 
from Pipeline 1 to create the final training dataset for the AI model.

The join is performed on 'Genome ID' <-> 'sample_id'.
"""
import argparse
from pathlib import Path

import pandas as pd
import numpy as np

def build_training_dataset(amr_db_path: str, feature_matrix_path: str, output_path: str, target_antibiotic: str = None):
    # 1. Load BV-BRC Database (Pipeline 2 Source)
    print(f"Loading BV-BRC database from {amr_db_path}...")
    try:
        # Auto-detect separator: CSV uses comma, TSV (PATRIC) uses tab
        sep = "," if amr_db_path.endswith(".csv") else "\t"
        amr_df = pd.read_csv(amr_db_path, sep=sep, dtype=str)
    except Exception as e:
        print(f"Error loading AMR database: {e}")
        return
        
    # Standardize column names (lowercase, replace spaces with underscores)
    amr_df.columns = [c.strip().lower().replace(" ", "_") for c in amr_df.columns]
    
    # 2. Filter for STRICTLY Laboratory-Measured Results (Challenge Requirement)
    # The dataset contains "Computational Method" (AdaBoost AI) predictions which we must ignore!
    if 'evidence' in amr_df.columns:
        initial_len = len(amr_df)
        amr_df = amr_df[amr_df['evidence'] == 'Laboratory Method']
        print(f"Filtered out {initial_len - len(amr_df)} computationally-predicted rows. Kept {len(amr_df)} laboratory-measured results.")
    
    # Clean Genome IDs (remove quotes if present)
    amr_df['genome_id'] = amr_df['genome_id'].str.replace('"', '')
    
    # 3. Filter for valid labels (Susceptible vs Resistant)
    # The column is called 'resistant_phenotype' in the actual dataset
    phenotype_col = 'resistant_phenotype' if 'resistant_phenotype' in amr_df.columns else 'phenotype'
    valid_phenotypes = ['Susceptible', 'Resistant']
    amr_df = amr_df[amr_df[phenotype_col].isin(valid_phenotypes)].copy()
    
    # Convert to binary label: Resistant = 1, Susceptible = 0
    amr_df['is_resistant'] = (amr_df[phenotype_col] == 'Resistant').astype(int)
    
    # 3. Filter by target antibiotic if specified
    if target_antibiotic:
        amr_df = amr_df[amr_df['antibiotic'].str.lower() == target_antibiotic.lower()]
        print(f"Filtered for antibiotic: {target_antibiotic} ({len(amr_df)} records found)")
        
    # We only need Genome ID, Antibiotic, and Resistance Label
    labels_df = amr_df[['genome_id', 'antibiotic', 'is_resistant']].drop_duplicates()
    
    # 4. Load Pipeline 1 Output (Feature Matrix)
    print(f"Loading feature matrix from {feature_matrix_path}...")
    features_df = pd.read_csv(feature_matrix_path, dtype={'sample_id': str})
    
    # 5. THE MERGE (The '+' from the sketch)
    print("Joining features with resistance labels...")
    final_df = pd.merge(
        labels_df, 
        features_df, 
        left_on='genome_id', 
        right_on='sample_id', 
        how='inner'
    )
    
    # Drop the redundant sample_id column
    final_df = final_df.drop(columns=['sample_id'])
    
    if len(final_df) == 0:
        print("Warning: The merge resulted in 0 rows. Check if Genome IDs match between the two files.")
        return
        
    # 6. Save final training set
    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    final_df.to_csv(out_path, index=False)
    
    print("\n" + "="*50)
    print(f"✓ Training Dataset Successfully Built!")
    print(f"  Saved to: {out_path}")
    print(f"  Shape: {final_df.shape[0]} genomes, {final_df.shape[1] - 3} AMR features")
    print("="*50)
    
    # Display preview
    print("\nData Preview:")
    cols_to_show = ['genome_id', 'antibiotic', 'is_resistant'] + list(final_df.columns[3:6])
    print(final_df[cols_to_show].head().to_string(index=False))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Merge BV-BRC labels with pipeline 1 features")
    parser.add_argument("--amr-db", required=True, help="Path to PATRIC_genomes_AMR.txt")
    parser.add_argument("--features", required=True, help="Path to feature_matrix.csv from Pipeline 1")
    parser.add_argument("--output", required=True, help="Path to output final training dataset CSV")
    parser.add_argument("--antibiotic", help="Filter for a specific antibiotic (e.g., 'ampicillin')")
    
    args = parser.parse_args()
    build_training_dataset(args.amr_db, args.features, args.output, args.antibiotic)
