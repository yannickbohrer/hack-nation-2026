import os
import uuid
import pandas as pd
from pathlib import Path
from typing import Dict, Any
from fastapi import UploadFile

# We can import from genome_firewall because we mounted it and set PYTHONPATH
from genome_firewall.module01.pipeline import run_pipeline_single

def process_fasta_file(file: UploadFile) -> Dict[str, int]:
    """
    Saves an uploaded FASTA file, runs the AMRFinderPlus pipeline on it,
    and returns a dictionary of extracted features mapped to 1 or 0.
    """
    # Create a unique temporary directory for this upload
    job_id = str(uuid.uuid4())
    temp_dir = Path(f"/tmp/genome_firewall_jobs/{job_id}")
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    fasta_path = temp_dir / file.filename
    
    try:
        # 1. Save the uploaded file
        with open(fasta_path, "wb") as buffer:
            buffer.write(file.file.read())
            
        # 2. Run Pipeline 1 (AMRFinderPlus -> Feature Matrix)
        # We output to the same temporary directory
        result = run_pipeline_single(
            fasta_path=fasta_path,
            output_dir=temp_dir,
            organism=None, # or we could try to infer/accept as parameter
            threads=2,
            output_format="csv"
        )
        
        if not result.get("success"):
            raise RuntimeError(f"Pipeline failed: {result.get('error')}")
            
        # 3. Parse the feature matrix
        # The pipeline returns the path to the matrix in result["steps"]["feature_matrix"]["matrix_path"]
        matrix_path = result["steps"]["feature_matrix"]["matrix_path"]
        
        df = pd.read_csv(matrix_path)
        
        # Convert the first row (the only sample) to a dictionary
        # Skip the 'sample_id' column
        if len(df) == 0:
            return {}
            
        feature_dict = {}
        row = df.iloc[0]
        for col in df.columns:
            if col != "sample_id":
                feature_dict[col] = int(row[col])
                
        return feature_dict
        
    finally:
        # Cleanup could happen here, or we can leave it for debugging
        # import shutil; shutil.rmtree(temp_dir, ignore_errors=True)
        pass
