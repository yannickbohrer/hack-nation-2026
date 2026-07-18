"""
Hack-Nation Backend — FastAPI server with AI streaming support.
"""

import os
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from services.ai_client import stream_chat_completion

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
