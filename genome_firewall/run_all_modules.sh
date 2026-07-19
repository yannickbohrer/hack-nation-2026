#!/bin/bash
set -e
echo "========================================="
echo "1. Running Pipeline 1 (AMRFinderPlus) on all genomes..."
echo "========================================="
eval "$(/home/yannick/miniconda3/bin/conda shell.bash hook)"
conda activate amrfinder

# Run Pipeline 1 in batch mode
/home/yannick/Code/hack-nation/genome_firewall/.venv/bin/python -m module01.pipeline --fasta-dir dataset/fastas --output pipeline-01_outputs --organism Escherichia

echo "========================================="
echo "2. Running Pipeline 2 (Merge with BV-BRC Labels)..."
echo "========================================="
conda deactivate || true

/home/yannick/Code/hack-nation/genome_firewall/.venv/bin/python module02_pipeline2.py --amr-db dataset/BVBRC_genome_amr_ecoli_full.csv --features pipeline-01_outputs/features/feature_matrix.csv --output pipeline-02_outputs/final_training_dataset.csv

echo "========================================="
echo "3. Splitting Dataset (Train / Calib / Test)..."
echo "========================================="
cd module02
/home/yannick/Code/hack-nation/genome_firewall/.venv/bin/python split_data.py

echo "Done! The challenge dataset is fully prepared."
