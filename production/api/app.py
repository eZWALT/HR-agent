import json
import os
import time
import traceback
import datetime
import uuid
from pydantic import BaseModel

import httpx
from fastapi import FastAPI
from contextlib import asynccontextmanager
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

OLLAMA_ENDPOINT_GPU0 = os.getenv("OLLAMA_ENDPOINT_GPU0", "http://host.docker.internal:5555")
OLLAMA_GPU0_MODEL = os.getenv("OLLAMA_GPU0_MODEL", "qwen3.6:35b")
OLLAMA_NUM_CTX = int(os.getenv("OLLAMA_NUM_CTX", "8192"))
_raw_keep_alive = os.getenv("OLLAMA_KEEP_ALIVE", "-1")
OLLAMA_KEEP_ALIVE = int(_raw_keep_alive) if _raw_keep_alive.lstrip("-").isdigit() else _raw_keep_alive
LLM_THINK = os.getenv("LLM_THINK", "false").lower() in ("1", "true", "yes")
LLM_BACKEND = os.getenv("LLM_BACKEND", "ollama")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
CLIENT_SLUG = os.getenv("CLIENT_SLUG", "grupo-sazon")

logger.info("starting up")
logger.info(f"LLM_BACKEND={LLM_BACKEND} OPENAI_MODEL={OPENAI_MODEL} CLIENT_SLUG={CLIENT_SLUG} OLLAMA_NUM_CTX={OLLAMA_NUM_CTX}")
logger.info(f"OLLAMA_ENDPOINT_GPU0={OLLAMA_ENDPOINT_GPU0} OLLAMA_GPU0_MODEL={OLLAMA_GPU0_MODEL}")
logger.info(f"OLLAMA_KEEP_ALIVE={OLLAMA_KEEP_ALIVE} LLM_THINK={LLM_THINK}")
logger.info(f"OPENAI_API_KEY={'set' if OPENAI_API_KEY else 'not set'}")


async def _warmup_ollama():
    """Send a 1-token request so the model is loaded into VRAM before the first real request."""
    if LLM_BACKEND != "ollama":
        return
    logger.info(f"warming up Ollama model '{OLLAMA_GPU0_MODEL}'...")
    import asyncio
    for attempt in range(3):
        try:
            async with httpx.AsyncClient() as client:
                payload = {
                    "model": OLLAMA_GPU0_MODEL,
                    "messages": [{"role": "user", "content": "hi"}],
                    "think": LLM_THINK,
                    "stream": False,
                    "keep_alive": OLLAMA_KEEP_ALIVE,
                    "options": {"num_ctx": OLLAMA_NUM_CTX},
                }
                logger.debug(f"warmup payload: {json.dumps(payload)}")
                r = await client.post(f"{OLLAMA_ENDPOINT_GPU0}/api/chat", json=payload, timeout=180)
                if r.status_code != 200:
                    logger.warning(f"warmup attempt {attempt+1} status={r.status_code} body={r.text[:300]}")
                r.raise_for_status()
            logger.info("Ollama warmup complete.")
            return
        except Exception as exc:
            logger.warning(f"Ollama warmup attempt {attempt+1}/3 failed: {exc}")
            if attempt < 2:
                await asyncio.sleep(3)
    logger.warning("Ollama warmup failed after 3 attempts (non-fatal, first request will be slow)")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await _warmup_ollama()
    yield

