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
ENV_FILE="${KINDRED_ENV_FILE:-$ROOT/.env}"
if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
  ENV_ARGS=(--env-file "$ENV_FILE")
fi

KINDRED_DEV_HOST="${KINDRED_DEV_HOST:-127.0.0.1}"
KINDRED_PORT="${KINDRED_PORT:-8000}"
KINDRED_API_PROXY="${KINDRED_API_PROXY:-http://127.0.0.1:$KINDRED_PORT}"

(
  cd "$ROOT"
  "$ROOT/.venv/bin/uvicorn" kindred.main:app \
    --app-dir backend \
    --host "$KINDRED_DEV_HOST" \
    --port "$KINDRED_PORT" \
    --reload \
    "${ENV_ARGS[@]}"
) &
BACKEND_PID=$!

(
  cd "$ROOT/frontend"
  KINDRED_API_PROXY="$KINDRED_API_PROXY" npm run dev
) &
FRONTEND_PID=$!

echo "Kindred API: http://127.0.0.1:$KINDRED_PORT/docs"
echo "Kindred web: http://127.0.0.1:5173"
wait
