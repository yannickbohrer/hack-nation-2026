"""
Module 01 Pipeline — The Genome Reader
=======================================
End-to-end pipeline: FASTA → Validate → AMRFinderPlus → Binary Feature Matrix

Usage:
  # Single genome
  python pipeline.py --fasta /path/to/genome.fasta --output ./output --organism Escherichia

  # Batch mode (directory of FASTA files)
  python pipeline.py --fasta-dir /path/to/fasta_dir --output ./output --organism Escherichia

  # With prevalence filtering
  python pipeline.py --fasta-dir /path/to/fasta_dir --output ./output \\
      --organism Klebsiella --min-prevalence 0.01 --format parquet
"""

import argparse
import logging
import sys
import json
from pathlib import Path
from datetime import datetime, timezone

from .fasta_validator import validate_fasta, FastaValidationResult
from .amrfinder_runner import run_amrfinder, run_amrfinder_batch, AMRFinderResult
from .feature_matrix_builder import (
    build_feature_matrix,
    save_feature_matrix,
    FeatureMatrixResult,
)

logger = logging.getLogger(__name__)


def run_pipeline_single(
    fasta_path: str | Path,
    output_dir: str | Path,
    organism: str | None = None,
    threads: int = 4,
    include_stress: bool = False,
    include_virulence: bool = False,
    min_prevalence: float = 0.0,
    max_prevalence: float = 1.0,
    output_format: str = "csv",
) -> dict:
    """
    Run the full Module 01 pipeline on a single FASTA file.

    Steps:
      1. Validate FASTA file
      2. Run AMRFinderPlus
      3. Build binary feature matrix (single-sample, useful for inference)

    Returns:
        Dict with pipeline results and paths.
    """
    fasta_path = Path(fasta_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    pipeline_result = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "fasta_path": str(fasta_path),
        "output_dir": str(output_dir),
        "organism": organism,
        "steps": {},
    }

    # ---------------------------------------------------------------
    # Step 1: Validate FASTA
    # ---------------------------------------------------------------
    logger.info(f"Step 1/3: Validating FASTA — {fasta_path.name}")
    validation = validate_fasta(fasta_path)
    print(validation.summary())
    print()

    pipeline_result["steps"]["validation"] = {
        "is_valid": validation.is_valid,
        "num_records": validation.num_records,
        "total_length": validation.total_length,
        "n50": validation.n50,
        "gc_content": validation.gc_content,
        "errors": validation.errors,
        "warnings": validation.warnings,
    }

    if not validation.is_valid:
        logger.error(f"FASTA validation failed for {fasta_path.name}")
        pipeline_result["success"] = False
        pipeline_result["error"] = "FASTA validation failed"
        return pipeline_result

    # ---------------------------------------------------------------
    # Step 2: Run AMRFinderPlus
    # ---------------------------------------------------------------
    logger.info(f"Step 2/3: Running AMRFinderPlus — {fasta_path.name}")
    amr_output_dir = output_dir / "amrfinder_output"
    amr_result = run_amrfinder(
        fasta_path=fasta_path,
        output_dir=amr_output_dir,
        organism=organism,
        threads=threads,
    )
    print(amr_result.summary())
    print()

    pipeline_result["steps"]["amrfinder"] = {
        "success": amr_result.success,
        "output_tsv": amr_result.output_tsv_path,
        "num_amr_genes": amr_result.num_amr_genes,
        "num_point_mutations": amr_result.num_point_mutations,
        "num_stress_genes": amr_result.num_stress_genes,
        "num_virulence_genes": amr_result.num_virulence_genes,
        "error": amr_result.error_message,
    }

    if not amr_result.success:
        logger.error(f"AMRFinderPlus failed for {fasta_path.name}")
        pipeline_result["success"] = False
        pipeline_result["error"] = f"AMRFinderPlus failed: {amr_result.error_message}"
        return pipeline_result

    # ---------------------------------------------------------------
    # Step 3: Build Feature Matrix
    # ---------------------------------------------------------------
    logger.info("Step 3/3: Building binary feature matrix")
    matrix_result = build_feature_matrix(
        amrfinder_results=[amr_result],
        include_stress=include_stress,
        include_virulence=include_virulence,
        min_prevalence=min_prevalence,
        max_prevalence=max_prevalence,
    )
    print(matrix_result.summary())
    print()

    if matrix_result.success:
        matrix_path, metadata_path = save_feature_matrix(
            matrix_result, output_dir / "features", format=output_format
        )
        pipeline_result["steps"]["feature_matrix"] = {
            "success": True,
            "matrix_path": matrix_path,
            "metadata_path": metadata_path,
            "num_samples": matrix_result.num_samples,
            "num_features": matrix_result.num_features,
            "sparsity": matrix_result.sparsity,
        }
    else:
        pipeline_result["steps"]["feature_matrix"] = {
            "success": False,
            "error": matrix_result.error_message,
        }

    pipeline_result["success"] = matrix_result.success

    # Save pipeline metadata
    meta_path = output_dir / "pipeline_result.json"
    with open(meta_path, "w") as f:
        json.dump(pipeline_result, f, indent=2, default=str)
    logger.info(f"Pipeline metadata saved to {meta_path}")

    return pipeline_result


