#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT/frontend"
npm run build
cd "$ROOT"

ENV_ARGS=()
ENV_FILE="${KINDRED_ENV_FILE:-$ROOT/.env}"
if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
  ENV_ARGS=(--env-file "$ENV_FILE")
fi

exec "$ROOT/.venv/bin/uvicorn" kindred.main:app \
  --app-dir backend \
  --host "${KINDRED_HOST:-0.0.0.0}" \
  --port "${KINDRED_PORT:-8000}" \
  "${ENV_ARGS[@]}"
