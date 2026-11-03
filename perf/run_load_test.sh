#!/usr/bin/env bash
# Runs the Locust load test against a local server using the mock LLM (no API credits).
#   ./perf/run_load_test.sh [mock_latency_ms]     e.g. 0 (app overhead only) or 800 (slow model)
set -euo pipefail
cd "$(dirname "$0")/.."
LATENCY="${1:-0}"
NAME="mock-latency-${LATENCY}ms"
PORT="${PORT:-8040}"
export LLM_PROVIDER=mock MOCK_LATENCY_MS="$LATENCY" DB_PATH="$(mktemp -d)/load.db"

uv run uvicorn app.main:app --port "$PORT" --log-level warning > /dev/null 2>&1 &
SERVER_PID=$!
trap 'kill $SERVER_PID 2>/dev/null || true' EXIT
for _ in $(seq 1 60); do curl -sf "localhost:$PORT/health" > /dev/null && break; sleep 0.5; done

uv run locust -f perf/locustfile.py --headless --host "http://127.0.0.1:$PORT" \
  --csv "perf/reports/$NAME" --html "perf/reports/$NAME.html" --only-summary > /dev/null 2>&1 || true
uv run python -m perf.summarize "perf/reports/$NAME" "$DB_PATH" "mock LLM, simulated model latency ${LATENCY} ms"
