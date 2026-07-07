# Development

## Toolchain

- Python 3.11+ and FastAPI
- standard-library `sqlite3`
- React 19, TypeScript, and Vite
- pytest for backend policy/persistence coverage
- Playwright for production-bundle browser coverage

The runtime avoids an ORM, job queue, component library, Markdown parser, and
frontend data framework. This keeps the Pi footprint and maintenance surface
small.

## Setup

```bash
cp .env.example .env
# Edit KINDRED_ADMIN_PASSWORD and KINDRED_SESSION_SECRET if testing auth manually.
python3 -m venv .venv
.venv/bin/pip install -e './backend[dev,notifications]'
cd frontend && npm install && cd ..
./scripts/dev.sh
```

`scripts/dev.sh` loads `.env` when present and shuts down both child processes
on exit.

## Common commands

```bash
.venv/bin/pytest backend
.venv/bin/python -m compileall -q backend/kindred
cd frontend && npm run typecheck
cd frontend && npm run build
./scripts/test.sh
```

The API app factory accepts an explicit `Settings` object, allowing tests to use
isolated temporary databases and disable the scheduler.

Most backend tests set `KINDRED_AUTH_ENABLED=false` through test settings for
legacy route coverage. Auth-specific tests run with authentication enabled and
verify administrator login, user creation, character grants, and disabled-user
revocation.

## Browser tests

Build the production bundle, then run an isolated app and deterministic model
double:

```bash
cd frontend && npm run build && cd ..
MOCK_OLLAMA_PORT=11436 python3 scripts/mock_ollama.py
KINDRED_DATABASE_PATH=/tmp/kindred-e2e.db \
KINDRED_DAEMON_ENABLED=false \
KINDRED_ADMIN_USERNAME=admin \
KINDRED_ADMIN_PASSWORD=change-me-now \
OLLAMA_BASE_URL=http://127.0.0.1:11436 \
  .venv/bin/uvicorn kindred.main:app --app-dir backend
```

In another terminal:

```bash
cd frontend
npm run test:e2e
```

The suite verifies character creation, chat, forced autonomous initiation,
notification setup fallback, activity, JSON download, console health, and a
390×844 viewport.

## Notification tests

For a running HTTPS/VAPID deployment, use the dependency-free notification smoke
script:

```bash
KINDRED_ADMIN_USERNAME=admin \
KINDRED_ADMIN_PASSWORD='your-password' \
python3 scripts/test_notifications.py https://your-machine.your-tailnet.ts.net
```

Add `--daemon` to force the real autonomous generation route after the delivery
test. See [Notification testing](NOTIFICATION_TESTING.md) for the iPhone,
Tailscale, Admin UI, and curl test matrix.

## Adding a model backend

1. Add a validated backend literal in `schemas.py`.
2. Add dispatch and an adapter in `llm.py`.
3. Normalize output into `LLMResult`.
4. Classify it as local or cloud. Every cloud adapter must call
   `RateLimiter.check_cloud` before network I/O and log usage afterward.
5. Add the editor option and cloud-warning behavior.
6. Test success and failure without real credentials.
7. Update `CLOUD_BACKENDS.md` or `LOCAL_MODELS.md`.

## Schema changes

`SCHEMA` handles initial creation but is not a general migration framework.
Before changing a shipped column:

1. copy the database;
2. add a schema-version table and explicit idempotent migration;
3. test upgrading from the last release;
4. document rollback.

Do not ask users to delete their database to upgrade.

## Logging policy

Store application-visible rationale summaries, not hidden chain-of-thought.
Logs may contain sensitive writing; never include `data/` in bug reports without
review and redaction.

## Code and contribution style

- Major modules and non-obvious policy functions need docstrings/comments.
- Keep scheduling decisions pure where possible.
- Keep API shapes typed.
- Prefer small React components and parallel independent fetches.
- Avoid heavy dependencies for straightforward platform features.
- Use focused commits.

Run `git diff --check`, backend tests, frontend build, and the relevant browser
flow before submitting. Never commit `.env`, SQLite databases, uploads, API
keys, PEM files, model weights, generated logs, Playwright reports, or builds.
