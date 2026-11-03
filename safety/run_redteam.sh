#!/usr/bin/env bash
# Starts the API on a throwaway DB, runs the promptfoo red-team against it, then summarises.
# LLM_PROVIDER defaults to "recorded" (replays safety/cassettes/redteam.jsonl); set it to
# "anthropic" with an API key to attack a live model instead.
set -euo pipefail
cd "$(dirname "$0")/.."

export LLM_PROVIDER="${LLM_PROVIDER:-recorded}"
export CASSETTE_PATH="safety/cassettes/redteam.jsonl"
export DB_PATH="$(mktemp -d)/redteam.db"
PORT=8020

uv run uvicorn app.main:app --port "$PORT" > /dev/null 2>&1 &
SERVER_PID=$!
trap 'kill $SERVER_PID 2>/dev/null || true' EXIT
for _ in $(seq 1 60); do curl -sf "localhost:$PORT/health" > /dev/null && break; sleep 0.5; done

# --no-cache: always hit the API; exit code is ignored here and checked by summarize.py instead.
npx -y promptfoo@0.125.1 eval -c safety/promptfooconfig.yaml --no-cache --no-progress-bar \
  -o safety/reports/latest.json > /dev/null || true
uv run python -m safety.summarize safety/reports/latest.json
