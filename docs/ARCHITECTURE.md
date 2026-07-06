# Architecture

Kindred is a single-user, local-first web application. The production shape is
one FastAPI process, one SQLite database, one static React bundle, and one
separate local inference server. There is no required cloud service.

```text
Browser
  ├─ HTTP/JSON ───────────────┐
  ├─ WebSocket live events ───┤
  └─ Service Worker/Web Push ─┤
                              ▼
FastAPI process
  ├─ API routes and static frontend
  ├─ SQLite repository
  ├─ character daemon
  ├─ notification fan-out
  ├─ cloud limiter/usage ledger
  └─ model adapter
        ├─ Ollama /api/chat (default, local)
        ├─ llama.cpp /v1/chat/completions (local)
        └─ OpenAI-compatible /chat/completions (optional cloud)
```

The daemon is intentionally in-process for the MVP. Run one FastAPI replica;
multiple replicas would each start a scheduler and require distributed locking.

## Backend modules

| Module | Responsibility |
| --- | --- |
| `config.py` | Environment parsing and safe defaults |
| `database.py` | Schema creation and explicit SQLite repository operations |
| `schemas.py` | Pydantic API contracts |
| `llm.py` | Prompt construction and backend adapters |
| `rate_limits.py` | Pre-call cloud budgets backed by the usage ledger |
| `daemon.py` | Pure scheduling policy plus async execution loop |
| `notifications.py` | WebSocket fan-out and optional Web Push |
| `main.py` | Application factory, routes, lifespan, and static serving |

Every database operation opens a short-lived connection, enables foreign keys
and WAL mode, and commits or rolls back as one unit. This is simple and robust
for a personal service on Pi-class hardware.

## Data model

- `characters`: profile, model choice, temperature, initiative, cooldown.
- `threads`: conversations belonging to one character.
- `messages`: content plus timestamp, backend/model, context summary, safe
  character rationale, and autonomous-message marker.
- `app_settings`: JSON values by settings section.
- `usage_logs`: cloud requests, tokens, estimated cost, task kind, dry-run.
- `push_subscriptions`: browser Web Push subscription JSON.
- `daemon_state`: last check, last initiated message, and decision note.

Deleting a character cascades to their threads, messages, and daemon state.
Usage rows keep accounting history but null the deleted character reference.

## Chat request sequence

1. The API validates and stores the user message.
2. It loads at most 20 recent user/character messages for model context.
3. A system prompt is assembled from profile fields and optional world notes.
4. The character's selected adapter runs. Cloud adapters check every configured
   budget before dispatch.
5. The response and safe audit metadata are stored.
6. Open clients receive a WebSocket event; saved push subscriptions are
   notified when Web Push is configured.

If generation fails, the user message remains logged and the API returns a
clear `503`. This preserves what the user wrote and avoids fabricating a reply.

## Autonomous scheduling

On each interval, `should_initiate` applies these gates in order:

1. process and persisted daemon enablement;
2. character initiative above zero;
3. quiet hours;
4. time since the latest message versus character cooldown;
5. global autonomous hourly and daily caps;
6. Poisson-style probability `1 - exp(-frequency × elapsed_days)`.

The pure decision function is unit tested. Forced runs in
`POST /api/daemon/run-once?character_id=…` bypass scheduling gates for manual
verification but still use the character's configured model backend.

## API routes

FastAPI serves live OpenAPI docs at `/docs` and the schema at `/openapi.json`.

| Method and path | Purpose |
| --- | --- |
| `GET /api/health` | Process, daemon, database, and backend status |
| `GET/POST /api/characters` | List or create characters |
| `GET/PATCH/DELETE /api/characters/{id}` | Character detail and mutation |
| `POST /api/characters/{id}/duplicate` | Copy a character profile |
| `POST /api/characters/{id}/avatar` | Store a local image up to 5 MB |
| `GET/POST /api/threads` | List or create conversation threads |
| `GET /api/threads/{id}/messages` | Read a thread |
| `POST /api/threads/{id}/messages` | Store user message and generate reply |
| `GET /api/messages/recent` | Recent messages across characters |
| `GET /api/logs` | Character/date/keyword search |
| `GET /api/logs/export` | Download Markdown or JSON |
| `GET/PATCH /api/settings` | Read or update settings sections |
| `GET /api/usage` | Current cloud usage windows and configured limits |
| `POST /api/images/generate` | Metered image-provider dry-run placeholder |
| `GET /api/notifications/public-key` | VAPID public configuration |
| `POST/DELETE /api/notifications/subscribe` | Manage push subscription |
| `WS /api/events/ws` | Live character-message events |
| `POST /api/daemon/run-once` | Run one scheduler cycle or forced character |

## Security boundaries

- There is no user authentication or tenant isolation in the MVP.
- Prompts and logs are local unless a character opts into a cloud backend.
- World notes become part of a cloud prompt for cloud-enabled characters.
- VAPID keys authorize push delivery; the private key must remain secret.
- Character prompt fields are untrusted model input. They do not grant system or
  filesystem access; model adapters expose chat completion only.
- The image endpoint is a dry-run placeholder and makes no live image request.

