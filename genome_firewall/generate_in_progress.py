import pandas as pd
from pathlib import Path
from module01.feature_matrix_builder import build_feature_matrix
from module01.amrfinder_runner import AMRFinderResult

def generate_preview():
    amr_dir = Path("pipeline-01_outputs/amrfinder_output")
    tsv_files = list(amr_dir.glob("*_amrfinder.tsv"))
    
    print(f"Found {len(tsv_files)} TSV files. Building preview matrix...")
    
    results = []
    for tsv_path in tsv_files:
        genome_id = tsv_path.stem.replace("_amrfinder", "")
        fasta_path = f"dataset/fastas/{genome_id}.fasta"
        
        try:
            if tsv_path.stat().st_size == 0:
                df = pd.DataFrame()
            else:
                df = pd.read_csv(str(tsv_path), sep="\t", dtype=str)
                # Normalize columns
                df.columns = [c.strip().lower().replace(" ", "_").replace("%_", "").lstrip("_") for c in df.columns]
                
            res = AMRFinderResult(
                success=True,
                fasta_path=fasta_path,
                output_tsv_path=str(tsv_path)
            )
            res.hits_df = df
            results.append(res)
        except Exception as e:
            print(f"Error parsing {tsv_path}: {e}")
            
    matrix_result = build_feature_matrix(results)
    
    if matrix_result.success:
        out_path = Path("pipeline-01_outputs/in_progress_feature_matrix.csv")
        matrix_result.matrix.to_csv(out_path, index=False)
        print(f"Success! Preview matrix saved to {out_path}")
        print(f"Shape: {matrix_result.matrix.shape[0]} genomes, {matrix_result.matrix.shape[1]-1} features")
    else:
        print(f"Failed to build matrix: {matrix_result.error_message}")

if __name__ == "__main__":
    generate_preview()
