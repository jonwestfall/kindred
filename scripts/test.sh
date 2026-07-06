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
echo "  cd frontend && npm run test:e2e"

