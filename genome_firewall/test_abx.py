import pandas as pd
df = pd.read_csv("dataset/PATRIC_genomes_AMR.txt", sep="\t", dtype=str)
df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
if 'evidence' in df.columns:
    df = df[df['evidence'] == 'Laboratory Method']
df = df[df['genome_name'].str.contains("Escherichia coli", na=False)]
print(df['antibiotic'].value_counts().head(10))
