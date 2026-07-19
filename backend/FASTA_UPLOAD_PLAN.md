# Implementation Plan: FASTA Upload & Prediction Pipeline

To enable the end-to-end flow where a doctor uploads a `.fasta` file and receives antibiotic resistance predictions, we need to bridge the web backend with the `genome_firewall` pipeline.

Here is the step-by-step implementation plan:

## 1. Update Backend Dockerfile (Dependencies)
The backend currently runs in a minimal `python:3.12-slim` container. To process `.fasta` files into a feature matrix, it needs the `genome_firewall` dependencies and the `AMRFinderPlus` binary.
- **Action**: Update `backend/Dockerfile` to install `ncbi-amrfinderplus` (via `apt` or by downloading the binary) and `hmmer` (which AMRFinderPlus requires).
- **Action**: Add `biopython` and `pyarrow` (required by `module01/pipeline.py`) to `backend/requirements.txt`.

## 2. Share `genome_firewall` Code with the Backend
The backend container currently only mounts the `./backend` folder. It needs access to the pipeline scripts in `module01`.
- **Action**: Update `docker-compose.yml` to mount the `./genome_firewall` directory into the backend container (e.g., as `/app/genome_firewall`).
- **Action**: Set the `PYTHONPATH` in `docker-compose.yml` so the backend can easily import `genome_firewall.module01.pipeline`.

## 3. Create FASTA Processing Service
We need a robust way to execute Pipeline 1 (`FASTA -> AMRFinderPlus -> Feature Matrix`) from the FastAPI backend.
- **Action**: Create `backend/services/fasta_processor.py`.
- **Logic**: 
  - Accept the raw uploaded file and save it to a temporary `/tmp/` directory.
  - Invoke `module01.pipeline.run_pipeline_single()` programmatically.
  - Parse the resulting `feature_matrix.csv` to extract the binary features (e.g., `{"gene_aac(3)-IId": 1, ...}`).
  - Clean up the temporary files to prevent disk bloat.

## 4. Add the API Endpoint
- **Action**: Update `backend/main.py`.
- **Logic**:
  - Add a `POST /api/predict/fasta` endpoint using FastAPI's `UploadFile`.
  - Pass the uploaded file to `fasta_processor.py` to get the feature dictionary.
  - Pass the feature dictionary to the existing `prediction_service.predict()` function.
  - Return the final predictions (resistance probabilities, confidence scores, and explainability features) as JSON.

## 5. End-to-End Testing
- **Action**: Write a quick script (or use `curl`) to test the endpoint using one of the existing `.fasta` files (e.g. `genome_firewall/test.fasta`).
- **Verify**: The endpoint correctly processes the file, runs AMRFinderPlus, queries the 5 models, and returns a valid JSON response.

## 6. Model Deployment Workflow (Google Colab → Backend)
The backend is designed to easily ingest models trained experimentally in Google Colab. 
- **Training (Colab)**: Data scientists continue experimenting in their Jupyter Notebook on Colab.
- **Exporting (Colab)**: Once satisfied, the models are serialized using `joblib.dump()`, alongside a `.json` manifest detailing the expected features and calibration thresholds.
- **Transfer**: The `.joblib` and `.json` files are downloaded from Colab and placed into the `backend/models/` directory.
- **Serving (Backend)**: On startup, the backend's `prediction_service.py` automatically detects and loads (`joblib.load()`) these exact models. When a `.fasta` upload occurs, the newly extracted features are evaluated by these live models to generate the final prediction.

---

**Please review this plan. Click "Proceed" (or give me the go-ahead in chat) and I will implement these changes.**