app = FastAPI(title="Sazoncito API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory thread storage: user_id -> {"messages": [...], "last_active": datetime}
active_threads: dict[str, dict] = {}


class ChatRequest(BaseModel):
    message: str
    user_id: str = ""


def _load_greeting() -> str:
    path = f"data/{CLIENT_SLUG}/config.json"
    try:
        with open(path) as f:
            return json.load(f).get("greeting", "")
    except Exception:
        return ""


def _get_thread(user_id: str) -> dict:
    if user_id not in active_threads:
        greeting = _load_greeting()
        initial_messages = []
        if greeting:
            initial_messages.append({"role": "assistant", "content": greeting})
        active_threads[user_id] = {
            "messages": initial_messages,
            "last_active": datetime.datetime.now(),
        }
    return active_threads[user_id]


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
    user_id = req.user_id or str(uuid.uuid4())
    thread = _get_thread(user_id)
    thread["messages"].append({"role": "user", "content": req.message})
    thread["last_active"] = datetime.datetime.now()
    logger.info(f"chat request | user={user_id[:8]} backend={LLM_BACKEND} history_len={len(thread['messages'])}")
    logger.debug(f"full messages: {json.dumps(thread['messages'], ensure_ascii=False)}")

    async def generate():
        async with httpx.AsyncClient() as client:
            try:
                if LLM_BACKEND == "openai":
                    logger.debug("calling openai")
                    async for event in _stream_openai(client, thread["messages"]):
                        yield event
                else:
                    logger.debug(f"calling ollama at {OLLAMA_ENDPOINT_GPU0}")
                    async for event in _stream_ollama(client, thread["messages"]):
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
        "think": LLM_THINK,
        "stream": True,
        "keep_alive": OLLAMA_KEEP_ALIVE,
        "options": {"num_ctx": OLLAMA_NUM_CTX},
    }
    logger.debug(f"ollama payload: model={OLLAMA_GPU0_MODEL} num_ctx={OLLAMA_NUM_CTX} think={LLM_THINK} keep_alive={OLLAMA_KEEP_ALIVE}")
    full_reply = ""
    t0 = time.perf_counter()
    first_token_ts = None
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
                full_reply += chunk
                if first_token_ts is None:
                    first_token_ts = time.perf_counter()
                yield f"data: {json.dumps(chunk)}\n\n"
            if data.get("done"):
                ttft = (first_token_ts - t0) * 1000 if first_token_ts else 0
                total = (time.perf_counter() - t0) * 1000
                tok_rate = len(full_reply.split()) / (total / 1000) if total > 0 else 0
                logger.info(f"ollama stream done | chunks={count} ttft={ttft:.0f}ms total={total:.0f}ms rate={tok_rate:.1f} tok/s reply={len(full_reply)} chars")
                yield "data: [DONE]\n\n"
    if full_reply:
        messages.append({"role": "assistant", "content": full_reply})


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
    full_reply = ""
    t0 = time.perf_counter()
    first_token_ts = None
    async with client.stream("POST", url, json=payload, headers=headers, timeout=120) as r:
        r.raise_for_status()
        count = 0
        async for line in r.aiter_lines():
            if not line or not line.startswith("data: "):
                continue
            if line == "data: [DONE]":
                ttft = (first_token_ts - t0) * 1000 if first_token_ts else 0
                total = (time.perf_counter() - t0) * 1000
                tok_rate = len(full_reply.split()) / (total / 1000) if total > 0 else 0
                logger.info(f"openai stream done | chunks={count} ttft={ttft:.0f}ms total={total:.0f}ms rate={tok_rate:.1f} tok/s reply={len(full_reply)} chars")
                yield "data: [DONE]\n\n"
                break
            data = json.loads(line[6:])
            chunk = data.get("choices", [{}])[0].get("delta", {}).get("content", "")
            if chunk:
                count += 1
                full_reply += chunk
                if first_token_ts is None:
                    first_token_ts = time.perf_counter()
                yield f"data: {json.dumps(chunk)}\n\n"
    if full_reply:
        messages.append({"role": "assistant", "content": full_reply})


@app.get("/benchmark")
async def benchmark():
    """Latency probe: non-stream request to measure TTFT and throughput."""
    import asyncio

    results = {"backend": LLM_BACKEND, "model": OLLAMA_GPU0_MODEL if LLM_BACKEND == "ollama" else OPENAI_MODEL}

    async with httpx.AsyncClient() as client:
        t0 = time.perf_counter()
        try:
            if LLM_BACKEND == "ollama":
                payload = {
                    "model": OLLAMA_GPU0_MODEL,
                    "messages": [{"role": "user", "content": "Say hello in one sentence."}],
                    "think": LLM_THINK,
                    "stream": False,
                    "keep_alive": OLLAMA_KEEP_ALIVE,
                    "options": {"num_ctx": OLLAMA_NUM_CTX, "num_predict": 100},
                }
                r = await client.post(f"{OLLAMA_ENDPOINT_GPU0}/api/chat", json=payload, timeout=120)
                r.raise_for_status()
                data = r.json()
                reply = data.get("message", {}).get("content", "")
                results["eval_duration_ns"] = data.get("eval_duration", 0)
                results["prompt_eval_duration_ns"] = data.get("prompt_eval_duration", 0)
                results["load_duration_ns"] = data.get("load_duration", 0)
                results["eval_count"] = data.get("eval_count", 0)
                results["tokens_per_second"] = (
                    results["eval_count"] / (results["eval_duration_ns"] / 1e9)
                    if results["eval_duration_ns"] > 0 else 0
                )
            else:
                payload = {
                    "model": OPENAI_MODEL,
                    "messages": [{"role": "user", "content": "Say hello in one sentence."}],
                    "max_tokens": 100,
                }
                headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
                r = await client.post("https://api.openai.com/v1/chat/completions", json=payload, headers=headers, timeout=60)
                r.raise_for_status()
                data = r.json()
                reply = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        except Exception as e:
            results["error"] = str(e)
            results["wall_ms"] = (time.perf_counter() - t0) * 1000
            return results

        wall_ms = (time.perf_counter() - t0) * 1000
        results["wall_ms"] = round(wall_ms, 1)
        results["reply_chars"] = len(reply)
        results["reply_preview"] = reply[:120]
        return results
