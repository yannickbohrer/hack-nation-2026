"""
Step 1: FASTA Validator
=======================
Validates that a FASTA file is well-formed and suitable for AMRFinderPlus input.

Checks performed:
  1. File exists and is readable
  2. File is valid FASTA format (parseable by BioPython)
  3. Contains at least one sequence record
  4. All sequences use valid nucleotide alphabet (A, C, G, T, N + IUPAC ambiguity codes)
  5. No empty sequences
  6. Reports basic assembly stats (N50, total length, num contigs, GC content)
"""

import os
import sys
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

from Bio import SeqIO
from Bio.Seq import Seq

logger = logging.getLogger(__name__)

# Valid IUPAC nucleotide characters (upper and lower)
VALID_NUCLEOTIDES = set("ACGTNacgtnRYSWKMBDHVryswkmbdhv")


@dataclass
class FastaValidationResult:
    """Result of FASTA file validation."""
    is_valid: bool
    file_path: str
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    # Assembly statistics (populated only if valid)
    num_records: int = 0
    total_length: int = 0
    shortest_seq: int = 0
    longest_seq: int = 0
    n50: int = 0
    gc_content: float = 0.0

    def summary(self) -> str:
        """Human-readable validation summary."""
        lines = [f"FASTA Validation: {'PASS' if self.is_valid else 'FAIL'}"]
        lines.append(f"  File: {self.file_path}")
        if self.errors:
            lines.append(f"  Errors ({len(self.errors)}):")
            for e in self.errors:
                lines.append(f"    ✗ {e}")
        if self.warnings:
            lines.append(f"  Warnings ({len(self.warnings)}):")
            for w in self.warnings:
                lines.append(f"    ⚠ {w}")
        if self.is_valid:
            lines.append(f"  Records:       {self.num_records}")
            lines.append(f"  Total length:  {self.total_length:,} bp")
            lines.append(f"  Shortest seq:  {self.shortest_seq:,} bp")
            lines.append(f"  Longest seq:   {self.longest_seq:,} bp")
            lines.append(f"  N50:           {self.n50:,} bp")
            lines.append(f"  GC content:    {self.gc_content:.1f}%")
        return "\n".join(lines)


def _compute_n50(lengths: list[int]) -> int:
    """Compute N50 from a list of contig lengths."""
    sorted_lengths = sorted(lengths, reverse=True)
    total = sum(sorted_lengths)
    cumulative = 0
    for length in sorted_lengths:
        cumulative += length
        if cumulative >= total / 2:
            return length
    return 0


def validate_fasta(file_path: str | Path) -> FastaValidationResult:
    """
    Validate a FASTA file for correctness and suitability for AMRFinderPlus.

    Args:
        file_path: Path to the FASTA file to validate.

    Returns:
        FastaValidationResult with validation status, errors, warnings,
        and assembly statistics.
    """
    file_path = Path(file_path)
    result = FastaValidationResult(is_valid=False, file_path=str(file_path))

    # --- Check 1: File exists and is readable ---
    if not file_path.exists():
        result.errors.append(f"File does not exist: {file_path}")
        return result

    if not file_path.is_file():
        result.errors.append(f"Path is not a file: {file_path}")
        return result

    if not os.access(file_path, os.R_OK):
        result.errors.append(f"File is not readable: {file_path}")
        return result

    file_size = file_path.stat().st_size
    if file_size == 0:
        result.errors.append("File is empty (0 bytes)")
        return result

    # --- Check 2 & 3: Parse FASTA and check records ---
    records = []
    try:
        for record in SeqIO.parse(str(file_path), "fasta"):
            records.append(record)
    except Exception as e:
        result.errors.append(f"Failed to parse FASTA: {e}")
        return result

    if len(records) == 0:
        result.errors.append("No sequence records found in FASTA file")
        return result

    # --- Check 4 & 5: Validate sequences ---
    lengths = []
    gc_count = 0
    total_bases = 0

    for i, record in enumerate(records):
        seq_str = str(record.seq)

        # Check for empty sequences
        if len(seq_str) == 0:
            result.errors.append(
                f"Record '{record.id}' (index {i}) has an empty sequence"
            )
            continue

        # Check for valid nucleotide characters
        invalid_chars = set(seq_str) - VALID_NUCLEOTIDES
        if invalid_chars:
            result.errors.append(
                f"Record '{record.id}' contains invalid characters: "
                f"{sorted(invalid_chars)}"
            )
            continue

        length = len(seq_str)
        lengths.append(length)
        seq_upper = seq_str.upper()
        gc_count += seq_upper.count("G") + seq_upper.count("C")
        total_bases += length

        # Warn on very short contigs
        if length < 200:
            result.warnings.append(
                f"Record '{record.id}' is very short ({length} bp) — "
                f"may be below AMRFinderPlus minimum contig length"
            )

    if result.errors:
        return result

    # --- Compute assembly statistics ---
    result.num_records = len(lengths)
    result.total_length = sum(lengths)
    result.shortest_seq = min(lengths)
    result.longest_seq = max(lengths)
    result.n50 = _compute_n50(lengths)
    result.gc_content = (gc_count / total_bases * 100) if total_bases > 0 else 0.0

    # --- Additional warnings for atypical assemblies ---
    # Typical bacterial genome: 0.5 – 12 Mbp
    if result.total_length < 300_000:
        result.warnings.append(
            f"Total assembly length ({result.total_length:,} bp) is unusually small "
            f"for a bacterial genome (expected ≥ 500 kbp)"
        )
    elif result.total_length > 15_000_000:
        result.warnings.append(
            f"Total assembly length ({result.total_length:,} bp) is unusually large "
            f"for a bacterial genome (expected ≤ 12 Mbp)"
        )

    if result.num_records > 500:
        result.warnings.append(
            f"Assembly has {result.num_records} contigs — highly fragmented. "
            f"Consider filtering short contigs."
        )

    result.is_valid = True
    logger.info(f"FASTA validation passed: {file_path}")
    return result


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python fasta_validator.py <path_to_fasta>")
        sys.exit(1)

    logging.basicConfig(level=logging.INFO)
    result = validate_fasta(sys.argv[1])
    print(result.summary())
    sys.exit(0 if result.is_valid else 1)
