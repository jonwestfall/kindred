"""FastAPI application and documented HTTP/WebSocket routes."""

from __future__ import annotations

import json
import platform
import shutil
import sys
import tempfile
import zipfile
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from hmac import compare_digest as hmac_compare
from importlib import metadata
from pathlib import Path
from re import sub
from typing import Any, Literal

from fastapi import (
    Depends,
    FastAPI,
    File,
    Header,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from starlette.background import BackgroundTask
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from .auth import (
    Principal,
    authenticate_request,
    create_token,
    hash_password,
    parse_token,
    require_admin,
    verify_password,
    websocket_token_from_header_or_query,
)
from .config import PROJECT_ROOT, Settings
from .daemon import CharacterDaemon
from .database import Database
from .llm import BackendUnavailable, LLMService
from .notifications import NotificationService
from .rate_limits import LimitExceeded, RateLimiter
from .schemas import (
    Character,
    CharacterBase,
    CharacterCardBundle,
    CharacterCardProfile,
    CharacterCreate,
    CharacterImportResult,
    CharacterUpdate,
    ChatRequest,
    ImageGenerationRequest,
    LorePack,
    LorePackAssignment,
    LorePackFile,
    LoginRequest,
    LoginResponse,
    Message,
    NotificationTestRequest,
    NotificationTestResult,
    SessionInfo,
    SettingsUpdate,
    SystemResetRequest,
    ThreadCreate,
    UserCreate,
    UserOut,
    UserUpdate,
)


REPOSITORY_URL = "https://github.com/jonwestfall/kindred"
BACKUP_SCHEMA = "kindred.backup.v1"


def _load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _package_version() -> str:
    """Return the installed backend package version."""

    try:
        return metadata.version("kindred")
    except metadata.PackageNotFoundError:
        return "0.1.0"


def _frontend_version() -> str:
    """Return the frontend package version without importing Node tooling."""

    package = PROJECT_ROOT / "frontend/package.json"
    if not package.exists():
        return "unknown"
    return str(_load_json(package).get("version", "unknown"))


_CHARACTER_FIELD_NAMES = set(CharacterBase.model_fields)


def _safe_filename(value: str) -> str:
    """Create a conservative download filename component."""

    cleaned = sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip("-").lower()
    return cleaned or "character"


def _character_to_card(character: dict[str, Any]) -> CharacterCardProfile:
    """Convert a stored database row into a portable card profile."""

    return CharacterCardProfile(**{field: character[field] for field in _CHARACTER_FIELD_NAMES})


def _bundle_for_characters(characters: list[dict[str, Any]]) -> CharacterCardBundle:
    """Build a versioned export bundle with current UTC timestamp."""

    return CharacterCardBundle(
        exported_at=datetime.now(UTC),
        characters=[_character_to_card(character) for character in characters],
    )


def _file_for_lore_pack(pack: dict[str, Any]) -> LorePackFile:
    """Convert a stored lore pack into a portable fact-pack file."""

    return LorePackFile(
        exported_at=datetime.now(UTC),
        name=pack["name"],
        description=pack["description"],
        source_title=pack["source_title"],
        source_author=pack["source_author"],
        source_reference=pack["source_reference"],
        facts=pack["facts"],
    )


def _safe_zip_members(archive: zipfile.ZipFile) -> None:
    """Reject absolute or parent-traversing backup entries."""

    for member in archive.namelist():
        path = Path(member)
        if path.is_absolute() or ".." in path.parts:
            raise HTTPException(400, "Backup contains an unsafe path")


def _add_uploads_to_backup(archive: zipfile.ZipFile, uploads: Path) -> int:
    """Add uploaded local files to a backup archive."""

    if not uploads.exists():
        return 0
    count = 0
    for path in uploads.rglob("*"):
        if path.is_file():
            archive.write(path, f"uploads/{path.relative_to(uploads).as_posix()}")
            count += 1
    return count


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

    def _include_all(principal: Principal) -> bool:
        return principal.is_admin

    def _require_character_access(character_id: int, principal: Principal) -> None:
        if not database.get_character(character_id):
            raise HTTPException(404, "Character not found")
        if not database.character_is_allowed(
            principal.user_id,
            character_id,
            include_all=_include_all(principal),
        ):
            raise HTTPException(403, "Character is not assigned to this account")

    def _require_thread_access(thread_id: int, principal: Principal) -> dict[str, Any]:
        thread = database.get_thread(thread_id)
        if not thread:
            raise HTTPException(404, "Thread not found")
        if not database.thread_belongs_to_user(
            thread_id,
            principal.user_id,
            include_all=_include_all(principal),
        ):
            raise HTTPException(403, "Thread is not available to this account")
        return thread

    def _principal_from_download_token(access_token: str, authorization: str | None) -> Principal:
        if not settings.auth_enabled:
            return Principal(username="local-admin", role="admin")
        token = access_token
        if not token and authorization and authorization.lower().startswith("bearer "):
            token = authorization.split(" ", 1)[1]
        if not token:
            raise HTTPException(401, "Authentication required")
        principal = parse_token(token, settings)
        if not principal.is_admin:
            user = database.get_user(principal.user_id)
            if not user or user["disabled"]:
                raise HTTPException(403, "Account is disabled")
        return principal

    @app.post("/api/auth/login", response_model=LoginResponse, tags=["auth"])
    def login(payload: LoginRequest) -> dict[str, Any]:
        """Authenticate the env-admin or a SQLite-backed regular user."""

        username = payload.username.strip()
        if (
            hmac_compare(username, settings.admin_username)
            and hmac_compare(payload.password, settings.admin_password)
        ):
            principal = Principal(username=settings.admin_username, role="admin")
            return {
                "token": create_token(principal, settings),
                "session": SessionInfo(username=principal.username, role=principal.role, user_id=None),
            }
        user = database.get_user_by_username(username)
        if not user or user["disabled"] or not verify_password(payload.password, user["password_hash"]):
            raise HTTPException(401, "Invalid username or password")
        principal = Principal(username=user["username"], role="user", user_id=user["id"])
        return {
            "token": create_token(principal, settings),
            "session": SessionInfo(username=principal.username, role=principal.role, user_id=principal.user_id),
        }

    @app.get("/api/auth/me", response_model=SessionInfo, tags=["auth"])
    def me(principal: Principal = Depends(authenticate_request)) -> dict[str, Any]:
        return {"username": principal.username, "role": principal.role, "user_id": principal.user_id}

    @app.get("/api/users", response_model=list[UserOut], tags=["admin"])
    def list_users(_: Principal = Depends(require_admin)) -> list[dict[str, Any]]:
        return database.list_users()

    @app.post("/api/users", response_model=UserOut, status_code=201, tags=["admin"])
    def create_user(payload: UserCreate, _: Principal = Depends(require_admin)) -> dict[str, Any]:
        try:
            return database.create_user(
                username=payload.username.strip(),
                display_name=payload.display_name.strip(),
                password_hash=hash_password(payload.password),
                disabled=payload.disabled,
                character_ids=payload.character_ids,
            )
        except Exception as exc:
            raise HTTPException(409, "User could not be created; username may already exist") from exc

    @app.patch("/api/users/{user_id}", response_model=UserOut, tags=["admin"])
    def update_user(
        user_id: int,
        payload: UserUpdate,
        _: Principal = Depends(require_admin),
    ) -> dict[str, Any]:
        user = database.update_user(
            user_id,
            username=payload.username.strip() if payload.username is not None else None,
            display_name=payload.display_name.strip() if payload.display_name is not None else None,
            password_hash=hash_password(payload.password) if payload.password else None,
            disabled=payload.disabled,
            character_ids=payload.character_ids,
        )
        if not user:
            raise HTTPException(404, "User not found")
        return user

    @app.delete("/api/users/{user_id}", status_code=204, tags=["admin"])
    def delete_user(user_id: int, _: Principal = Depends(require_admin)) -> Response:
        if not database.delete_user(user_id):
            raise HTTPException(404, "User not found")
        return Response(status_code=204)

    @app.get("/api/health", tags=["system"])
    async def health() -> dict[str, Any]:
        """Report process health and live backend availability."""

        api_version = _package_version()
        frontend_version = _frontend_version()
        return {
            "status": "ok",
            "version": api_version,
            "repository_url": REPOSITORY_URL,
            "api": {
                "version": api_version,
                "build": settings.build_number,
            },
            "frontend": {
                "version": frontend_version,
                "build": settings.frontend_build_number,
            },
            "runtime": {
                "python": sys.version.split()[0],
                "platform": platform.platform(),
                "build": settings.build_number,
            },
            "environment": settings.environment,
            "database": str(settings.database_path),
            "database_schema_version": database.schema_version(),
            "backends": await llm.backend_status(),
            "daemon": {
                "process_enabled": settings.daemon_enabled,
                "settings": database.get_settings().get("daemon", {}),
            },
        }

    @app.get("/api/characters", response_model=list[Character], tags=["characters"])
    def list_characters(principal: Principal = Depends(authenticate_request)) -> list[dict[str, Any]]:
        return database.list_characters(principal.user_id, include_all=_include_all(principal))

    @app.post("/api/characters", response_model=Character, status_code=201, tags=["characters"])
    def create_character(payload: CharacterCreate, _: Principal = Depends(require_admin)) -> dict[str, Any]:
        return database.create_character(payload.model_dump())

    @app.get("/api/characters/export", tags=["characters"])
    def export_all_characters(
        access_token: str = "",
        authorization: str | None = Header(default=None),
    ) -> JSONResponse:
        """Download all character profiles as a portable Kindred card bundle."""

        principal = _principal_from_download_token(access_token, authorization)
        if not principal.is_admin:
            raise HTTPException(403, "Administrator access required")
        bundle = _bundle_for_characters(database.list_characters())
        return JSONResponse(
            jsonable_encoder(bundle),
            headers={"Content-Disposition": 'attachment; filename="kindred-characters.json"'},
        )

    @app.post(
        "/api/characters/import",
        response_model=CharacterImportResult,
        status_code=201,
        tags=["characters"],
    )
    def import_characters(
        payload: CharacterCardBundle,
        name_conflict: str = Query(default="rename", pattern="^(rename|skip)$"),
        _: Principal = Depends(require_admin),
    ) -> dict[str, Any]:
        """Create characters from a versioned, portable Kindred card bundle."""

        existing_names = {character["name"].casefold() for character in database.list_characters()}
        created: list[dict[str, Any]] = []
        skipped: list[str] = []
        for card in payload.characters:
            values = {
                field: getattr(card, field)
                for field in _CHARACTER_FIELD_NAMES
            }
            original_name = str(values["name"]).strip()
            candidate = original_name
            if candidate.casefold() in existing_names:
                if name_conflict == "skip":
                    skipped.append(original_name)
                    continue
                base = f"{original_name} (import)"
                candidate = base
                index = 2
                while candidate.casefold() in existing_names:
                    candidate = f"{base} {index}"
                    index += 1
            values["name"] = candidate
            imported = database.create_character(values)
            existing_names.add(imported["name"].casefold())
            created.append(imported)
        return {"created": created, "skipped": skipped}

    @app.get("/api/characters/{character_id}/export", tags=["characters"])
    def export_character(
        character_id: int,
        access_token: str = "",
        authorization: str | None = Header(default=None),
    ) -> JSONResponse:
        """Download one character profile as a portable Kindred card bundle."""

        principal = _principal_from_download_token(access_token, authorization)
        if not principal.is_admin:
            raise HTTPException(403, "Administrator access required")
        character = database.get_character(character_id)
        if not character:
            raise HTTPException(404, "Character not found")
        bundle = _bundle_for_characters([character])
        filename = f"kindred-character-{_safe_filename(character['name'])}.json"
        return JSONResponse(
            jsonable_encoder(bundle),
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    @app.get("/api/characters/{character_id}", response_model=Character, tags=["characters"])
    def get_character(
        character_id: int,
        principal: Principal = Depends(authenticate_request),
    ) -> dict[str, Any]:
        _require_character_access(character_id, principal)
        character = database.get_character(character_id)
        if not character:
            raise HTTPException(404, "Character not found")
        return character

    @app.patch("/api/characters/{character_id}", response_model=Character, tags=["characters"])
    def update_character(
        character_id: int,
        payload: CharacterUpdate,
        _: Principal = Depends(require_admin),
    ) -> dict[str, Any]:
        character = database.update_character(character_id, payload.model_dump(exclude_none=True))
        if not character:
            raise HTTPException(404, "Character not found")
        return character

    @app.delete("/api/characters/{character_id}", status_code=204, tags=["characters"])
    def delete_character(character_id: int, _: Principal = Depends(require_admin)) -> Response:
        if not database.delete_character(character_id):
            raise HTTPException(404, "Character not found")
        return Response(status_code=204)

    @app.get(
        "/api/characters/{character_id}/lore-packs",
        response_model=LorePackAssignment,
        tags=["lore"],
    )
    def get_character_lore_packs(
        character_id: int,
        _: Principal = Depends(require_admin),
    ) -> dict[str, list[int]]:
        """Return lore/fact packs currently attached to one character."""

        if not database.get_character(character_id):
            raise HTTPException(404, "Character not found")
        return {"pack_ids": database.list_character_lore_pack_ids(character_id)}

    @app.put(
        "/api/characters/{character_id}/lore-packs",
        response_model=LorePackAssignment,
        tags=["lore"],
    )
    def update_character_lore_packs(
        character_id: int,
        payload: LorePackAssignment,
        _: Principal = Depends(require_admin),
    ) -> dict[str, list[int]]:
        """Replace the fact-pack assignments used for character retrieval."""

        try:
            pack_ids = database.replace_character_lore_packs(character_id, payload.pack_ids)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        if pack_ids is None:
            raise HTTPException(404, "Character not found")
        return {"pack_ids": pack_ids}

    @app.get("/api/lore-packs", response_model=list[LorePack], tags=["lore"])
    def list_lore_packs(_: Principal = Depends(require_admin)) -> list[dict[str, Any]]:
        """List imported lore/fact packs for admin management."""

        return database.list_lore_packs()

    @app.post("/api/lore-packs/import", response_model=LorePack, status_code=201, tags=["lore"])
    def import_lore_pack(
        payload: LorePackFile,
        _: Principal = Depends(require_admin),
    ) -> dict[str, Any]:
        """Import a versioned lore/fact-pack file for later character assignment."""

        values = payload.model_dump(by_alias=False, exclude={"facts", "schema_", "exported_at"})
        facts = [fact.model_dump() for fact in payload.facts]
        return database.create_lore_pack(values, facts)

    @app.get("/api/lore-packs/{pack_id}", response_model=LorePack, tags=["lore"])
    def get_lore_pack(pack_id: int, _: Principal = Depends(require_admin)) -> dict[str, Any]:
        """Fetch one lore/fact pack with its facts."""

        pack = database.get_lore_pack(pack_id)
        if not pack:
            raise HTTPException(404, "Lore pack not found")
        return pack

    @app.get("/api/lore-packs/{pack_id}/export", tags=["lore"])
    def export_lore_pack(
        pack_id: int,
        access_token: str = "",
        authorization: str | None = Header(default=None),
    ) -> JSONResponse:
        """Download one lore/fact pack as a portable Kindred import file."""

        principal = _principal_from_download_token(access_token, authorization)
        if not principal.is_admin:
            raise HTTPException(403, "Administrator access required")
        pack = database.get_lore_pack(pack_id)
        if not pack:
            raise HTTPException(404, "Lore pack not found")
        filename = f"kindred-fact-pack-{_safe_filename(pack['name'])}.json"
        return JSONResponse(
            jsonable_encoder(_file_for_lore_pack(pack)),
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    @app.delete("/api/lore-packs/{pack_id}", status_code=204, tags=["lore"])
    def delete_lore_pack(pack_id: int, _: Principal = Depends(require_admin)) -> Response:
        """Delete a lore/fact pack and remove it from every character."""

        if not database.delete_lore_pack(pack_id):
            raise HTTPException(404, "Lore pack not found")
        return Response(status_code=204)

    @app.post(
        "/api/characters/{character_id}/duplicate",
        response_model=Character,
        status_code=201,
        tags=["characters"],
    )
    def duplicate_character(character_id: int, _: Principal = Depends(require_admin)) -> dict[str, Any]:
        character = database.duplicate_character(character_id)
        if not character:
            raise HTTPException(404, "Character not found")
        return character

    @app.post("/api/characters/{character_id}/avatar", tags=["characters"])
    async def upload_avatar(
        character_id: int,
        file: UploadFile = File(...),
        _: Principal = Depends(require_admin),
    ) -> dict[str, str]:
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
    def list_threads(
        character_id: int | None = None,
        scope: Literal["mine", "all"] = "mine",
        principal: Principal = Depends(authenticate_request),
    ) -> list[dict[str, Any]]:
        """List current-account threads by default; admins may request all."""

        if character_id is not None:
            _require_character_access(character_id, principal)
        if scope == "all" and not principal.is_admin:
            raise HTTPException(403, "Administrator access required for all threads")
        return database.list_threads(
            character_id,
            user_id=principal.user_id,
            include_all=principal.is_admin and scope == "all",
        )

    @app.post("/api/threads", status_code=201, tags=["chat"])
    def create_thread(
        payload: ThreadCreate,
        principal: Principal = Depends(authenticate_request),
    ) -> dict[str, Any]:
        if not database.get_character(payload.character_id):
            raise HTTPException(404, "Character not found")
        _require_character_access(payload.character_id, principal)
        return database.create_thread(payload.character_id, payload.title, user_id=principal.user_id)

    @app.get("/api/threads/{thread_id}/messages", response_model=list[Message], tags=["chat"])
    def list_messages(
        thread_id: int,
        limit: int = Query(default=200, ge=1, le=1000),
        principal: Principal = Depends(authenticate_request),
    ):
        _require_thread_access(thread_id, principal)
        return database.list_messages(thread_id, limit)

    @app.post("/api/threads/{thread_id}/messages", response_model=Message, tags=["chat"])
    async def send_message(
        thread_id: int,
        payload: ChatRequest,
        principal: Principal = Depends(authenticate_request),
    ) -> dict[str, Any]:
        """Log the user message, generate one character reply, and notify clients."""

        thread = _require_thread_access(thread_id, principal)
        character = database.get_character(thread["character_id"])
        if not character:
            raise HTTPException(404, "Character not found")
        database.add_message(
            thread_id,
            character["id"],
            "user",
            payload.content,
            prompt_context_summary="User-authored message.",
            user_id=thread.get("user_id"),
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
            user_id=thread.get("user_id"),
        )
        await notifications.publish(
            {
                "type": "character_message",
                "message": message,
                "user_id": thread.get("user_id"),
                "thread_id": thread_id,
                "character_id": character["id"],
                "character_name": character["name"],
                "content": generated.content,
            }
        )
        return message

    @app.get("/api/messages/recent", tags=["chat"])
    def recent_messages(
        limit: int = Query(default=50, ge=1, le=500),
        principal: Principal = Depends(authenticate_request),
    ) -> list[dict[str, Any]]:
        return database.search_logs(
            limit=limit,
            user_id=principal.user_id,
            include_all=_include_all(principal),
        )

    @app.get("/api/logs", tags=["logs"])
    def search_logs(
        character_id: int | None = None,
        keyword: str = "",
        date_from: str = "",
        date_to: str = "",
        limit: int = Query(default=500, ge=1, le=5000),
        principal: Principal = Depends(authenticate_request),
    ) -> list[dict[str, Any]]:
        if character_id is not None:
            _require_character_access(character_id, principal)
        return database.search_logs(
            character_id=character_id,
            user_id=principal.user_id,
            include_all=_include_all(principal),
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
        access_token: str = "",
        authorization: str | None = Header(default=None),
    ) -> Response:
        principal = _principal_from_download_token(access_token, authorization)
        if character_id is not None:
            _require_character_access(character_id, principal)
        records = list(
            reversed(
                database.search_logs(
                    character_id=character_id,
                    user_id=principal.user_id,
                    include_all=_include_all(principal),
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
    def get_settings(_: Principal = Depends(require_admin)) -> dict[str, Any]:
        return database.get_settings()

    @app.patch("/api/settings", tags=["settings"])
    def update_settings(payload: SettingsUpdate, _: Principal = Depends(require_admin)) -> dict[str, Any]:
        current = database.get_settings().get(payload.section)
        if isinstance(current, dict) and isinstance(payload.value, dict):
            value = {**current, **payload.value}
        else:
            value = payload.value
        database.set_setting(payload.section, value)
        return database.get_settings()

    @app.get("/api/usage", tags=["settings"])
    def usage(_: Principal = Depends(require_admin)) -> dict[str, object]:
        return RateLimiter(database).summary()

    @app.get("/api/system/backup", tags=["system"])
    def backup_system(
        access_token: str = "",
        authorization: str | None = Header(default=None),
    ) -> FileResponse:
        """Download a whole-system backup zip with SQLite and uploads."""

        principal = _principal_from_download_token(access_token, authorization)
        if not principal.is_admin:
            raise HTTPException(403, "Administrator access required")
        created_at = datetime.now(UTC)
        temp_dir = Path(tempfile.mkdtemp(prefix="kindred-backup-"))
        snapshot = temp_dir / "kindred.db"
        archive_path = temp_dir / "kindred-backup.zip"
        database.backup_to(snapshot)
        with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.write(snapshot, "database/kindred.db")
            upload_count = _add_uploads_to_backup(archive, uploads)
            archive.writestr(
                "manifest.json",
                json.dumps(
                    {
                        "schema": BACKUP_SCHEMA,
                        "created_at": created_at.isoformat(),
                        "api_version": _package_version(),
                        "frontend_version": _frontend_version(),
                        "build": settings.build_number,
                        "database_schema_version": database.schema_version(),
                        "repository_url": REPOSITORY_URL,
                        "database": "database/kindred.db",
                        "uploads_count": upload_count,
                    },
                    indent=2,
                ),
            )
        timestamp = created_at.strftime("%Y%m%d-%H%M%S")
        return FileResponse(
            archive_path,
            media_type="application/zip",
            filename=f"kindred-backup-{timestamp}.zip",
            background=BackgroundTask(lambda: shutil.rmtree(temp_dir, ignore_errors=True)),
        )

    @app.post("/api/system/restore", tags=["system"])
    async def restore_system(
        file: UploadFile = File(...),
        _: Principal = Depends(require_admin),
    ) -> dict[str, Any]:
        """Restore a whole-system backup zip produced by Kindred."""

        temp_dir = Path(tempfile.mkdtemp(prefix="kindred-restore-"))
        stopped_daemon = False
        try:
            archive_path = temp_dir / "restore.zip"
            with archive_path.open("wb") as handle:
                shutil.copyfileobj(file.file, handle)
            extract_dir = temp_dir / "extract"
            with zipfile.ZipFile(archive_path) as archive:
                _safe_zip_members(archive)
                try:
                    manifest = json.loads(archive.read("manifest.json"))
                except (KeyError, json.JSONDecodeError) as exc:
                    raise HTTPException(400, "Backup manifest is missing or invalid") from exc
                if manifest.get("schema") != BACKUP_SCHEMA:
                    raise HTTPException(400, "Backup schema is not supported")
                if "database/kindred.db" not in archive.namelist():
                    raise HTTPException(400, "Backup is missing database/kindred.db")
                archive.extractall(extract_dir)
            await daemon.stop()
            stopped_daemon = True
            try:
                database.restore_from(extract_dir / "database/kindred.db", defaults)
            except RuntimeError as exc:
                raise HTTPException(400, str(exc)) from exc
            restored_uploads = extract_dir / "uploads"
            if uploads.exists():
                shutil.rmtree(uploads)
            if restored_uploads.exists():
                shutil.copytree(restored_uploads, uploads)
            else:
                uploads.mkdir(parents=True, exist_ok=True)
            daemon.start()
            stopped_daemon = False
            return {"status": "restored", "manifest": manifest}
        finally:
            if stopped_daemon:
                daemon.start()
            shutil.rmtree(temp_dir, ignore_errors=True)

    @app.post("/api/system/reset", tags=["system"])
    async def reset_system(
        payload: SystemResetRequest,
        _: Principal = Depends(require_admin),
    ) -> dict[str, Any]:
        """Reset Kindred to the committed defaults and seed characters."""

        stopped_daemon = False
        try:
            await daemon.stop()
            stopped_daemon = True
            seeded = database.reset_to_defaults(
                defaults,
                _load_json(PROJECT_ROOT / "data/seed/characters.json"),
            )
            if uploads.exists():
                shutil.rmtree(uploads)
            uploads.mkdir(parents=True, exist_ok=True)
            daemon.start()
            stopped_daemon = False
            return {"status": "reset", "seeded_characters": seeded, "confirmed": payload.confirm}
        finally:
            if stopped_daemon:
                daemon.start()

    @app.post("/api/images/generate", tags=["settings"])
    def generate_image(
        payload: ImageGenerationRequest,
        principal: Principal = Depends(authenticate_request),
    ) -> dict[str, Any]:
        """Meter a provider-neutral image task; live image adapters follow post-MVP."""

        if payload.character_id is not None:
            _require_character_access(payload.character_id, principal)
        limiter = RateLimiter(database)
        dry_run = payload.dry_run or settings.cloud_dry_run
        limiter.reserve_cloud(
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
    def notification_public_key(_: Principal = Depends(authenticate_request)) -> dict[str, Any]:
        return {
            "public_key": settings.vapid_public_key,
            "web_push_configured": bool(settings.vapid_private_key and settings.vapid_public_key),
        }

    @app.post("/api/notifications/subscribe", status_code=201, tags=["notifications"])
    async def subscribe(
        request: Request,
        principal: Principal = Depends(authenticate_request),
    ) -> dict[str, str]:
        subscription = await request.json()
        try:
            database.save_subscription(subscription, user_id=principal.user_id)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        return {"status": "subscribed"}

    @app.delete("/api/notifications/subscribe", status_code=204, tags=["notifications"])
    async def unsubscribe(
        request: Request,
        _: Principal = Depends(authenticate_request),
    ) -> Response:
        body = await request.json()
        database.delete_subscription(body.get("endpoint", ""))
        return Response(status_code=204)

    @app.post(
        "/api/notifications/test",
        response_model=NotificationTestResult,
        tags=["notifications"],
    )
    async def test_notification(
        payload: NotificationTestRequest,
        principal: Principal = Depends(authenticate_request),
    ) -> dict[str, Any]:
        """Publish a logged character-message event to the signed-in account.

        This intentionally exercises the same WebSocket and Web Push fan-out as
        real character messages, but it does not call the LLM. Use
        `/api/daemon/run-once` when testing the full autonomous generation path.
        """

        character = database.get_character(payload.character_id)
        if not character:
            raise HTTPException(404, "Character not found")
        _require_character_access(payload.character_id, principal)
        thread = database.get_or_create_thread(character["id"], user_id=principal.user_id)
        content = (
            payload.content.strip()
            if payload.content and payload.content.strip()
            else f"Kindred notification test from {character['name']}."
        )
        message = database.add_message(
            thread["id"],
            character["id"],
            "character",
            content,
            backend="kindred",
            model="notification-test",
            prompt_context_summary="Manual notification delivery test; no model prompt was sent.",
            character_rationale=(
                "This message was created by the notification test endpoint to verify delivery."
            ),
            initiated=True,
            user_id=principal.user_id,
        )
        await notifications.publish(
            {
                "type": "character_message",
                "message": message,
                "user_id": principal.user_id,
                "thread_id": thread["id"],
                "character_id": character["id"],
                "character_name": character["name"],
                "content": content,
            }
        )
        return {
            "status": "sent",
            "web_push_configured": bool(settings.vapid_private_key and settings.vapid_public_key),
            "subscription_count": len(database.list_subscriptions(principal.user_id)),
            "thread_id": thread["id"],
            "message": message,
        }

    @app.websocket("/api/events/ws")
    async def event_socket(socket: WebSocket, token: str | None = None) -> None:
        try:
            principal = websocket_token_from_header_or_query(
                socket.headers.get("authorization"),
                token,
                settings,
            )
            if not principal.is_admin:
                user = database.get_user(principal.user_id)
                if not user or user["disabled"]:
                    await socket.close(code=1008)
                    return
        except HTTPException:
            await socket.close(code=1008)
            return
        await notifications.connect(socket, principal)
        try:
            while True:
                await socket.receive_text()
        except WebSocketDisconnect:
            notifications.disconnect(socket)

    @app.post("/api/daemon/run-once", tags=["daemon"])
    async def run_daemon_once(
        character_id: int | None = None,
        _: Principal = Depends(require_admin),
    ) -> list[dict[str, Any]]:
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