def run_pipeline_batch(
    fasta_dir: str | Path,
    output_dir: str | Path,
    organism: str | None = None,
    threads: int = 4,
    include_stress: bool = False,
    include_virulence: bool = False,
    min_prevalence: float = 0.0,
    max_prevalence: float = 1.0,
    output_format: str = "csv",
) -> dict:
    """
    Run the full Module 01 pipeline on a directory of FASTA files.

    Steps:
      1. Validate all FASTA files
      2. Run AMRFinderPlus on valid files
      3. Build combined binary feature matrix

    Returns:
        Dict with pipeline results and paths.
    """
    fasta_dir = Path(fasta_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    pipeline_result = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "fasta_dir": str(fasta_dir),
        "output_dir": str(output_dir),
        "organism": organism,
        "mode": "batch",
    }

    # Find all FASTA files
    fasta_files = []
    for ext in ["*.fasta", "*.fa", "*.fna", "*.FASTA"]:
        fasta_files.extend(fasta_dir.glob(ext))
    fasta_files = sorted(set(fasta_files))

    if not fasta_files:
        pipeline_result["success"] = False
        pipeline_result["error"] = f"No FASTA files found in {fasta_dir}"
        return pipeline_result

    logger.info(f"Found {len(fasta_files)} FASTA files")

    # ---------------------------------------------------------------
    # Step 1: Validate all FASTA files
    # ---------------------------------------------------------------
    logger.info(f"Step 1/3: Validating {len(fasta_files)} FASTA files")
    validations = []
    valid_fastas = []

    for fasta_file in fasta_files:
        validation = validate_fasta(fasta_file)
        validations.append(validation)
        if validation.is_valid:
            valid_fastas.append(fasta_file)
        else:
            logger.warning(
                f"Skipping invalid FASTA: {fasta_file.name} — "
                f"{'; '.join(validation.errors)}"
            )

    logger.info(
        f"Validation: {len(valid_fastas)}/{len(fasta_files)} files passed"
    )

    if not valid_fastas:
        pipeline_result["success"] = False
        pipeline_result["error"] = "No FASTA files passed validation"
        return pipeline_result

    # ---------------------------------------------------------------
    # Step 2: Run AMRFinderPlus on all valid files
    # ---------------------------------------------------------------
    logger.info(f"Step 2/3: Running AMRFinderPlus on {len(valid_fastas)} genomes")
    amr_output_dir = output_dir / "amrfinder_output"

    amr_results = []
    for i, fasta_file in enumerate(valid_fastas, 1):
        logger.info(f"  [{i}/{len(valid_fastas)}] {fasta_file.name}")
        amr_result = run_amrfinder(
            fasta_path=fasta_file,
            output_dir=amr_output_dir,
            organism=organism,
            threads=threads,
        )
        amr_results.append(amr_result)

    successful_amr = [r for r in amr_results if r.success]
    logger.info(
        f"AMRFinderPlus: {len(successful_amr)}/{len(amr_results)} succeeded"
    )

    if not successful_amr:
        pipeline_result["success"] = False
        pipeline_result["error"] = "No AMRFinderPlus runs succeeded"
        return pipeline_result

    # ---------------------------------------------------------------
    # Step 3: Build combined feature matrix
    # ---------------------------------------------------------------
    logger.info("Step 3/3: Building combined binary feature matrix")
    matrix_result = build_feature_matrix(
        amrfinder_results=successful_amr,
        include_stress=include_stress,
        include_virulence=include_virulence,
        min_prevalence=min_prevalence,
        max_prevalence=max_prevalence,
    )
    print(matrix_result.summary())

    if matrix_result.success:
        matrix_path, metadata_path = save_feature_matrix(
            matrix_result, output_dir / "features", format=output_format
        )
        pipeline_result["steps"] = {
            "validation": {
                "total_files": len(fasta_files),
                "valid_files": len(valid_fastas),
                "invalid_files": len(fasta_files) - len(valid_fastas),
            },
            "amrfinder": {
                "total_runs": len(amr_results),
                "successful_runs": len(successful_amr),
                "failed_runs": len(amr_results) - len(successful_amr),
            },
            "feature_matrix": {
                "success": True,
                "matrix_path": matrix_path,
                "metadata_path": metadata_path,
                "num_samples": matrix_result.num_samples,
                "num_features": matrix_result.num_features,
                "sparsity": matrix_result.sparsity,
            },
        }
        pipeline_result["success"] = True
    else:
        pipeline_result["success"] = False
        pipeline_result["error"] = f"Feature matrix failed: {matrix_result.error_message}"

    # Save pipeline metadata
    meta_path = output_dir / "pipeline_result.json"
    with open(meta_path, "w") as f:
        json.dump(pipeline_result, f, indent=2, default=str)

    return pipeline_result


