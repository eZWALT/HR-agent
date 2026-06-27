#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
COMPOSE_FILE="$SCRIPT_DIR/docker-compose.yml"
MODE="${1:-ollama}"

[[ -f "$ROOT_DIR/.env" ]] || { echo "no .env at $ROOT_DIR/.env — copy .env.example to .env"; exit 1; }
source "$ROOT_DIR/.env"

ENV_FILE="--env-file $ROOT_DIR/.env"
OLLAMA_PIDS=()

cleanup() {
  echo "shutting down..."
  docker compose -f "$COMPOSE_FILE" down 2>/dev/null || true
  for pid in "${OLLAMA_PIDS[@]}"; do kill "$pid" 2>/dev/null || true; done
}
trap cleanup EXIT INT TERM

ollama_serve() {
  local port=$1 gpu_idx=$2 devices=$3
  if curl -sf "http://localhost:${port}/api/tags" >/dev/null 2>&1; then
    echo "  GPU${gpu_idx} already running on port ${port}, reusing"
    return 0
  fi
  echo "  GPU${gpu_idx} starting ollama on port ${port}..."
  CUDA_VISIBLE_DEVICES="${devices}" \
    OLLAMA_HOST="0.0.0.0:${port}" \
    OLLAMA_KEEP_ALIVE="${OLLAMA_KEEP_ALIVE:--1}" \
    "$OLLAMA_BIN" serve &
  OLLAMA_PIDS+=($!)
  local i=0
  until curl -sf "http://localhost:${port}/api/tags" >/dev/null 2>&1; do
    sleep 1; ((i++))
    if [[ $i -ge 10 ]]; then
      echo "  WARN: GPU${gpu_idx} not ready after 10s, skipping"
      return 1
    fi
  done
}

ollama_pull() {
  local port=$1 model=$2
  if OLLAMA_HOST="localhost:${port}" "$OLLAMA_BIN" list 2>/dev/null | grep -q "^${model}"; then
    echo "  model ${model} already present"
  else
    echo "  pulling ${model}..."
    OLLAMA_HOST="localhost:${port}" "$OLLAMA_BIN" pull "$model" || echo "  WARN: pull ${model} failed"
  fi
}

launch_ollama() {
  export LLM_BACKEND=ollama

  # GPU0 — required
  if ollama_serve "${OLLAMA_GPU0_PORT:-5555}" 0 "${OLLAMA_GPU0_VISIBLE_DEVICES:-0}"; then
    ollama_pull "${OLLAMA_GPU0_PORT:-5555}" "${OLLAMA_GPU0_MODEL:-qwen3.6:35b}"
  fi

  # GPU1 — best-effort (skip if busy/unavailable)
  if [[ -n "${OLLAMA_GPU1_PORT:-}" ]]; then
    if ollama_serve "$OLLAMA_GPU1_PORT" 1 "${OLLAMA_GPU1_VISIBLE_DEVICES:-1}"; then
      IFS=',' read -ra MODELS <<< "${OLLAMA_GPU1_MODELS:-}"
      for model in "${MODELS[@]}"; do
        ollama_pull "$OLLAMA_GPU1_PORT" "$model"
      done
    fi
  fi

  docker compose $ENV_FILE -f "$COMPOSE_FILE" up --build
}

case "$MODE" in
  ollama)
    launch_ollama
    ;;
  openai)
    [[ -z "$OPENAI_API_KEY" ]] && { echo "need OPENAI_API_KEY"; exit 1; }
    export LLM_BACKEND=openai
    docker compose $ENV_FILE -f "$COMPOSE_FILE" up --build
    ;;
esac
