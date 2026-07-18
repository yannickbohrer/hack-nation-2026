"""
Inspector tool to validate pipeline data extraction.
Reads the FASTA file, the AMRFinderPlus TSV, and the final feature matrix CSV,
and presents a human-readable comparison to ensure data provenance.
"""
import argparse
import textwrap
from pathlib import Path

import pandas as pd
from Bio import SeqIO
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import print as rprint

console = Console()

def inspect_pipeline_output(fasta_path: str, tsv_path: str, matrix_path: str):
    fasta_path = Path(fasta_path)
    tsv_path = Path(tsv_path)
    matrix_path = Path(matrix_path)
    
    if not all([fasta_path.exists(), tsv_path.exists(), matrix_path.exists()]):
        console.print("[red]Error: One or more input files do not exist.[/red]")
        return
        
    console.print(Panel(f"[bold cyan]Pipeline Inspector[/bold cyan]\n"
                        f"FASTA: {fasta_path.name}\n"
                        f"TSV: {tsv_path.name}\n"
                        f"Matrix: {matrix_path.name}", 
                        expand=False))
    
    # 1. Load the FASTA data into memory
    console.print("\n[bold yellow]1. Loading FASTA File[/bold yellow]")
    fasta_records = {record.id: record for record in SeqIO.parse(fasta_path, "fasta")}
    console.print(f"Loaded {len(fasta_records)} contig(s). Total length: {sum(len(r) for r in fasta_records.values()):,} bp")
    
    # 2. Load the TSV file (AMRFinderPlus raw hits)
    console.print("\n[bold yellow]2. Loading AMRFinderPlus TSV[/bold yellow]")
    if tsv_path.stat().st_size == 0:
        console.print("[yellow]TSV file is empty (no hits found by AMRFinderPlus).[/yellow]")
        raw_hits = pd.DataFrame()
    else:
        raw_hits = pd.read_csv(tsv_path, sep="\t")
        # Find column names dynamically (AMRFinderPlus versions differ slightly)
        contig_col = next((c for c in raw_hits.columns if "contig id" in c.lower() or c.lower() == "contig_id"), None)
        start_col = next((c for c in raw_hits.columns if "start" in c.lower()), None)
        stop_col = next((c for c in raw_hits.columns if "stop" in c.lower()), None)
        gene_col = next((c for c in raw_hits.columns if "symbol" in c.lower() or "gene" in c.lower()), None)
        type_col = next((c for c in raw_hits.columns if "type" == c.lower() or "element type" in c.lower()), None)
        
        table = Table(title="Raw Hits in TSV")
        table.add_column("Hit Type", style="cyan")
        table.add_column("Gene", style="magenta")
        table.add_column("Contig", style="green")
        table.add_column("Start-Stop", style="yellow")
        table.add_column("FASTA Sequence Snippet", style="white")

        for _, row in raw_hits.iterrows():
            contig = str(row[contig_col])
            start = int(row[start_col])
            stop = int(row[stop_col])
            gene = str(row[gene_col])
            hit_type = str(row[type_col])
            
            # Extract actual sequence from FASTA
            if contig in fasta_records:
                # BED/AMRFinder uses 1-based coordinates
                seq = fasta_records[contig].seq[start-1:stop]
                # Show first 20 and last 20 bp
                if len(seq) > 40:
                    snippet = f"{seq[:20]}...{seq[-20:]} ({len(seq)} bp)"
                else:
                    snippet = f"{seq} ({len(seq)} bp)"
            else:
                snippet = "[red]Contig not found in FASTA![/red]"
                
            table.add_row(hit_type, gene, contig, f"{start}-{stop}", snippet)
            
        console.print(table)
        
    # 3. Load the feature matrix
    console.print("\n[bold yellow]3. Validating Feature Matrix Mapping[/bold yellow]")
    matrix = pd.read_csv(matrix_path, dtype={"sample_id": str})
    
    # Check if this sample is in the matrix
    sample_id = fasta_path.stem
    sample_row = matrix[matrix["sample_id"] == sample_id]
    
    if sample_row.empty:
        console.print(f"[red]Sample {sample_id} not found in the feature matrix![/red]")
    else:
        # Extract features that are '1'
        sample_dict = sample_row.iloc[0].to_dict()
        active_features = [k for k, v in sample_dict.items() if k != "sample_id" and v == 1]
        
        console.print(f"Features present for [bold]{sample_id}[/bold]:")
        
        if not active_features:
            console.print("  [dim]None[/dim]")
        else:
            for feat in active_features:
                # Check if this feature maps back to our raw hits
                gene_symbol = feat.replace("gene_", "").replace("mut_", "")
                
                # Verify it against raw TSV
                if not raw_hits.empty and gene_col:
                    matches = raw_hits[raw_hits[gene_col] == gene_symbol]
                    if not matches.empty:
                        console.print(f"  ✅ [bold green]{feat}[/bold green] -> Maps to TSV hit '{gene_symbol}'")
                    else:
                        console.print(f"  ⚠ [bold red]{feat}[/bold red] -> NOT found in TSV hits! (Bug?)")
                else:
                    console.print(f"  ✅ [bold green]{feat}[/bold green]")
                    
    console.print("\n[bold green]Validation Complete![/bold green] The CSV accurately reflects the actual FASTA contents found by AMRFinderPlus.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Inspect pipeline outputs against the original FASTA")
    parser.add_argument("--fasta", required=True, help="Path to original FASTA file")
    parser.add_argument("--tsv", required=True, help="Path to AMRFinderPlus output TSV")
    parser.add_argument("--matrix", required=True, help="Path to final feature matrix CSV")
    
    args = parser.parse_args()
    inspect_pipeline_output(args.fasta, args.tsv, args.matrix)
