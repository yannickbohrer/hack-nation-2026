"""
Module 01 — The Genome Reader
==============================
FASTA → Validate → AMRFinderPlus → Binary Feature Matrix

This module uses AMRFinderPlus (NCBI, public-domain) as the primary and
default annotation tool. AMRFinderPlus is NOT replaced — it is the gold
standard for identifying AMR genes and resistance-associated mutations.

Pipeline steps:
  1. fasta_validator   — Validate FASTA correctness and assembly quality
  2. amrfinder_runner  — Run AMRFinderPlus, parse TSV output
  3. feature_matrix_builder — Transform hits into binary feature matrix

Optional:
  - kmer_fallback_poc  — PoC k-mer feature extractor (vision demo only)
"""
