from Bio import Entrez
Entrez.email = "test@example.com"
handle = Entrez.esearch(db="nucleotide", term="Salmonella enterica A038_2016[Organism]")
record = Entrez.read(handle)
print(record["IdList"])
