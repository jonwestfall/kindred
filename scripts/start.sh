#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT/frontend"
npm run build
cd "$ROOT"

ENV_ARGS=()
if [[ -f "${KINDRED_ENV_FILE:-$ROOT/.env}" ]]; then
  ENV_ARGS=(--env-file "${KINDRED_ENV_FILE:-$ROOT/.env}")
fi

exec "$ROOT/.venv/bin/uvicorn" kindred.main:app \
  --app-dir backend \
  --host "${KINDRED_HOST:-0.0.0.0}" \
  --port "${KINDRED_PORT:-8000}" \
  "${ENV_ARGS[@]}"
