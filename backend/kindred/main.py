"""FastAPI application and documented HTTP/WebSocket routes."""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import (
    FastAPI,
    File,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from .config import PROJECT_ROOT, Settings
from .daemon import CharacterDaemon
from .database import Database
from .llm import BackendUnavailable, LLMService
from .notifications import NotificationService
from .rate_limits import LimitExceeded, RateLimiter
from .schemas import (
    Character,
    CharacterCreate,
    CharacterUpdate,
    ChatRequest,
    ImageGenerationRequest,
    Message,
    SettingsUpdate,
    ThreadCreate,
)


def _load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def create_app(runtime_settings: Settings | None = None) -> FastAPI:
    """Application factory used by Uvicorn and isolated backend tests."""

    settings = runtime_settings or Settings.from_env()
    database = Database(settings.database_path)
    defaults = _load_json(PROJECT_ROOT / "config/defaults.json")
    database.initialize(defaults)
    database.seed_characters(_load_json(PROJECT_ROOT / "data/seed/characters.json"))
    llm = LLMService(settings, database)
    notifications = NotificationService(settings, database)
    daemon = CharacterDaemon(settings, database, llm, notifications)
    uploads = settings.database_path.parent / "uploads"
    uploads.mkdir(parents=True, exist_ok=True)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        daemon.start()
        yield
        await daemon.stop()

    app = FastAPI(
        title="Kindred API",
        version="0.1.0",
        description=(
            "Local-first character chat, logging, scheduling, notification, "
            "and optional cloud-provider API."
        ),
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.database = database
    app.state.llm = llm
    app.state.notifications = notifications
    app.state.daemon = daemon
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.mount("/uploads", StaticFiles(directory=uploads), name="uploads")

    @app.exception_handler(LimitExceeded)
    async def limit_handler(_: Request, exc: LimitExceeded) -> JSONResponse:
        return JSONResponse(status_code=429, content={"detail": str(exc)})

    @app.get("/api/health", tags=["system"])
    async def health() -> dict[str, Any]:
        """Report process health and live backend availability."""

        return {
            "status": "ok",
            "version": "0.1.0",
            "environment": settings.environment,
            "database": str(settings.database_path),
            "backends": await llm.backend_status(),
            "daemon": {
                "process_enabled": settings.daemon_enabled,
                "settings": database.get_settings().get("daemon", {}),
            },
        }

    @app.get("/api/characters", response_model=list[Character], tags=["characters"])
    def list_characters() -> list[dict[str, Any]]:
        return database.list_characters()

    @app.post("/api/characters", response_model=Character, status_code=201, tags=["characters"])
    def create_character(payload: CharacterCreate) -> dict[str, Any]:
        return database.create_character(payload.model_dump())

    @app.get("/api/characters/{character_id}", response_model=Character, tags=["characters"])
    def get_character(character_id: int) -> dict[str, Any]:
        character = database.get_character(character_id)
        if not character:
            raise HTTPException(404, "Character not found")
        return character

    @app.patch("/api/characters/{character_id}", response_model=Character, tags=["characters"])
    def update_character(character_id: int, payload: CharacterUpdate) -> dict[str, Any]:
        character = database.update_character(character_id, payload.model_dump(exclude_none=True))
        if not character:
            raise HTTPException(404, "Character not found")
        return character

    @app.delete("/api/characters/{character_id}", status_code=204, tags=["characters"])
    def delete_character(character_id: int) -> Response:
        if not database.delete_character(character_id):
            raise HTTPException(404, "Character not found")
        return Response(status_code=204)

    @app.post(
        "/api/characters/{character_id}/duplicate",
        response_model=Character,
        status_code=201,
        tags=["characters"],
    )
    def duplicate_character(character_id: int) -> dict[str, Any]:
        character = database.duplicate_character(character_id)
        if not character:
            raise HTTPException(404, "Character not found")
        return character

    @app.post("/api/characters/{character_id}/avatar", tags=["characters"])
    async def upload_avatar(character_id: int, file: UploadFile = File(...)) -> dict[str, str]:
        """Save a small local avatar and update the character profile."""

        if not database.get_character(character_id):
            raise HTTPException(404, "Character not found")
        if file.content_type not in {"image/jpeg", "image/png", "image/webp", "image/gif"}:
            raise HTTPException(415, "Avatar must be JPEG, PNG, WebP, or GIF")
        content = await file.read()
        if len(content) > 5 * 1024 * 1024:
            raise HTTPException(413, "Avatar exceeds the 5 MB limit")
        suffix = {
            "image/jpeg": ".jpg",
            "image/png": ".png",
            "image/webp": ".webp",
            "image/gif": ".gif",
        }[file.content_type]
        path = uploads / f"character-{character_id}{suffix}"
        path.write_bytes(content)
        url = f"/uploads/{path.name}"
        database.update_character(character_id, {"avatar_url": url})
        return {"avatar_url": url}

    @app.get("/api/threads", tags=["chat"])
    def list_threads(character_id: int | None = None) -> list[dict[str, Any]]:
        return database.list_threads(character_id)

    @app.post("/api/threads", status_code=201, tags=["chat"])
    def create_thread(payload: ThreadCreate) -> dict[str, Any]:
        if not database.get_character(payload.character_id):
            raise HTTPException(404, "Character not found")
        return database.create_thread(payload.character_id, payload.title)

    @app.get("/api/threads/{thread_id}/messages", response_model=list[Message], tags=["chat"])
    def list_messages(thread_id: int, limit: int = Query(default=200, ge=1, le=1000)):
        if not database.get_thread(thread_id):
            raise HTTPException(404, "Thread not found")
        return database.list_messages(thread_id, limit)

    @app.post("/api/threads/{thread_id}/messages", response_model=Message, tags=["chat"])
    async def send_message(thread_id: int, payload: ChatRequest) -> dict[str, Any]:
        """Log the user message, generate one character reply, and notify clients."""

        thread = database.get_thread(thread_id)
        if not thread:
            raise HTTPException(404, "Thread not found")
        character = database.get_character(thread["character_id"])
        if not character:
            raise HTTPException(404, "Character not found")
        database.add_message(
            thread_id,
            character["id"],
            "user",
            payload.content,
            prompt_context_summary="User-authored message.",
        )
        history = database.list_messages(thread_id, limit=40)
        try:
            generated, summary, rationale = await llm.respond(character, history)
        except BackendUnavailable as exc:
            raise HTTPException(503, str(exc)) from exc
        message = database.add_message(
            thread_id,
            character["id"],
            "character",
            generated.content,
            backend=generated.backend,
            model=generated.model,
            prompt_context_summary=summary,
            character_rationale=rationale,
        )
        await notifications.publish(
            {
                "type": "character_message",
                "message": message,
                "thread_id": thread_id,
                "character_id": character["id"],
                "character_name": character["name"],
                "content": generated.content,
            }
        )
        return message

    @app.get("/api/messages/recent", tags=["chat"])
    def recent_messages(limit: int = Query(default=50, ge=1, le=500)) -> list[dict[str, Any]]:
        return database.search_logs(limit=limit)

    @app.get("/api/logs", tags=["logs"])
    def search_logs(
        character_id: int | None = None,
        keyword: str = "",
        date_from: str = "",
        date_to: str = "",
        limit: int = Query(default=500, ge=1, le=5000),
    ) -> list[dict[str, Any]]:
        return database.search_logs(
            character_id=character_id,
            keyword=keyword,
            date_from=date_from,
            date_to=date_to,
            limit=limit,
        )

    @app.get("/api/logs/export", tags=["logs"])
    def export_logs(
        format: str = Query(default="markdown", pattern="^(markdown|json)$"),
        character_id: int | None = None,
        keyword: str = "",
        date_from: str = "",
        date_to: str = "",
    ) -> Response:
        records = list(
            reversed(
                database.search_logs(
                    character_id=character_id,
                    keyword=keyword,
                    date_from=date_from,
                    date_to=date_to,
                    limit=5000,
                )
            )
        )
        if format == "json":
            return JSONResponse(
                records,
                headers={"Content-Disposition": 'attachment; filename="kindred-logs.json"'},
            )
        lines = ["# Kindred conversation export", ""]
        active_thread: int | None = None
        for record in records:
            if record["thread_id"] != active_thread:
                active_thread = record["thread_id"]
                lines.extend([f"## {record['character_name']} — {record['thread_title']}", ""])
            speaker = "You" if record["sender"] == "user" else record["character_name"]
            lines.extend(
                [
                    f"**{speaker}** · {record['timestamp']}",
                    "",
                    record["content"],
                    "",
                    (
                        f"_Backend: {record['backend'] or 'n/a'} / {record['model'] or 'n/a'}; "
                        f"context: {record['prompt_context_summary'] or 'n/a'}; "
                        f"rationale: {record['character_rationale'] or 'n/a'}_"
                    ),
                    "",
                ]
            )
        return PlainTextResponse(
            "\n".join(lines),
            media_type="text/markdown",
            headers={"Content-Disposition": 'attachment; filename="kindred-logs.md"'},
        )

    @app.get("/api/settings", tags=["settings"])
    def get_settings() -> dict[str, Any]:
        return database.get_settings()

    @app.patch("/api/settings", tags=["settings"])
    def update_settings(payload: SettingsUpdate) -> dict[str, Any]:
        current = database.get_settings().get(payload.section)
        if isinstance(current, dict) and isinstance(payload.value, dict):
            value = {**current, **payload.value}
        else:
            value = payload.value
        database.set_setting(payload.section, value)
        return database.get_settings()

    @app.get("/api/usage", tags=["settings"])
    def usage() -> dict[str, object]:
        return RateLimiter(database).summary()

    @app.post("/api/images/generate", tags=["settings"])
    def generate_image(payload: ImageGenerationRequest) -> dict[str, Any]:
        """Meter a provider-neutral image task; live image adapters follow post-MVP."""

        limiter = RateLimiter(database)
        limiter.check_cloud(estimated_tokens=0, request_kind="image")
        dry_run = payload.dry_run or settings.cloud_dry_run
        database.log_usage(
            provider=payload.provider,
            model="image-provider-placeholder",
            request_kind="image",
            dry_run=dry_run,
            character_id=payload.character_id,
        )
        if not dry_run:
            raise HTTPException(
                501,
                "Live image generation is a provider adapter placeholder in the MVP; use dry run.",
            )
        return {
            "status": "dry_run",
            "provider": payload.provider,
            "prompt_preview": payload.prompt[:160],
            "warning": "No external request was made.",
        }

    @app.get("/api/notifications/public-key", tags=["notifications"])
    def notification_public_key() -> dict[str, Any]:
        return {
            "public_key": settings.vapid_public_key,
            "web_push_configured": bool(settings.vapid_private_key and settings.vapid_public_key),
        }

    @app.post("/api/notifications/subscribe", status_code=201, tags=["notifications"])
    async def subscribe(request: Request) -> dict[str, str]:
        subscription = await request.json()
        try:
            database.save_subscription(subscription)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        return {"status": "subscribed"}

    @app.delete("/api/notifications/subscribe", status_code=204, tags=["notifications"])
    async def unsubscribe(request: Request) -> Response:
        body = await request.json()
        database.delete_subscription(body.get("endpoint", ""))
        return Response(status_code=204)

    @app.websocket("/api/events/ws")
    async def event_socket(socket: WebSocket) -> None:
        await notifications.connect(socket)
        try:
            while True:
                await socket.receive_text()
        except WebSocketDisconnect:
            notifications.disconnect(socket)

    @app.post("/api/daemon/run-once", tags=["daemon"])
    async def run_daemon_once(character_id: int | None = None) -> list[dict[str, Any]]:
        """Run one decision cycle; character_id forces a message for smoke testing."""

        return await daemon.run_once(force_character_id=character_id)

    frontend_dist = PROJECT_ROOT / "frontend/dist"
    if frontend_dist.exists():
        assets = frontend_dist / "assets"
        if assets.exists():
            app.mount("/assets", StaticFiles(directory=assets), name="frontend-assets")

        @app.get("/{path:path}", include_in_schema=False)
        def frontend(path: str) -> FileResponse:
            requested = (frontend_dist / path).resolve()
            if (
                path
                and requested.is_relative_to(frontend_dist.resolve())
                and requested.is_file()
            ):
                return FileResponse(requested)
            return FileResponse(frontend_dist / "index.html")

    return app


app = create_app()
