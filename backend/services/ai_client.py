"""
Thin wrapper around the OpenAI Python SDK with async streaming support.

Swap the model, adjust the system prompt, or replace with another provider
as needed once the hackathon challenge is revealed.
"""

import json
import os
from openai import AsyncOpenAI

_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is not set. "
                "Copy .env.example to .env and add your key."
            )
        _client = AsyncOpenAI(api_key=api_key)
    return _client


async def stream_chat_completion(
    messages: list[dict],
    model: str = "gpt-4o-mini",
    temperature: float = 0.7,
    system_prompt: str | None = None,
):
    """
    Yield JSON-encoded token chunks from an OpenAI chat completion stream.

    Each yielded string is a JSON object: {"content": "..."} where content
    is the next token delta.  The caller is responsible for sending the
    final {"done": true} event.
    """
    client = _get_client()

    full_messages = []
    if system_prompt:
        full_messages.append({"role": "system", "content": system_prompt})
    full_messages.extend(messages)

    stream = await client.chat.completions.create(
        model=model,
        messages=full_messages,
        temperature=temperature,
        stream=True,
    )

    async for chunk in stream:
        delta = chunk.choices[0].delta if chunk.choices else None
        if delta and delta.content:
            yield json.dumps({"content": delta.content})
