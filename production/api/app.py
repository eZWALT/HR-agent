import json
import os
import traceback
from pydantic import BaseModel

import httpx
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from loguru import logger

OLLAMA_ENDPOINT_GPU0 = os.getenv("OLLAMA_ENDPOINT_GPU0", "http://host.docker.internal:11434")
OLLAMA_GPU0_MODEL = os.getenv("OLLAMA_GPU0_MODEL", "qwen2.5:27b")
LLM_BACKEND = os.getenv("LLM_BACKEND", "ollama")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
CLIENT_SLUG = os.getenv("CLIENT_SLUG", "grupo-sazon")

logger.info("starting up")
logger.info(f"LLM_BACKEND={LLM_BACKEND} OPENAI_MODEL={OPENAI_MODEL} CLIENT_SLUG={CLIENT_SLUG}")
logger.info(f"OLLAMA_ENDPOINT_GPU0={OLLAMA_ENDPOINT_GPU0} OLLAMA_GPU0_MODEL={OLLAMA_GPU0_MODEL}")
logger.info(f"OPENAI_API_KEY={'set' if OPENAI_API_KEY else 'not set'}")

app = FastAPI(title="Sazoncito API")


class ChatRequest(BaseModel):
    message: str


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/ping")
async def ping():
    return {"pong": True, "backend": "sazoncito", "llm_backend": LLM_BACKEND}


@app.get("/config")
async def get_config():
    path = f"data/{CLIENT_SLUG}/config.json"
    logger.debug(f"reading config from {path}")
    try:
        with open(path) as f:
            data = json.load(f)
            logger.debug(f"config loaded: {data.get('client_name')} / {data.get('assistant_name')}")
            return data
    except FileNotFoundError:
        logger.error(f"config not found for client: {CLIENT_SLUG}")
        return {"error": f"config not found for client: {CLIENT_SLUG}"}
    except json.JSONDecodeError as e:
        logger.error(f"invalid config JSON at {path}: {e}")
        return {"error": f"invalid config: {e}"}


@app.post("/chat")
async def chat(req: ChatRequest):
    messages = [{"role": "user", "content": req.message}]
    logger.info(f"chat request | backend={LLM_BACKEND} | msg='{req.message[:80]}...'")

    async def generate():
        async with httpx.AsyncClient() as client:
            try:
                if LLM_BACKEND == "openai":
                    logger.debug("calling openai")
                    async for event in _stream_openai(client, messages):
                        yield event
                else:
                    logger.debug(f"calling ollama at {OLLAMA_ENDPOINT_GPU0}")
                    async for event in _stream_ollama(client, messages):
                        yield event
            except httpx.ConnectError as e:
                logger.error(f"connection failed: {e}")
                yield f"data: ⚠️ Could not reach {LLM_BACKEND} backend: {e}\n\n"
                yield "data: [DONE]\n\n"
            except httpx.TimeoutException as e:
                logger.error(f"timeout: {e}")
                yield f"data: ⚠️ {LLM_BACKEND} backend timed out: {e}\n\n"
                yield "data: [DONE]\n\n"
            except Exception as e:
                logger.error(f"unexpected error: {e}\n{traceback.format_exc()}")
                yield f"data: ⚠️ Error: {e}\n\n"
                yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


async def _stream_ollama(client, messages):
    url = f"{OLLAMA_ENDPOINT_GPU0}/api/chat"
    payload = {
        "model": OLLAMA_GPU0_MODEL,
        "messages": messages,
        "stream": True,
    }
    logger.debug(f"ollama payload: model={OLLAMA_GPU0_MODEL}")
    async with client.stream("POST", url, json=payload, timeout=120) as r:
        r.raise_for_status()
        count = 0
        async for line in r.aiter_lines():
            if not line:
                continue
            data = json.loads(line)
            chunk = data.get("message", {}).get("content", "")
            if chunk:
                count += 1
                yield f"data: {chunk}\n\n"
            if data.get("done"):
                logger.debug(f"ollama stream done — {count} chunks")
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
    logger.debug(f"openai payload: model={OPENAI_MODEL}")
    async with client.stream("POST", url, json=payload, headers=headers, timeout=120) as r:
        r.raise_for_status()
        count = 0
        async for line in r.aiter_lines():
            if not line or not line.startswith("data: "):
                continue
            if line == "data: [DONE]":
                logger.debug(f"openai stream done — {count} chunks")
                yield "data: [DONE]\n\n"
                return
            data = json.loads(line[6:])
            chunk = data.get("choices", [{}])[0].get("delta", {}).get("content", "")
            if chunk:
                count += 1
                yield f"data: {chunk}\n\n"
