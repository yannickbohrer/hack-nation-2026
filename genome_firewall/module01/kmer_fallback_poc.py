"""
PoC: k-mer Fallback Feature Extractor (Vision Demo)
=====================================================
A lightweight proof-of-concept that extracts k-mer frequency features directly
from a FASTA file — no external annotation tool required.

PURPOSE:
  This is NOT a replacement for AMRFinderPlus. AMRFinderPlus is the gold standard
  and the primary tool in our pipeline. This PoC exists solely to demonstrate the
  *vision* of a fully self-contained AI-based feature extractor that could:
    - Run without installing external bioinformatics tools
    - Serve as a fallback when AMRFinderPlus is unavailable
    - Capture novel resistance signals not in curated databases

HOW IT WORKS:
  1. Reads a FASTA file
  2. Counts k-mer frequencies (default k=6, yielding 4^6 = 4096 features)
  3. Normalizes to relative frequencies
  4. Outputs a dense numerical feature vector per genome

LIMITATIONS (why this is a PoC, not production):
  - No biological interpretation — features are opaque k-mer frequencies
  - No gene-level explanations (required by the challenge for Module 03)
  - Likely lower accuracy than curated AMR gene/mutation features
  - Feature space grows as 4^k — larger k is more expressive but sparse
"""

import logging
from pathlib import Path
from itertools import product
from collections import Counter
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd
from Bio import SeqIO

logger = logging.getLogger(__name__)


@dataclass
class KmerFeatureResult:
    """Result of k-mer feature extraction."""
    success: bool
    sample_id: str
    features: Optional[np.ndarray] = None
    feature_names: Optional[list[str]] = None
    k: int = 6
    error_message: Optional[str] = None


def _count_kmers(sequence: str, k: int) -> Counter:
    """Count k-mer occurrences in a DNA sequence."""
    sequence = sequence.upper()
    counts = Counter()
    for i in range(len(sequence) - k + 1):
        kmer = sequence[i:i + k]
        # Skip k-mers containing N or other ambiguity codes
        if all(c in "ACGT" for c in kmer):
            counts[kmer] += 1
    return counts


def _get_all_kmers(k: int) -> list[str]:
    """Generate all possible k-mers in lexicographic order."""
    return ["".join(combo) for combo in product("ACGT", repeat=k)]


def extract_kmer_features(
    fasta_path: str | Path,
    k: int = 6,
) -> KmerFeatureResult:
    """
    Extract normalized k-mer frequency features from a FASTA file.

    Args:
        fasta_path: Path to FASTA file.
        k: k-mer length (default 6 → 4096 features).

    Returns:
        KmerFeatureResult with feature vector.
    """
    fasta_path = Path(fasta_path)
    sample_id = fasta_path.stem

    result = KmerFeatureResult(
        success=False, sample_id=sample_id, k=k
    )

    try:
        # Count k-mers across all contigs
        total_counts = Counter()
        for record in SeqIO.parse(str(fasta_path), "fasta"):
            total_counts += _count_kmers(str(record.seq), k)

        # Build feature vector in canonical order
        all_kmers = _get_all_kmers(k)
        total = sum(total_counts.values())

        if total == 0:
            result.error_message = "No valid k-mers found"
            return result

        # Normalize to relative frequencies
        features = np.array(
            [total_counts.get(kmer, 0) / total for kmer in all_kmers],
            dtype=np.float32,
        )

        result.success = True
        result.features = features
        result.feature_names = [f"kmer_{kmer}" for kmer in all_kmers]

        logger.info(
            f"Extracted {len(all_kmers)} k-mer features from {sample_id} "
            f"({total:,} total k-mers counted)"
        )

    except Exception as e:
        result.error_message = f"k-mer extraction failed: {e}"

    return result


def extract_kmer_features_batch(
    fasta_paths: list[str | Path],
    k: int = 6,
) -> pd.DataFrame:
    """
    Extract k-mer features for multiple FASTA files into a DataFrame.

    Returns:
        DataFrame with columns: sample_id, kmer_AAAA, kmer_AAAC, ...
    """
    all_kmers = _get_all_kmers(k)
    feature_cols = [f"kmer_{kmer}" for kmer in all_kmers]

    rows = []
    for fasta_path in fasta_paths:
        result = extract_kmer_features(fasta_path, k=k)
        if result.success:
            row = {"sample_id": result.sample_id}
            row.update(dict(zip(feature_cols, result.features)))
            rows.append(row)
        else:
            logger.warning(f"Skipped {fasta_path}: {result.error_message}")

    return pd.DataFrame(rows)


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)
    print("=" * 60)
    print("PoC: k-mer Fallback Feature Extractor")
    print("NOTE: This is a vision demo — AMRFinderPlus is the")
    print("      primary tool for the Genome Firewall pipeline.")
    print("=" * 60)

    if len(sys.argv) < 2:
        print("\nUsage: python kmer_fallback_poc.py <fasta_path> [k]")
        sys.exit(1)

    k = int(sys.argv[2]) if len(sys.argv) > 2 else 6
    result = extract_kmer_features(sys.argv[1], k=k)

    if result.success:
        print(f"\n✓ Extracted {len(result.features)} features (k={k})")
        print(f"  Non-zero features: {np.count_nonzero(result.features)}")
        print(f"  Max frequency:     {result.features.max():.6f}")
        print(f"  Feature vector L2: {np.linalg.norm(result.features):.6f}")
    else:
        print(f"\n✗ Failed: {result.error_message}")
