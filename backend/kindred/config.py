"""Environment-driven configuration with safe local-first defaults."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True, slots=True)
class Settings:
    """Runtime settings loaded once for each application instance."""

    environment: str
    build_number: str
    frontend_build_number: str
    host: str
    port: int
    database_path: Path
    cors_origins: tuple[str, ...]
    daemon_enabled: bool
    daemon_interval_seconds: int
    timezone: str
    ollama_base_url: str
    ollama_model: str
    embeddings_enabled: bool
    embeddings_provider: str
    embeddings_model: str
    embeddings_dimensions: int
    llamacpp_base_url: str
    cloud_base_url: str
    cloud_api_key: str
    cloud_model: str
    cloud_dry_run: bool
    vapid_private_key: str
    vapid_public_key: str
    vapid_subject: str
    auth_enabled: bool
    admin_username: str
    admin_password: str
    session_secret: str
    session_hours: int

    @classmethod
    def from_env(cls) -> "Settings":
        """Build settings without requiring a heavyweight settings package."""

        database = Path(os.getenv("KINDRED_DATABASE_PATH", str(PROJECT_ROOT / "data/kindred.db")))
        if not database.is_absolute():
            database = (PROJECT_ROOT / database).resolve()
        origins = tuple(
            item.strip()
            for item in os.getenv(
                "KINDRED_CORS_ORIGINS",
                "http://localhost:5173,http://127.0.0.1:5173",
            ).split(",")
            if item.strip()
        )
        return cls(
            environment=os.getenv("KINDRED_ENV", "development"),
            build_number=os.getenv("KINDRED_BUILD", "dev"),
            frontend_build_number=os.getenv(
                "KINDRED_FRONTEND_BUILD",
                os.getenv("KINDRED_BUILD", "dev"),
            ),
            host=os.getenv("KINDRED_HOST", "0.0.0.0"),
            port=int(os.getenv("KINDRED_PORT", "8000")),
            database_path=database,
            cors_origins=origins,
            daemon_enabled=_bool("KINDRED_DAEMON_ENABLED", True),
            daemon_interval_seconds=max(15, int(os.getenv("KINDRED_DAEMON_INTERVAL_SECONDS", "60"))),
            timezone=os.getenv("KINDRED_TIMEZONE", "America/Chicago"),
            ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/"),
            ollama_model=os.getenv("OLLAMA_MODEL", "llama3.2:1b"),
            embeddings_enabled=_bool("KINDRED_EMBEDDINGS_ENABLED", False),
            embeddings_provider=os.getenv("KINDRED_EMBEDDINGS_PROVIDER", "ollama"),
            embeddings_model=os.getenv("KINDRED_EMBEDDINGS_MODEL", "all-minilm"),
            embeddings_dimensions=max(0, int(os.getenv("KINDRED_EMBEDDINGS_DIMENSIONS", "0"))),
            llamacpp_base_url=os.getenv("LLAMACPP_BASE_URL", "http://127.0.0.1:8080").rstrip("/"),
            cloud_base_url=os.getenv("OPENAI_COMPATIBLE_BASE_URL", "https://api.openai.com/v1").rstrip("/"),
            cloud_api_key=os.getenv("OPENAI_API_KEY", ""),
            cloud_model=os.getenv("OPENAI_COMPATIBLE_MODEL", "gpt-4.1-mini"),
            cloud_dry_run=_bool("KINDRED_CLOUD_DRY_RUN", True),
            vapid_private_key=os.getenv("VAPID_PRIVATE_KEY", ""),
            vapid_public_key=os.getenv("VAPID_PUBLIC_KEY", ""),
            vapid_subject=os.getenv("VAPID_SUBJECT", "mailto:admin@example.com"),
            auth_enabled=_bool("KINDRED_AUTH_ENABLED", True),
            admin_username=os.getenv("KINDRED_ADMIN_USERNAME", "admin"),
            admin_password=os.getenv("KINDRED_ADMIN_PASSWORD", "change-me-now"),
            session_secret=os.getenv("KINDRED_SESSION_SECRET", "kindred-dev-session-secret-change-me"),
            session_hours=max(1, int(os.getenv("KINDRED_SESSION_HOURS", "168"))),
        )
