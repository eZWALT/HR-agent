import json
import os
from pydantic import BaseModel

import httpx
from fastapi import FastAPI
from fastapi.responses import StreamingResponse

app = FastAPI(title="Sazoncito API")

OLLAMA_ENDPOINT_GPU0 = os.getenv("OLLAMA_ENDPOINT_GPU0", "http://host.docker.internal:11434")
OLLAMA_GPU0_MODEL = os.getenv("OLLAMA_GPU0_MODEL", "qwen2.5:27b")
LLM_BACKEND = os.getenv("LLM_BACKEND", "ollama")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


class ChatRequest(BaseModel):
    message: str


async def _stream_ollama(client, messages):
    url = f"{OLLAMA_ENDPOINT_GPU0}/api/chat"
    payload = {
        "model": OLLAMA_GPU0_MODEL,
        "messages": messages,
        "stream": True,
    }
    async with client.stream("POST", url, json=payload, timeout=120) as r:
        async for line in r.aiter_lines():
            if not line:
                continue
            data = json.loads(line)
            chunk = data.get("message", {}).get("content", "")
            if chunk:
                yield f"data: {chunk}\n\n"
            if data.get("done"):
                yield "data: [DONE]\n\n"


async def _stream_openai(client, messages):
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": OPENAI_MODEL,
        "messages": messages,
        "stream": True,
    }
    async with client.stream("POST", url, json=payload, headers=headers, timeout=120) as r:
        async for line in r.aiter_lines():
            if not line or not line.startswith("data: "):
                continue
            if line == "data: [DONE]":
                yield "data: [DONE]\n\n"
                return
            data = json.loads(line[6:])
            chunk = data.get("choices", [{}])[0].get("delta", {}).get("content", "")
            if chunk:
                yield f"data: {chunk}\n\n"


@app.get("/config")
async def get_config():
    # TODO: query `clients` table from DB for multi-tenant support.
    #       The `clients` table has a `config JSONB` column for per-client settings.
    return {
        "client_name": "Grupo Sazón",
        "assistant_name": "María",
        "emoji": "🌶️",
        "greeting": "¡Hola! Soy María, tu asistente de selección en Grupo Sazón. Para comenzar, ¿tienes licencia de conducir vigente?",
    }


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/chat")
async def chat(req: ChatRequest):
    messages = [{"role": "user", "content": req.message}]

    async def generate():
        async with httpx.AsyncClient() as client:
            try:
                if LLM_BACKEND == "openai":
                    async for event in _stream_openai(client, messages):
                        yield event
                else:
                    async for event in _stream_ollama(client, messages):
                        yield event
            except Exception as e:
                yield f"data: ⚠️ Error: {e}\n\n"
                yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
