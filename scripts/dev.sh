#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ ! -x "$ROOT/.venv/bin/uvicorn" ]]; then
  echo "Missing .venv. Run: python3 -m venv .venv && .venv/bin/pip install -e './backend[dev,notifications]'" >&2
  exit 1
fi

if [[ ! -d "$ROOT/frontend/node_modules" ]]; then
  echo "Missing frontend dependencies. Run: cd frontend && npm install" >&2
  exit 1
fi

cleanup() {
  kill "${BACKEND_PID:-}" "${FRONTEND_PID:-}" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

ENV_ARGS=()
if [[ -f "${KINDRED_ENV_FILE:-$ROOT/.env}" ]]; then
  ENV_ARGS=(--env-file "${KINDRED_ENV_FILE:-$ROOT/.env}")
fi

(
  cd "$ROOT"
  "$ROOT/.venv/bin/uvicorn" kindred.main:app \
    --app-dir backend \
    --host 127.0.0.1 \
    --port 8000 \
    --reload \
    "${ENV_ARGS[@]}"
) &
BACKEND_PID=$!

(
  cd "$ROOT/frontend"
  npm run dev
) &
FRONTEND_PID=$!

echo "Kindred API: http://127.0.0.1:8000/docs"
echo "Kindred web: http://127.0.0.1:5173"
wait
