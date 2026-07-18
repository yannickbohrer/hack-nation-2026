from Bio import Entrez, SeqIO
import sys

Entrez.email = "test@example.com"

try:
    print("Downloading E. coli K-12 MG1655 (U00096.3)...")
    handle = Entrez.efetch(db="nucleotide", id="U00096.3", rettype="fasta", retmode="text")
    record = SeqIO.read(handle, "fasta")
    handle.close()
    
    with open("511145.12.fasta", "w") as out:
        SeqIO.write(record, out, "fasta")
    print("Downloaded successfully.")
except Exception as e:
    print(f"Failed to download: {e}")
    sys.exit(1)
