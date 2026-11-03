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

# --no-cache: always hit the API. promptfoo's own exit code is ignored (summarize.py decides),
# but if it produced no results file at all, show its log so the failure is debuggable.
rm -f safety/reports/latest.json
npx -y promptfoo@0.125.1 eval -c safety/promptfooconfig.yaml --no-cache --no-progress-bar \
  -o safety/reports/latest.json > safety/reports/promptfoo.log 2>&1 || true
if [ ! -f safety/reports/latest.json ]; then
  echo "promptfoo produced no results. Its output:" >&2
  tail -40 safety/reports/promptfoo.log >&2
  exit 1
fi
uv run python -m safety.summarize safety/reports/latest.json
