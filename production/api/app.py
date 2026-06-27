import json
import os
from pydantic import BaseModel

import httpx
from fastapi import FastAPI
from fastapi.responses import StreamingResponse

app = FastAPI(title="Sazoncito API")

OLLAMA_ENDPOINT_GPU0 = os.getenv("OLLAMA_ENDPOINT_GPU0", "http://host.docker.internal:11434")
LLM_BACKEND = os.getenv("LLM_BACKEND", "ollama")
OLLAMA_GPU0_MODEL = os.getenv("OLLAMA_GPU0_MODEL", "qwen2.5:27b")


class ChatRequest(BaseModel):
    message: str


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/chat")
async def chat(req: ChatRequest):
    async def generate():
        async with httpx.AsyncClient() as client:
            url = f"{OLLAMA_ENDPOINT_GPU0}/api/chat"
            payload = {
                "model": OLLAMA_GPU0_MODEL,
                "messages": [{"role": "user", "content": req.message}],
                "stream": True,
            }
            try:
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
            except Exception as e:
                yield f"data: ⚠️ Ollama unreachable: {e}\n\n"
                yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
