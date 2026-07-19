import pandas as pd
import numpy as np
from scipy.spatial.distance import squareform
from scipy.cluster.hierarchy import linkage, fcluster
from pathlib import Path
import time
import subprocess

def run_mash():
    print("Finding FASTA files...")
    fasta_dir = Path("../dataset/fastas")
    fastas = list(fasta_dir.glob("*.fasta"))
    
    list_file = Path("fasta_list.txt")
    with open(list_file, "w") as f:
        for fasta in fastas:
            f.write(f"{fasta.absolute()}\n")
            
    msh_file = Path("../pipeline-02_outputs/all_genomes.msh")
    dist_file = Path("../pipeline-02_outputs/distances.tsv")
    msh_file.parent.mkdir(parents=True, exist_ok=True)
    
    if not msh_file.exists():
        print("Running mash sketch...")
        subprocess.run(["mash", "sketch", "-l", str(list_file), "-o", str(msh_file)], check=True)
    
    if not dist_file.exists():
        print("Running mash dist...")
        with open(dist_file, "w") as f:
            subprocess.run(["mash", "dist", str(msh_file), str(msh_file)], stdout=f, check=True)
            
    return dist_file

def compute_clusters(dist_file):
    print("Loading Mash distances...")
    # Mash dist format: reference-id, query-id, distance, p-value, shared-hashes
    df = pd.read_csv(dist_file, sep="\t", header=None, names=["ref", "query", "dist", "pval", "hashes"])
    
    # Extract genome_id from path
    df['ref_id'] = df['ref'].apply(lambda x: Path(x).stem)
    df['query_id'] = df['query'].apply(lambda x: Path(x).stem)
    
    # Pivot to distance matrix
    print("Building distance matrix...")
    dist_matrix = df.pivot(index='ref_id', columns='query_id', values='dist').fillna(0)
    
    genomes = dist_matrix.index.tolist()
    # Convert symmetric square matrix to condensed form required by scipy
    condensed_dist = squareform(dist_matrix.values, checks=False)
    
    print("Performing hierarchical clustering (Average linkage)...")
    Z = linkage(condensed_dist, method='average')
    
    for cutoff in [0.05, 0.02]:
        print(f"\nProcessing cutoff: {cutoff}")
        labels = fcluster(Z, t=cutoff, criterion='distance')
        
        cluster_df = pd.DataFrame({
            'genome_id': genomes,
            'cluster_id': labels
        })
        
        num_clusters = cluster_df['cluster_id'].nunique()
        counts = cluster_df['cluster_id'].value_counts()
        singletons = (counts == 1).sum()
        median_size = counts.median()
        max_size = counts.max()
        
        print(f"  Number of clusters: {num_clusters}")
        print(f"  Singleton count: {singletons}")
        print(f"  Median cluster size: {median_size:.1f}")
        print(f"  Maximum cluster size: {max_size}")
        print(f"  Percentage mapped: 100.0% (all genomes in matrix)")
        
        out_name = f"../pipeline-02_outputs/mash_cluster_{str(cutoff).replace('.', '')}.csv"
        cluster_df.to_csv(out_name, index=False)
        print(f"  Saved mapping to {out_name}")

if __name__ == "__main__":
    start_time = time.time()
    dist_file = run_mash()
    compute_clusters(dist_file)
    print(f"\nFinished in {time.time() - start_time:.2f} seconds.")
