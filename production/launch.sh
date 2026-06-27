#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
COMPOSE_FILE="$SCRIPT_DIR/docker-compose.yml"
MODE="${1:-ollama}"

# root .env is the single source of truth
[[ -f "$ROOT_DIR/.env" ]] || { echo "no .env at $ROOT_DIR/.env"; exit 1; }
source "$ROOT_DIR/.env"

# docker compose needs .env next to the compose file — copy it over
cp "$ROOT_DIR/.env" "$SCRIPT_DIR/.env"
cleanup() {
  rm -f "$SCRIPT_DIR/.env"
  docker compose -f "$COMPOSE_FILE" down
}
trap cleanup EXIT INT TERM

start_ollama_per_gpu() {
  local gpu_idx=0
  while true; do
    local port_var="OLLAMA_GPU${gpu_idx}_PORT"
    local models_var="OLLAMA_GPU${gpu_idx}_MODELS"
    local devices_var="OLLAMA_GPU${gpu_idx}_VISIBLE_DEVICES"
    [[ -z "${!port_var}" ]] && break

    CUDA_VISIBLE_DEVICES="${!devices_var}" \
      OLLAMA_HOST="0.0.0.0:${!port_var}" \
      OLLAMA_KEEP_ALIVE="${OLLAMA_KEEP_ALIVE:--1}" \
      "$OLLAMA_BIN" serve &

    until curl -sf "http://localhost:${!port_var}/api/tags" >/dev/null 2>&1; do sleep 1; done

    for model in ${!models_var//,/ }; do
      "$OLLAMA_BIN" list | grep -q "^$model" && continue
      "$OLLAMA_BIN" pull "$model"
    done

    ((gpu_idx++))
  done

  docker compose -f "$COMPOSE_FILE" up --build
}

case "$MODE" in
  ollama)
    start_ollama_per_gpu
    ;;
  openai)
    [[ -z "$OPENAI_API_KEY" ]] && { echo "need OPENAI_API_KEY"; exit 1; }
    docker compose -f "$COMPOSE_FILE" up --build
    ;;
esac
