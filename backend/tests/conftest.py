"""Shared isolated database and application fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from kindred.config import Settings
from kindred.database import Database
from kindred.main import create_app


def test_settings(database_path: Path) -> Settings:
    return Settings(
        environment="test",
        host="127.0.0.1",
        port=8000,
        database_path=database_path,
        cors_origins=("http://testserver",),
        daemon_enabled=False,
        daemon_interval_seconds=60,
        timezone="UTC",
        ollama_base_url="http://127.0.0.1:9",
        ollama_model="test-model",
        llamacpp_base_url="http://127.0.0.1:9",
        cloud_base_url="http://127.0.0.1:9/v1",
        cloud_api_key="",
        cloud_model="test-cloud-model",
        cloud_dry_run=True,
        vapid_private_key="",
        vapid_public_key="",
        vapid_subject="mailto:test@example.com",
        auth_enabled=False,
        admin_username="admin",
        admin_password="test-password",
        session_secret="test-session-secret",
        session_hours=24,
    )


@pytest.fixture
def database(tmp_path: Path) -> Database:
    db = Database(tmp_path / "kindred-test.db")
    db.initialize(
        {
            "daemon": {
                "enabled": True,
                "quiet_hours_start": "22:00",
                "quiet_hours_end": "08:00",
                "global_messages_per_hour": 4,
                "global_messages_per_day": 12,
            },
            "limits": {
                "requests_per_hour": 2,
                "requests_per_day": 3,
                "tokens_per_day": 100,
                "cloud_spend_ceiling_usd": 1.0,
                "image_generations_per_day": 1,
            },
            "notifications": {"enabled": True},
            "world_notes": "",
        }
    )
    return db


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    app = create_app(test_settings(tmp_path / "api-test.db"))
    with TestClient(app) as test_client:
        yield test_client
