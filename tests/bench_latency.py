#!/usr/bin/env python3
"""
Latency benchmarks for the HR-agent chat backend.

Tests 3 layers:
  1. Ollama direct (/api/chat non-stream)
  2. Backend SSE (/chat stream)
  3. Backend non-stream (/benchmark endpoint)

Run on atlas:
    python3 tests/bench_latency.py --endpoint http://localhost:5555 --model qwen3.6:35b
    python3 tests/bench_latency.py --backend http://localhost:8000

Or from inside the backend container:
    python3 tests/bench_latency.py --ollama-direct
"""

import argparse
import json
import time
import sys

import httpx


PROMPT = "Say hello in one sentence."
WARMUP_PROMPT = "hi"


def bench_ollama_direct(endpoint: str, model: str, think: bool = False, runs: int = 3):
    """Test 1: Ollama /api/chat non-stream — measures pure inference latency."""
    print(f"\n{'='*60}")
    print(f"TEST 1: Ollama Direct (non-stream)")
    print(f"  endpoint: {endpoint}")
    print(f"  model:    {model}")
    print(f"  think:    {think}")
    print(f"  runs:     {runs}")
    print(f"{'='*60}")

    # Warmup
    print("\n  [warmup] loading model into VRAM...")
    t0 = time.perf_counter()
    with httpx.Client() as c:
        r = c.post(f"{endpoint}/api/chat", json={
            "model": model,
            "messages": [{"role": "user", "content": WARMUP_PROMPT}],
            "think": think,
            "stream": False,
            "keep_alive": -1,
            "options": {"num_predict": 1, "num_ctx": 8192},
        }, timeout=120)
        r.raise_for_status()
    warmup_ms = (time.perf_counter() - t0) * 1000
    print(f"  [warmup] done in {warmup_ms:.0f}ms")

    results = []
    for i in range(runs):
        t0 = time.perf_counter()
        with httpx.Client() as c:
            r = c.post(f"{endpoint}/api/chat", json={
                "model": model,
                "messages": [{"role": "user", "content": PROMPT}],
                "think": think,
                "stream": False,
                "keep_alive": -1,
                "options": {"num_ctx": 8192},
            }, timeout=120)
            r.raise_for_status()
            data = r.json()
        wall_ms = (time.perf_counter() - t0) * 1000
        reply = data.get("message", {}).get("content", "")
        eval_count = data.get("eval_count", 0)
        eval_dur_ns = data.get("eval_duration", 0)
        load_dur_ns = data.get("load_duration", 0)
        prompt_eval_ns = data.get("prompt_eval_duration", 0)
        tps = eval_count / (eval_dur_ns / 1e9) if eval_dur_ns > 0 else 0

        print(f"\n  Run {i+1}/{runs}:")
        print(f"    wall:         {wall_ms:.0f}ms")
        print(f"    load:         {load_dur_ns/1e6:.0f}ms")
        print(f"    prompt_eval:  {prompt_eval_ns/1e6:.0f}ms")
        print(f"    eval:         {eval_dur_ns/1e6:.0f}ms")
        print(f"    tokens:       {eval_count}")
        print(f"    tok/s:        {tps:.1f}")
        print(f"    reply:        {reply[:80]!r}")
        results.append({
            "run": i + 1,
            "wall_ms": wall_ms,
            "load_ms": load_dur_ns / 1e6,
            "prompt_eval_ms": prompt_eval_ns / 1e6,
            "eval_ms": eval_dur_ns / 1e6,
            "tokens": eval_count,
            "tps": tps,
        })

    _summary(results)
    return results


def bench_ollama_stream(endpoint: str, model: str, think: bool = False, runs: int = 3):
    """Test 2: Ollama /api/chat stream — measures TTFT (time to first token)."""
    print(f"\n{'='*60}")
    print(f"TEST 2: Ollama Stream (TTFT)")
    print(f"  endpoint: {endpoint}")
    print(f"  model:    {model}")
    print(f"  think:    {think}")
    print(f"{'='*60}")

    results = []
    for i in range(runs):
        t0 = time.perf_counter()
        first_token = None
        full_reply = ""
        chunk_count = 0

        with httpx.Client() as c:
            with c.stream("POST", f"{endpoint}/api/chat", json={
                "model": model,
                "messages": [{"role": "user", "content": PROMPT}],
                "think": think,
                "stream": True,
                "keep_alive": -1,
                "options": {"num_ctx": 8192},
            }, timeout=120) as r:
                r.raise_for_status()
                for line in r.iter_lines():
                    if not line:
                        continue
                    data = json.loads(line)
                    chunk = data.get("message", {}).get("content", "")
                    if chunk:
                        if first_token is None:
                            first_token = time.perf_counter()
                        chunk_count += 1
                        full_reply += chunk

        total_ms = (time.perf_counter() - t0) * 1000
        ttft_ms = (first_token - t0) * 1000 if first_token else 0
        gen_ms = total_ms - ttft_ms if first_token else 0
        tps = len(full_reply.split()) / (gen_ms / 1000) if gen_ms > 0 else 0

        print(f"\n  Run {i+1}/{runs}:")
        print(f"    TTFT:         {ttft_ms:.0f}ms")
        print(f"    generation:   {gen_ms:.0f}ms")
        print(f"    total:        {total_ms:.0f}ms")
        print(f"    chunks:       {chunk_count}")
        print(f"    reply chars:  {len(full_reply)}")
        print(f"    tok/s (approx): {tps:.1f}")
        results.append({
            "run": i + 1,
            "ttft_ms": ttft_ms,
            "gen_ms": gen_ms,
            "total_ms": total_ms,
            "chunks": chunk_count,
            "reply_chars": len(full_reply),
            "tps": tps,
        })

    _summary(results)
    return results


