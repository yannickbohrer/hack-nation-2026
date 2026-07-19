FROM python:3.12-slim

WORKDIR /app

# Install curl for healthcheck and hmmer (needed for AMRFinderPlus)
RUN apt-get update && apt-get install -y --no-install-recommends curl hmmer ncbi-blast+ ca-certificates && rm -rf /var/lib/apt/lists/*

# Install AMRFinderPlus from precompiled binaries
RUN curl -LO https://github.com/ncbi/amr/releases/download/amrfinder_v4.2.7/amrfinder_binaries_v4.2.7.tar.gz && \
    tar -xzf amrfinder_binaries_v4.2.7.tar.gz -C /usr/local/bin/ && \
    rm amrfinder_binaries_v4.2.7.tar.gz && \
    amrfinder -u

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
