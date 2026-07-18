"""
Step 2: AMRFinderPlus Runner
=============================
Runs AMRFinderPlus on a validated FASTA file and parses the output.

AMRFinderPlus identifies:
  - Acquired antimicrobial resistance (AMR) genes
  - Point mutations associated with resistance
  - Stress response genes
  - Virulence factors

The output is a structured TSV with columns describing each hit:
  Protein id, Gene symbol, Sequence name, Scope, Element type,
  Element subtype, Class, Subclass, Method, Target length,
  Reference length, % Coverage, % Identity, Accession of closest seq,
  Name of closest seq, HMM id, HMM description
"""

import subprocess
import logging
import shutil
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

# Expected columns in AMRFinderPlus output (v4.2.7)
# Raw headers: Name, Protein id, Contig id, Start, Stop, Strand,
# Element symbol, Element name, Scope, Type, Subtype, Class, Subclass,
# Method, Target length, Reference sequence length, % Coverage of reference,
# % Identity to reference, Alignment length, Closest reference accession,
# Closest reference name, HMM accession, HMM description
AMRFINDER_COLUMNS = [
    "name",
    "protein_id",
    "contig_id",
    "start",
    "stop",
    "strand",
    "element_symbol",
    "element_name",
    "scope",
    "type",
    "subtype",
    "class",
    "subclass",
    "method",
    "target_length",
    "reference_sequence_length",
    "coverage_of_reference",
    "identity_to_reference",
    "alignment_length",
    "closest_reference_accession",
    "closest_reference_name",
    "hmm_accession",
    "hmm_description",
]


@dataclass
class AMRFinderResult:
    """Result of running AMRFinderPlus on a single genome."""
    success: bool
    fasta_path: str
    output_tsv_path: Optional[str] = None
    hits_df: Optional[pd.DataFrame] = None
    num_amr_genes: int = 0
    num_point_mutations: int = 0
    num_stress_genes: int = 0
    num_virulence_genes: int = 0
    error_message: Optional[str] = None
    stderr_output: Optional[str] = None

    def summary(self) -> str:
        """Human-readable summary of AMRFinderPlus results."""
        lines = [f"AMRFinderPlus: {'SUCCESS' if self.success else 'FAILED'}"]
        lines.append(f"  Input: {self.fasta_path}")
        if self.success:
            lines.append(f"  Output TSV: {self.output_tsv_path}")
            total = (
                self.num_amr_genes + self.num_point_mutations
                + self.num_stress_genes + self.num_virulence_genes
            )
            lines.append(f"  Total hits:        {total}")
            lines.append(f"    AMR genes:       {self.num_amr_genes}")
            lines.append(f"    Point mutations: {self.num_point_mutations}")
            lines.append(f"    Stress genes:    {self.num_stress_genes}")
            lines.append(f"    Virulence genes: {self.num_virulence_genes}")
        else:
            lines.append(f"  Error: {self.error_message}")
        return "\n".join(lines)


def _find_amrfinder_binary() -> str:
    """
    Locate the amrfinder binary. Tries:
      1. conda env 'amrfinder'
      2. PATH
    """
    # Try conda env first
    conda_path = Path.home() / "miniconda3" / "envs" / "amrfinder" / "bin" / "amrfinder"
    if conda_path.exists():
        return str(conda_path)

    # Fall back to PATH
    which = shutil.which("amrfinder")
    if which:
        return which

    raise FileNotFoundError(
        "AMRFinderPlus binary not found. Install via: "
        "conda install -c bioconda -c conda-forge ncbi-amrfinderplus"
    )


