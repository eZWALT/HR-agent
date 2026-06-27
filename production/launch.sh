#!/usr/bin/env bash
# launch.sh — unified launcher for HR-agent
#
# Usage:
#   ./launch.sh                # defaults to ollama (multi-GPU)
#   ./launch.sh --ollama       # start host ollama per GPU, then compose up
#   ./launch.sh --openai       # compose up without local ollama
#   ./launch.sh --remote       # ollama running on a different host (set OLLAMA_HOST in .env)
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

if [[ -f "${SCRIPT_DIR}/.env" ]]; then
    set -a
    source "${SCRIPT_DIR}/.env"
    set +a
else
    echo "ERROR: .env not found at ${SCRIPT_DIR}/.env"
    exit 1
fi

MODE="ollama"
while [[ $# -gt 0 ]]; do
    case $1 in
        --ollama)  MODE="ollama" ;;
        --openai)  MODE="openai" ;;
        --remote)  MODE="remote" ;;
        *)
            echo "Unknown argument: $1"
            echo "Usage: $0 [--ollama|--openai|--remote]"
            exit 1
            ;;
    esac
    shift
done

echo "[launch.sh] mode: $MODE"

COMPOSE_FILE="${SCRIPT_DIR}/docker-compose.yml"

# ─────────────────────────────────────────────────────────────────────────────
# OLLAMA path — start one ollama server per GPU, then compose up
# ─────────────────────────────────────────────────────────────────────────────
launch_ollama() {
    if [[ -z "${OLLAMA_BIN}" ]]; then
        echo "ERROR: OLLAMA_BIN not set in .env (path to ollama binary)"
        exit 1
    fi

    PIDS=()
    gpu_idx=0

    while true; do
        port_var="OLLAMA_GPU${gpu_idx}_PORT"
        models_var="OLLAMA_GPU${gpu_idx}_MODELS"
        devices_var="OLLAMA_GPU${gpu_idx}_VISIBLE_DEVICES"

        port="${!port_var}"
        [[ -z "${port}" ]] && break

        models="${!models_var}"
        devices="${!devices_var}"

        echo "[GPU ${gpu_idx}] Starting ollama on port ${port} (CUDA_VISIBLE_DEVICES=${devices})..."
        CUDA_VISIBLE_DEVICES="${devices}" \
            OLLAMA_HOST="0.0.0.0:${port}" \
            OLLAMA_KEEP_ALIVE="${OLLAMA_KEEP_ALIVE:--1}" \
            "${OLLAMA_BIN}" serve &
        PIDS+=($!)

        echo "[GPU ${gpu_idx}] Waiting for ollama to be ready..."
        until curl -sf "http://localhost:${port}/api/tags" > /dev/null 2>&1; do
            sleep 1
        done
        echo "      ollama on port ${port} is up."

        IFS=',' read -ra model_list <<< "${models}"
        for model in "${model_list[@]}"; do
            if "${OLLAMA_BIN}" list | grep -q "^${model}"; then
                echo "[GPU ${gpu_idx}] Model ${model} already present, skipping pull."
            else
                echo "[GPU ${gpu_idx}] Pulling ${model}..."
                "${OLLAMA_BIN}" pull "${model}"
            fi
        done

        ((gpu_idx++))
    done

    if [[ ${#PIDS[@]} -eq 0 ]]; then
        echo "ERROR: no GPU entries found in .env (OLLAMA_GPU0_PORT, etc.)"
        exit 1
    fi

    cleanup() {
        echo "Shutting down ollama instances..."
        for pid in "${PIDS[@]}"; do
            kill "${pid}" 2>/dev/null
        done
        docker compose -f "${COMPOSE_FILE}" down
    }
    trap cleanup EXIT INT TERM

    echo "[launch.sh] Starting docker compose (${#PIDS[@]} ollama instance(s))..."
    export LLM_BACKEND="ollama"
    docker compose -f "${COMPOSE_FILE}" up --build
}

# ─────────────────────────────────────────────────────────────────────────────
# OPENAI path — no local ollama needed, just compose up
# ─────────────────────────────────────────────────────────────────────────────
launch_openai() {
    if [[ -z "${OPENAI_API_KEY}" ]]; then
        echo "ERROR: OPENAI_API_KEY not set in .env"
        exit 1
    fi
    trap "echo 'Shutting down...'; docker compose -f '${COMPOSE_FILE}' down" EXIT INT TERM
    export LLM_BACKEND="openai"
    echo "[1/1] Starting docker compose (openai backend)..."
    docker compose -f "${COMPOSE_FILE}" up --build
}

# ─────────────────────────────────────────────────────────────────────────────
# REMOTE path — ollama running on a different host, just compose up
# ─────────────────────────────────────────────────────────────────────────────
launch_remote() {
    if [[ -z "${OLLAMA_HOST}" || "${OLLAMA_HOST}" == "host.docker.internal" ]]; then
        echo "ERROR: set OLLAMA_HOST in .env to the remote ollama address (e.g. 192.168.1.50)"
        exit 1
    fi
    trap "echo 'Shutting down...'; docker compose -f '${COMPOSE_FILE}' down" EXIT INT TERM
    export LLM_BACKEND="ollama"
    echo "[1/1] Starting docker compose (remote ollama at ${OLLAMA_HOST})..."
    docker compose -f "${COMPOSE_FILE}" up --build
}

case $MODE in
    ollama) launch_ollama ;;
    openai) launch_openai ;;
    remote) launch_remote ;;
esac

wait
