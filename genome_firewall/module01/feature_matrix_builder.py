"""
Step 3: Feature Matrix Builder
===============================
Transforms AMRFinderPlus output into a binary feature matrix suitable for ML.

The feature matrix has:
  - Rows: one per genome (sample)
  - Columns: one per unique AMR feature (gene or point mutation)
  - Values: 1 if the feature is present, 0 if absent

Feature types extracted:
  1. AMR gene presence (by gene_symbol) — e.g., blaCTX-M-15, mecA, vanA
  2. Point mutations (by gene_symbol + mutation notation) — e.g., gyrA_S83L
  3. Optionally: stress/virulence genes (configurable)

Output format specification:
  - CSV/Parquet with columns: sample_id, feature_1, feature_2, ..., feature_N
  - Companion metadata CSV with feature descriptions
"""

import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class FeatureMatrixResult:
    """Result of feature matrix construction."""
    success: bool
    matrix: Optional[pd.DataFrame] = None
    feature_metadata: Optional[pd.DataFrame] = None
    num_samples: int = 0
    num_features: int = 0
    sparsity: float = 0.0  # fraction of zeros
    error_message: Optional[str] = None

    def summary(self) -> str:
        """Human-readable summary."""
        lines = [f"Feature Matrix: {'SUCCESS' if self.success else 'FAILED'}"]
        if self.success:
            lines.append(f"  Samples:   {self.num_samples}")
            lines.append(f"  Features:  {self.num_features}")
            lines.append(f"  Sparsity:  {self.sparsity:.1%}")
            if (
                self.feature_metadata is not None
                and len(self.feature_metadata) > 0
                and "feature_type" in self.feature_metadata.columns
            ):
                type_counts = self.feature_metadata["feature_type"].value_counts()
                for ftype, count in type_counts.items():
                    lines.append(f"    {ftype}: {count}")
        else:
            lines.append(f"  Error: {self.error_message}")
        return "\n".join(lines)


def _extract_features_from_hits(
    hits_df: pd.DataFrame,
    sample_id: str,
    include_stress: bool = False,
    include_virulence: bool = False,
) -> dict[str, dict]:
    """
    Extract feature presence/absence from a single genome's AMRFinderPlus hits.

    Returns:
        Dict mapping feature_name -> {
            "present": 1,
            "feature_type": "amr_gene" | "point_mutation" | "stress" | "virulence",
            "amr_class": str,
            "amr_subclass": str,
            "element_type": str,
            "method": str,
            "identity_pct": float,
            "coverage_pct": float,
        }
    """
    features = {}

    if hits_df is None or len(hits_df) == 0:
        return features

    for _, row in hits_df.iterrows():
        # Support both v4.2.7 column names and legacy names
        element_type = str(
            row.get("type", row.get("element_type", ""))
        ).upper()
        element_subtype = str(
            row.get("subtype", row.get("element_subtype", ""))
        ).upper()
        gene_symbol = str(
            row.get("element_symbol", row.get("gene_symbol", ""))
        ).strip()
        method = str(row.get("method", "")).strip()

        # Skip entries without a gene symbol
        if not gene_symbol or gene_symbol in ("nan", "NA", ""):
            continue

        # Determine feature type and whether to include
        if element_type == "AMR":
            if element_subtype == "POINT":
                feature_type = "point_mutation"
                # For point mutations, the gene symbol already includes
                # the mutation (e.g., gyrA_S83L)
                feature_name = f"mut_{gene_symbol}"
            else:
                feature_type = "amr_gene"
                feature_name = f"gene_{gene_symbol}"
        elif element_type == "STRESS":
            if not include_stress:
                continue
            feature_type = "stress"
            feature_name = f"stress_{gene_symbol}"
        elif element_type == "VIRULENCE":
            if not include_virulence:
                continue
            feature_type = "virulence"
            feature_name = f"vir_{gene_symbol}"
        else:
            continue  # Skip unknown types

        # Parse identity/coverage as floats (v4.2.7 column names)
        try:
            identity = float(row.get(
                "identity_to_reference", row.get("identity_pct", 0)
            ))
        except (ValueError, TypeError):
            identity = 0.0
        try:
            coverage = float(row.get(
                "coverage_of_reference", row.get("coverage_pct", 0)
            ))
        except (ValueError, TypeError):
            coverage = 0.0

        # Read class/subclass (v4.2.7 uses 'class'/'subclass')
        amr_class = str(row.get("class", row.get("amr_class", "")))
        amr_subclass = str(row.get("subclass", row.get("amr_subclass", "")))

        features[feature_name] = {
            "present": 1,
            "feature_type": feature_type,
            "amr_class": amr_class,
            "amr_subclass": amr_subclass,
            "element_type": element_type,
            "method": method,
            "identity_pct": identity,
            "coverage_pct": coverage,
        }

    return features


