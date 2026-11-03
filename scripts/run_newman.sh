#!/usr/bin/env bash
# Starts the API (mock LLM, throwaway DB) and runs the generated Postman collection with Newman.
set -euo pipefail
cd "$(dirname "$0")/.."
PORT="${PORT:-8030}"
export LLM_PROVIDER="${LLM_PROVIDER:-mock}" DB_PATH="$(mktemp -d)/newman.db"

uv run uvicorn app.main:app --port "$PORT" > /dev/null 2>&1 &
SERVER_PID=$!
trap 'kill $SERVER_PID 2>/dev/null || true' EXIT
for _ in $(seq 1 60); do curl -sf "localhost:$PORT/health" > /dev/null && break; sleep 0.5; done

mkdir -p reports
npx -y newman@6 run postman/docuchat.postman_collection.json \
  --env-var "baseUrl=http://127.0.0.1:$PORT" \
  --reporters cli,junit --reporter-junit-export reports/newman-junit.xml