def run_amrfinder(
    fasta_path: str | Path,
    output_dir: str | Path,
    organism: Optional[str] = None,
    threads: int = 4,
    ident_min: Optional[float] = None,
    coverage_min: Optional[float] = None,
) -> AMRFinderResult:
    """
    Run AMRFinderPlus on a FASTA file.

    Args:
        fasta_path: Path to the input FASTA file (nucleotide assembly).
        output_dir: Directory to write output TSV files.
        organism: Optional organism name for organism-specific point mutation
                  detection (e.g., 'Escherichia', 'Klebsiella',
                  'Staphylococcus_aureus', 'Salmonella').
        threads: Number of CPU threads to use.
        ident_min: Minimum % identity threshold (default: AMRFinderPlus default).
        coverage_min: Minimum % coverage threshold (default: AMRFinderPlus default).

    Returns:
        AMRFinderResult with parsed hits DataFrame and summary statistics.
    """
    fasta_path = Path(fasta_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Output file path
    stem = fasta_path.stem
    output_tsv = output_dir / f"{stem}_amrfinder.tsv"

    result = AMRFinderResult(success=False, fasta_path=str(fasta_path))

    try:
        amrfinder_bin = _find_amrfinder_binary()
    except FileNotFoundError as e:
        result.error_message = str(e)
        return result

    # Build command
    cmd = [
        amrfinder_bin,
        "--nucleotide", str(fasta_path),
        "--output", str(output_tsv),
        "--threads", str(threads),
        "--plus",  # Include stress/virulence genes
        "--name", stem,  # Sample name for output
    ]

    if organism:
        cmd.extend(["--organism", organism])

    if ident_min is not None:
        cmd.extend(["--ident_min", str(ident_min)])

    if coverage_min is not None:
        cmd.extend(["--coverage_min", str(coverage_min)])

    logger.info(f"Running AMRFinderPlus: {' '.join(cmd)}")

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,  # 10 minute timeout per genome
        )

        result.stderr_output = proc.stderr

        if proc.returncode != 0:
            result.error_message = (
                f"AMRFinderPlus exited with code {proc.returncode}: "
                f"{proc.stderr[:500]}"
            )
            return result

    except subprocess.TimeoutExpired:
        result.error_message = "AMRFinderPlus timed out after 600 seconds"
        return result
    except Exception as e:
        result.error_message = f"Failed to run AMRFinderPlus: {e}"
        return result

    # Parse output TSV
    try:
        if not output_tsv.exists() or output_tsv.stat().st_size == 0:
            # Valid case: no hits found
            result.success = True
            result.output_tsv_path = str(output_tsv)
            result.hits_df = pd.DataFrame(columns=AMRFINDER_COLUMNS)
            return result

        df = pd.read_csv(str(output_tsv), sep="\t", dtype=str)
        # Normalize column names: strip, lowercase, spaces→underscores,
        # remove leading % and _
        normalized = []
        for c in df.columns:
            c = c.strip().lower().replace(" ", "_").replace("%_", "")
            # Remove leading underscores
            c = c.lstrip("_")
            normalized.append(c)
        df.columns = normalized

        result.hits_df = df
        result.output_tsv_path = str(output_tsv)
        result.success = True

        # Count by element type (column is 'type' in v4.2.7)
        type_col = "type" if "type" in df.columns else "element_type"
        subtype_col = "subtype" if "subtype" in df.columns else "element_subtype"

        if type_col in df.columns:
            type_counts = df[type_col].value_counts()
            result.num_amr_genes = int(type_counts.get("AMR", 0))
            result.num_stress_genes = int(type_counts.get("STRESS", 0))
            result.num_virulence_genes = int(type_counts.get("VIRULENCE", 0))

        if subtype_col in df.columns:
            subtype_counts = df[subtype_col].value_counts()
            result.num_point_mutations = int(subtype_counts.get("POINT", 0))

        logger.info(f"AMRFinderPlus found {len(df)} hits for {stem}")

    except Exception as e:
        result.error_message = f"Failed to parse AMRFinderPlus output: {e}"
        result.success = False

    return result


def run_amrfinder_batch(
    fasta_dir: str | Path,
    output_dir: str | Path,
    organism: Optional[str] = None,
    threads: int = 4,
    file_pattern: str = "*.fasta",
) -> list[AMRFinderResult]:
    """
    Run AMRFinderPlus on all FASTA files in a directory.

    Args:
        fasta_dir: Directory containing FASTA files.
        output_dir: Directory for output TSV files.
        organism: Optional organism name for point mutation detection.
        threads: Number of CPU threads per run.
        file_pattern: Glob pattern for FASTA files.

    Returns:
        List of AMRFinderResult objects.
    """
    fasta_dir = Path(fasta_dir)
    fasta_files = sorted(fasta_dir.glob(file_pattern))

    # Also check common extensions
    if not fasta_files:
        for ext in ["*.fa", "*.fna", "*.fasta", "*.FASTA"]:
            fasta_files.extend(fasta_dir.glob(ext))
        fasta_files = sorted(set(fasta_files))

    if not fasta_files:
        logger.warning(f"No FASTA files found in {fasta_dir}")
        return []

    logger.info(f"Running AMRFinderPlus on {len(fasta_files)} FASTA files")

    results = []
    for i, fasta_file in enumerate(fasta_files, 1):
        logger.info(f"Processing [{i}/{len(fasta_files)}]: {fasta_file.name}")
        result = run_amrfinder(
            fasta_path=fasta_file,
            output_dir=output_dir,
            organism=organism,
            threads=threads,
        )
        results.append(result)

    successes = sum(1 for r in results if r.success)
    logger.info(f"AMRFinderPlus batch complete: {successes}/{len(results)} succeeded")

    return results


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)

    if len(sys.argv) < 3:
        print("Usage: python amrfinder_runner.py <fasta_path> <output_dir> [organism]")
        print("  organism examples: Escherichia, Klebsiella, Staphylococcus_aureus")
        sys.exit(1)

    organism = sys.argv[3] if len(sys.argv) > 3 else None
    result = run_amrfinder(sys.argv[1], sys.argv[2], organism=organism)
    print(result.summary())

    if result.success and result.hits_df is not None and len(result.hits_df) > 0:
        print("\nTop hits:")
        display_cols = [
            c for c in ["gene_symbol", "sequence_name", "element_type",
                        "element_subtype", "amr_class", "amr_subclass",
                        "identity_pct", "coverage_pct", "method"]
            if c in result.hits_df.columns
        ]
        print(result.hits_df[display_cols].to_string(index=False))

    sys.exit(0 if result.success else 1)