def build_feature_matrix(
    amrfinder_results: list,
    sample_ids: Optional[list[str]] = None,
    include_stress: bool = False,
    include_virulence: bool = False,
    min_prevalence: float = 0.0,
    max_prevalence: float = 1.0,
) -> FeatureMatrixResult:
    """
    Build a binary feature matrix from multiple AMRFinderPlus results.

    Args:
        amrfinder_results: List of AMRFinderResult objects (from amrfinder_runner).
        sample_ids: Optional list of sample IDs. If None, derived from file paths.
        include_stress: Include stress response genes as features.
        include_virulence: Include virulence factors as features.
        min_prevalence: Minimum fraction of samples a feature must appear in
                        to be included (filters very rare features).
        max_prevalence: Maximum fraction of samples a feature can appear in
                        (filters features present in nearly all samples —
                        they have no discriminative power).

    Returns:
        FeatureMatrixResult with:
          - matrix: DataFrame (samples × features) of 0/1 values
          - feature_metadata: DataFrame with feature descriptions
    """
    result = FeatureMatrixResult(success=False)

    # Filter to successful results
    valid_results = [r for r in amrfinder_results if r.success]
    if not valid_results:
        result.error_message = "No successful AMRFinderPlus results to build matrix from"
        return result

    # Determine sample IDs
    if sample_ids is None:
        sample_ids = [Path(r.fasta_path).stem for r in valid_results]

    if len(sample_ids) != len(valid_results):
        result.error_message = (
            f"Mismatch: {len(sample_ids)} sample IDs for "
            f"{len(valid_results)} results"
        )
        return result

    # Extract features for each sample
    all_sample_features = {}
    all_feature_metadata = {}

    for sid, amr_result in zip(sample_ids, valid_results):
        features = _extract_features_from_hits(
            amr_result.hits_df,
            sample_id=sid,
            include_stress=include_stress,
            include_virulence=include_virulence,
        )
        all_sample_features[sid] = features

        # Collect metadata for each feature
        for fname, fmeta in features.items():
            if fname not in all_feature_metadata:
                all_feature_metadata[fname] = {
                    "feature_name": fname,
                    "feature_type": fmeta["feature_type"],
                    "amr_class": fmeta["amr_class"],
                    "amr_subclass": fmeta["amr_subclass"],
                    "element_type": fmeta["element_type"],
                }

    # Build the union of all features across all samples
    all_features = sorted(all_feature_metadata.keys())

    if not all_features:
        # Valid case: no AMR features found in any sample
        result.success = True
        result.matrix = pd.DataFrame({"sample_id": sample_ids})
        result.feature_metadata = pd.DataFrame()
        result.num_samples = len(sample_ids)
        result.num_features = 0
        result.sparsity = 1.0
        logger.warning("No AMR features found across any samples")
        return result

    # Build binary matrix
    matrix_data = []
    for sid in sample_ids:
        row = {"sample_id": sid}
        sample_feats = all_sample_features.get(sid, {})
        for feature in all_features:
            row[feature] = 1 if feature in sample_feats else 0
        matrix_data.append(row)

    matrix_df = pd.DataFrame(matrix_data)

    # Apply prevalence filters
    feature_cols = [c for c in matrix_df.columns if c != "sample_id"]
    prevalences = matrix_df[feature_cols].mean()

    features_to_keep = prevalences[
        (prevalences >= min_prevalence) & (prevalences <= max_prevalence)
    ].index.tolist()

    if features_to_keep:
        matrix_df = matrix_df[["sample_id"] + features_to_keep]
    else:
        logger.warning("All features filtered out by prevalence thresholds")
        features_to_keep = []

    # Build feature metadata DataFrame
    metadata_rows = [
        all_feature_metadata[f]
        for f in features_to_keep
        if f in all_feature_metadata
    ]
    feature_metadata_df = pd.DataFrame(metadata_rows)

    # Add prevalence info to metadata
    if len(feature_metadata_df) > 0 and len(features_to_keep) > 0:
        prev_values = prevalences[features_to_keep].values
        feature_metadata_df["prevalence"] = prev_values

    # Compute sparsity
    if features_to_keep:
        binary_values = matrix_df[features_to_keep].values
        sparsity = 1.0 - (np.sum(binary_values) / binary_values.size)
    else:
        sparsity = 1.0

    result.success = True
    result.matrix = matrix_df
    result.feature_metadata = feature_metadata_df
    result.num_samples = len(sample_ids)
    result.num_features = len(features_to_keep)
    result.sparsity = sparsity

    logger.info(
        f"Feature matrix built: {result.num_samples} samples × "
        f"{result.num_features} features (sparsity: {sparsity:.1%})"
    )

    return result


def save_feature_matrix(
    matrix_result: FeatureMatrixResult,
    output_dir: str | Path,
    format: str = "csv",
) -> tuple[str, str]:
    """
    Save the feature matrix and metadata to disk.

    Args:
        matrix_result: FeatureMatrixResult from build_feature_matrix.
        output_dir: Directory to save files.
        format: 'csv' or 'parquet'.

    Returns:
        Tuple of (matrix_path, metadata_path).
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if format == "parquet":
        matrix_path = output_dir / "feature_matrix.parquet"
        metadata_path = output_dir / "feature_metadata.parquet"
        matrix_result.matrix.to_parquet(str(matrix_path), index=False)
        if matrix_result.feature_metadata is not None and len(matrix_result.feature_metadata) > 0:
            matrix_result.feature_metadata.to_parquet(str(metadata_path), index=False)
    else:
        matrix_path = output_dir / "feature_matrix.csv"
        metadata_path = output_dir / "feature_metadata.csv"
        matrix_result.matrix.to_csv(str(matrix_path), index=False)
        if matrix_result.feature_metadata is not None and len(matrix_result.feature_metadata) > 0:
            matrix_result.feature_metadata.to_csv(str(metadata_path), index=False)

    logger.info(f"Saved feature matrix to {matrix_path}")
    logger.info(f"Saved feature metadata to {metadata_path}")

    return str(matrix_path), str(metadata_path)


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)
    print("Feature matrix builder — use via pipeline.py for end-to-end execution")
    print("  Or import: from feature_matrix_builder import build_feature_matrix")
