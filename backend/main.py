"""
Hack-Nation Backend — FastAPI server with AI streaming support.
"""

import os
from dotenv import load_dotenv
from fastapi import FastAPI, Request, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from services.ai_client import stream_chat_completion
from services.prediction_service import prediction_service
from services.fasta_processor import process_fasta_file

load_dotenv()

app = FastAPI(title="Hack-Nation API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@app.get("/api/status")
async def health_check():
    return {"status": "API is operational"}


# ---------------------------------------------------------------------------
# Chat / AI streaming endpoint
# ---------------------------------------------------------------------------
class ChatMessage(BaseModel):
    role: str = "user"
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    model: str = "gpt-4o-mini"
    temperature: float = 0.7


@app.post("/api/chat")
async def chat(req: ChatRequest, request: Request):
    """
    Streams an AI chat completion back to the client via Server-Sent Events.
    Each SSE `data` payload is a JSON string with a `content` field containing
    the next token chunk, or `{"done": true}` when the stream is complete.
    """

    async def event_generator():
        async for chunk in stream_chat_completion(
            messages=[m.model_dump() for m in req.messages],
            model=req.model,
            temperature=req.temperature,
        ):
            if await request.is_disconnected():
                break
            yield {"data": chunk}
        yield {"data": '{"done": true}'}

    return EventSourceResponse(event_generator())


# ---------------------------------------------------------------------------
# Prediction endpoint
# ---------------------------------------------------------------------------
from typing import Dict, Any

class PredictionRequest(BaseModel):
    features: Dict[str, int]


@app.post("/api/predict")
async def predict_resistance(req: PredictionRequest):
    """
    Given a set of AMR features (from AMRFinderPlus), return the predictions
    from all trained logistic regression models.
    """
    results = prediction_service.predict(req.features)
    if "error" in results:
        return {"error": results["error"]}
    return {"predictions": results}

@app.post("/api/predict/fasta")
async def predict_from_fasta(file: UploadFile = File(...)):
    """
    Accepts a raw .fasta file upload, runs it through the AMRFinderPlus pipeline
    to extract features, and returns predictions from all loaded models.
    """
    if not file.filename.endswith((".fasta", ".fa", ".fna")):
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload a FASTA file.")
        
    try:
        # Process the FASTA to get the feature dictionary
        features = process_fasta_file(file)
        
        # Get predictions using the extracted features
        results = prediction_service.predict(features)
        
        if "error" in results:
            raise HTTPException(status_code=500, detail=results["error"])
            
        return {
            "filename": file.filename,
            "features_extracted": len(features),
            "predictions": results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
