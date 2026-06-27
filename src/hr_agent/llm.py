from __future__ import annotations

import os

from langchain_openai import ChatOpenAI
from loguru import logger


def _build_base_url() -> str:
    """Return the OpenAI-compatible base URL for the active backend."""
    backend = os.getenv("LLM_BACKEND", "ollama")
    if backend == "openai":
        return "https://api.openai.com/v1"
    ollama_host = os.getenv("OLLAMA_HOST", "host.docker.internal")
    ollama_port = os.getenv("OLLAMA_GPU0_PORT", "5555")
    return f"http://{ollama_host}:{ollama_port}/v1"


def _build_model_name() -> str:
    backend = os.getenv("LLM_BACKEND", "ollama")
    if backend == "openai":
        return os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    return os.getenv("OLLAMA_GPU0_MODEL", "qwen3.6:35b")


def _build_api_key() -> str:
    backend = os.getenv("LLM_BACKEND", "ollama")
    if backend == "openai":
        return os.getenv("OPENAI_API_KEY", "")
    return "ollama"


BASE_URL = _build_base_url()
MODEL = _build_model_name()
API_KEY = _build_api_key()

logger.info(f"LLM client: backend={os.getenv('LLM_BACKEND', 'ollama')} model={MODEL} base_url={BASE_URL}")


def get_llm(temperature: float = 0.0, streaming: bool = False) -> ChatOpenAI:
    kwargs = {
        "model": MODEL,
        "temperature": temperature,
        "base_url": BASE_URL,
        "api_key": API_KEY,
        "streaming": streaming,
        "timeout": 120,
    }
    if os.getenv("LLM_BACKEND", "ollama") == "ollama":
        think = os.getenv("LLM_THINK", "false").lower() in ("1", "true", "yes")
        kwargs["extra_body"] = {
            "think": think,
            "keep_alive": int(os.getenv("OLLAMA_KEEP_ALIVE", "-1")),
        }
        num_ctx = int(os.getenv("OLLAMA_NUM_CTX", "8192"))
        kwargs["model_kwargs"] = {"options": {"num_ctx": num_ctx}}
    return ChatOpenAI(**kwargs)
