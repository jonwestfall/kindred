# Kindred

Kindred is a local-first, open-source web app for creating and chatting with
fictional, literary, and custom characters. A local Ollama or llama.cpp server
is the default model provider. Optional cloud calls are explicit, metered, and
guarded by configurable budgets.

The backend API, local persistence, model adapters, autonomous daemon, usage
guardrails, push event plumbing, and test suite are implemented. The web client
and deployment documentation are the next milestone.

## Repository layout

```text
backend/   FastAPI API, SQLite persistence, model adapters, and daemon
frontend/  Lightweight React/Vite web interface and service worker
docs/      Architecture, installation, operations, and limitations
scripts/   Development, smoke-test, seed, and key-generation helpers
config/    Committed safe defaults
data/      Runtime SQLite data (ignored) and committed example seeds
docker/    Multi-architecture container definitions
```

The target development platform is macOS Apple Silicon. Deployment targets
include Raspberry Pi 400 and Raspberry Pi 4 with a 64-bit operating system.
