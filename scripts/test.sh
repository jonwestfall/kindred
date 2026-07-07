#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
"$ROOT/.venv/bin/pytest" "$ROOT/backend"
(
  cd "$ROOT/frontend"
  npm run build
)

echo "Unit tests and production frontend build passed."
echo "For browser coverage, start Kindred plus scripts/mock_ollama.py, then run:"
echo "  MOCK_OLLAMA_PORT=11436 python3 scripts/mock_ollama.py"
echo "  OLLAMA_BASE_URL=http://127.0.0.1:11436 .venv/bin/uvicorn kindred.main:app --app-dir backend"
echo "  cd frontend && npm run test:e2e"
