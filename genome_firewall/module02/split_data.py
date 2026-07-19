"""
Splits the final training dataset into Train, Calibration, and Hidden Test sets.
Ensures that all antibiotic tests for a single genome stay together in the same split
to prevent data leakage (a form of grouping by genetic similarity).
"""
import pandas as pd
from sklearn.model_selection import train_test_split
from pathlib import Path

def main():
    print("Loading finalized dataset...")
    df = pd.read_csv("../pipeline-02_outputs/final_training_dataset.csv")
    
    print(f"Total rows before split: {len(df)}")
    
    # We must group by genome_id to ensure a genome's tests aren't split across train/test
    # This simulates "genetic similarity" grouping without full phylogenetic trees.
    unique_genomes = df['genome_id'].unique()
    
    # 60% Train, 20% Calibration, 20% Hidden Test
    # 1. Split off 20% for Hidden Test
    train_calib_genomes, test_genomes = train_test_split(unique_genomes, test_size=0.20, random_state=42)
    
    # 2. Split the remaining 80% into 75/25 to get 60% Train, 20% Calibration
    train_genomes, calib_genomes = train_test_split(train_calib_genomes, test_size=0.25, random_state=42)
    
    train_df = df[df['genome_id'].isin(train_genomes)]
    calib_df = df[df['genome_id'].isin(calib_genomes)]
    test_df = df[df['genome_id'].isin(test_genomes)]
    
    out_dir = Path("../pipeline-02_outputs/splits")
    out_dir.mkdir(exist_ok=True)
    
    train_df.to_csv(out_dir / "train.csv", index=False)
    calib_df.to_csv(out_dir / "calibration.csv", index=False)
    test_df.to_csv(out_dir / "hidden_test.csv", index=False)
    
    print("\nDataset successfully split based on Challenge Rules!")
    print(f"  Train Set:       {len(train_df)} rows ({len(train_genomes)} genomes)")
    print(f"  Calibration Set: {len(calib_df)} rows ({len(calib_genomes)} genomes)")
    print(f"  Hidden Test Set: {len(test_df)} rows ({len(test_genomes)} genomes)")

if __name__ == "__main__":
    main()