def main():
    parser = argparse.ArgumentParser(
        description="Module 01 — The Genome Reader: FASTA → Validate → AMRFinderPlus → Feature Matrix",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Single genome
  python -m module01_genome_reader.pipeline \\
      --fasta genome.fasta --output ./output --organism Escherichia

  # Batch mode
  python -m module01_genome_reader.pipeline \\
      --fasta-dir ./genomes/ --output ./output --organism Klebsiella

  # With filtering and parquet output
  python -m module01_genome_reader.pipeline \\
      --fasta-dir ./genomes/ --output ./output \\
      --organism Staphylococcus_aureus \\
      --min-prevalence 0.01 --format parquet
        """,
    )

    # Input (mutually exclusive)
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "--fasta", type=str,
        help="Path to a single FASTA file"
    )
    input_group.add_argument(
        "--fasta-dir", type=str,
        help="Path to directory containing FASTA files (batch mode)"
    )

    # Required
    parser.add_argument(
        "--output", type=str, required=True,
        help="Output directory for results"
    )

    # Optional
    parser.add_argument(
        "--organism", type=str, default=None,
        help="Organism name for AMRFinderPlus point mutation detection "
             "(e.g., Escherichia, Klebsiella, Staphylococcus_aureus, Salmonella)"
    )
    parser.add_argument(
        "--threads", type=int, default=4,
        help="Number of CPU threads for AMRFinderPlus (default: 4)"
    )
    parser.add_argument(
        "--include-stress", action="store_true",
        help="Include stress response genes in feature matrix"
    )
    parser.add_argument(
        "--include-virulence", action="store_true",
        help="Include virulence factors in feature matrix"
    )
    parser.add_argument(
        "--min-prevalence", type=float, default=0.0,
        help="Minimum feature prevalence to include (default: 0.0)"
    )
    parser.add_argument(
        "--max-prevalence", type=float, default=1.0,
        help="Maximum feature prevalence to include (default: 1.0)"
    )
    parser.add_argument(
        "--format", type=str, choices=["csv", "parquet"], default="csv",
        help="Output format for feature matrix (default: csv)"
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="Enable verbose logging"
    )

    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    # Run pipeline
    if args.fasta:
        result = run_pipeline_single(
            fasta_path=args.fasta,
            output_dir=args.output,
            organism=args.organism,
            threads=args.threads,
            include_stress=args.include_stress,
            include_virulence=args.include_virulence,
            min_prevalence=args.min_prevalence,
            max_prevalence=args.max_prevalence,
            output_format=args.format,
        )
    else:
        result = run_pipeline_batch(
            fasta_dir=args.fasta_dir,
            output_dir=args.output,
            organism=args.organism,
            threads=args.threads,
            include_stress=args.include_stress,
            include_virulence=args.include_virulence,
            min_prevalence=args.min_prevalence,
            max_prevalence=args.max_prevalence,
            output_format=args.format,
        )

    # Print final status
    print("\n" + "=" * 60)
    if result.get("success"):
        print("✓ Pipeline completed successfully!")
        steps = result.get("steps", {})
        fm = steps.get("feature_matrix", {})
        if fm.get("matrix_path"):
            print(f"  Feature matrix: {fm['matrix_path']}")
            print(f"  Metadata:       {fm.get('metadata_path', 'N/A')}")
            print(f"  Dimensions:     {fm['num_samples']} samples × {fm['num_features']} features")
    else:
        print(f"✗ Pipeline failed: {result.get('error', 'Unknown error')}")
    print("=" * 60)

    sys.exit(0 if result.get("success") else 1)


if __name__ == "__main__":
    main()