def bench_backend_sse(backend: str, runs: int = 3):
    """Test 3: Full round-trip through FastAPI backend SSE endpoint."""
    print(f"\n{'='*60}")
    print(f"TEST 3: Backend SSE (/chat)")
    print(f"  backend: {backend}")
    print(f"{'='*60}")

    # Verify backend is up
    try:
        with httpx.Client() as c:
            r = c.get(f"{backend}/health", timeout=5)
            r.raise_for_status()
    except Exception as e:
        print(f"  ERROR: backend unreachable: {e}")
        return []

    results = []
    for i in range(runs):
        t0 = time.perf_counter()
        first_token = None
        full_reply = ""
        chunk_count = 0
        user_id = f"bench-{i}"

        with httpx.Client() as c:
            with c.stream("POST", f"{backend}/chat",
                json={"message": PROMPT, "user_id": user_id},
                timeout=120,
            ) as r:
                r.raise_for_status()
                for line in r.iter_lines():
                    if not line:
                        continue
                    if line.startswith("data: ") and line != "data: [DONE]":
                        if first_token is None:
                            first_token = time.perf_counter()
                        chunk_count += 1
                        try:
                            chunk = json.loads(line[6:])
                        except json.JSONDecodeError:
                            chunk = line[6:]
                        full_reply += chunk

        total_ms = (time.perf_counter() - t0) * 1000
        ttft_ms = (first_token - t0) * 1000 if first_token else 0
        gen_ms = total_ms - ttft_ms if first_token else 0

        print(f"\n  Run {i+1}/{runs}:")
        print(f"    TTFT:         {ttft_ms:.0f}ms")
        print(f"    generation:   {gen_ms:.0f}ms")
        print(f"    total:        {total_ms:.0f}ms")
        print(f"    chunks:       {chunk_count}")
        print(f"    reply chars:  {len(full_reply)}")
        results.append({
            "run": i + 1,
            "ttft_ms": ttft_ms,
            "gen_ms": gen_ms,
            "total_ms": total_ms,
            "chunks": chunk_count,
            "reply_chars": len(full_reply),
        })

    _summary(results)
    return results


def bench_backend_endpoint(backend: str, runs: int = 3):
    """Test 4: Backend /benchmark endpoint (non-stream probe)."""
    print(f"\n{'='*60}")
    print(f"TEST 4: Backend /benchmark endpoint")
    print(f"  backend: {backend}")
    print(f"{'='*60}")

    results = []
    for i in range(runs):
        t0 = time.perf_counter()
        try:
            with httpx.Client() as c:
                r = c.get(f"{backend}/benchmark", timeout=120)
                r.raise_for_status()
                data = r.json()
        except Exception as e:
            print(f"  Run {i+1}: ERROR: {e}")
            continue

        wall_ms = (time.perf_counter() - t0) * 1000
        print(f"\n  Run {i+1}/{runs}:")
        print(f"    wall:         {wall_ms:.0f}ms")
        if "wall_ms" in data:
            print(f"    backend wall: {data['wall_ms']:.0f}ms")
        if "tokens_per_second" in data:
            print(f"    tok/s:        {data['tokens_per_second']:.1f}")
        if "eval_count" in data:
            print(f"    tokens:       {data['eval_count']}")
        if "reply_preview" in data:
            print(f"    reply:        {data['reply_preview'][:80]!r}")
        if "error" in data:
            print(f"    ERROR:        {data['error']}")
        results.append(data)

    _summary(results)
    return results


def _summary(results):
    if not results:
        print("\n  No results to summarize.")
        return
    print(f"\n  {'─'*40}")
    print(f"  SUMMARY ({len(results)} runs)")
    print(f"  {'─'*40}")
    for key in results[0]:
        if key == "run":
            continue
        vals = [r[key] for r in results if isinstance(r.get(key), (int, float))]
        if vals:
            avg = sum(vals) / len(vals)
            mn = min(vals)
            mx = max(vals)
            print(f"    {key:20s}  avg={avg:>8.1f}  min={mn:>8.1f}  max={mx:>8.1f}")


def main():
    parser = argparse.ArgumentParser(description="HR-agent latency benchmarks")
    parser.add_argument("--endpoint", default="http://localhost:5555", help="Ollama endpoint")
    parser.add_argument("--model", default="qwen3.6:35b", help="Ollama model name")
    parser.add_argument("--backend", default="http://localhost:8000", help="FastAPI backend URL")
    parser.add_argument("--runs", type=int, default=3, help="Runs per test")
    parser.add_argument("--think", action="store_true", help="Enable Qwen3 thinking mode")
    parser.add_argument("--ollama-only", action="store_true", help="Only test Ollama direct")
    parser.add_argument("--backend-only", action="store_true", help="Only test backend endpoints")
    args = parser.parse_args()

    think = args.think

    if not args.backend_only:
        bench_ollama_direct(args.endpoint, args.model, think=think, runs=args.runs)
        bench_ollama_stream(args.endpoint, args.model, think=think, runs=args.runs)

    if not args.ollama_only:
        bench_backend_sse(args.backend, runs=args.runs)
        bench_backend_endpoint(args.backend, runs=args.runs)


if __name__ == "__main__":
    main()
