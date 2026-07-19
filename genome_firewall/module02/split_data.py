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
    
    print("Loading cluster mapping (using 0.02 cutoff)...")
    cluster_df = pd.read_csv("../pipeline-02_outputs/mash_cluster_002.csv")
    
    # Many-to-one merge of cluster mapping onto the dataset
    df = df.merge(cluster_df, on='genome_id', how='inner')
    
    # Group by cluster_id to prevent genetic leakage
    unique_clusters = df['cluster_id'].unique()
    
    # 60% Train, 20% Calibration, 20% Hidden Test
    # 1. Split off 20% for Hidden Test
    train_calib_clusters, test_clusters = train_test_split(unique_clusters, test_size=0.20, random_state=42)
    
    # 2. Split the remaining 80% into 75/25 to get 60% Train, 20% Calibration
    train_clusters, calib_clusters = train_test_split(train_calib_clusters, test_size=0.25, random_state=42)
    
    train_df = df[df['cluster_id'].isin(train_clusters)]
    calib_df = df[df['cluster_id'].isin(calib_clusters)]
    test_df = df[df['cluster_id'].isin(test_clusters)]
    
    out_dir = Path("../pipeline-02_outputs/splits")
    out_dir.mkdir(exist_ok=True)
    
    train_df.to_csv(out_dir / "train.csv", index=False)
    calib_df.to_csv(out_dir / "calibration.csv", index=False)
    test_df.to_csv(out_dir / "hidden_test.csv", index=False)
    
    print("\nDataset successfully split based on Challenge Rules (Cluster-Aware)!")
    print(f"  Train Set:       {len(train_df)} rows ({train_df['genome_id'].nunique()} genomes in {len(train_clusters)} clusters)")
    print(f"  Calibration Set: {len(calib_df)} rows ({calib_df['genome_id'].nunique()} genomes in {len(calib_clusters)} clusters)")
    print(f"  Hidden Test Set: {len(test_df)} rows ({test_df['genome_id'].nunique()} genomes in {len(test_clusters)} clusters)")

if __name__ == "__main__":
    main()
