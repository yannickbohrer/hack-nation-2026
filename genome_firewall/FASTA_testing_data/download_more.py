from Bio import Entrez, SeqIO
import sys
import time

Entrez.email = "test_pipeline@example.com"

# Known E. coli accessions with varying resistance profiles
accessions = {
    "O157_H7_Sakai": "BA000007.3",  # Pathogenic O157:H7
    "UTI89": "CP000243.1",          # Uropathogenic
    "MDR_Strain": "CP018985.1",     # Known multidrug-resistant E. coli
    "Plasmid_pNDM_MAR": "HQ451074.1" # Plasmid carrying NDM-1 superbug gene
}

for name, acc in accessions.items():
    print(f"Downloading {name} ({acc})...")
    try:
        handle = Entrez.efetch(db="nucleotide", id=acc, rettype="fasta", retmode="text")
        record = SeqIO.read(handle, "fasta")
        handle.close()
        
        with open(f"{name}.fasta", "w") as out:
            SeqIO.write(record, out, "fasta")
        print(f"  ✓ Downloaded {name}")
        time.sleep(1) # Be nice to NCBI servers
    except Exception as e:
        print(f"  ✗ Failed: {e}")

