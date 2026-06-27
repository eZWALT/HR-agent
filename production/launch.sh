#!/usr/bin/env bash
set -e
D="$(cd "$(dirname "$0")" && pwd)"
[[ -f "$D/.env" ]] && source "$D/.env" || { echo "no .env"; exit 1; }

mode="${1:-ollama}"

ollama_up() {
  local i=0 p m d
  while true; do
    p="OLLAMA_GPU${i}_PORT"; m="OLLAMA_GPU${i}_MODELS"; d="OLLAMA_GPU${i}_VISIBLE_DEVICES"
    [[ -z "${!p}" ]] && break
    CUDA_VISIBLE_DEVICES="${!d}" OLLAMA_HOST="0.0.0.0:${!p}" OLLAMA_KEEP_ALIVE="${OLLAMA_KEEP_ALIVE:--1}" "$OLLAMA_BIN" serve &
    until curl -sf "http://localhost:${!p}/api/tags" >/dev/null 2>&1; do sleep 1; done
    for mod in ${!m//,/ }; do "$OLLAMA_BIN" list | grep -q "^$mod" && continue; "$OLLAMA_BIN" pull "$mod"; done
    ((i++))
  done
  trap "kill $(jobs -p) 2>/dev/null; docker compose -f '$D/docker-compose.yml' down" EXIT INT TERM
  docker compose -f "$D/docker-compose.yml" up --build
}

case "$mode" in
  ollama) ollama_up ;;
  openai) [[ -z "$OPENAI_API_KEY" ]] && { echo "need OPENAI_API_KEY"; exit 1; }
          trap "docker compose -f '$D/docker-compose.yml' down" EXIT INT TERM
          docker compose -f "$D/docker-compose.yml" up --build ;;
esac
