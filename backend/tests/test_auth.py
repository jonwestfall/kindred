"""Authentication and multi-user access control coverage."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from kindred.config import Settings
from kindred.main import create_app


def auth_settings(database_path: Path) -> Settings:
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
        auth_enabled=True,
        admin_username="root",
        admin_password="correct-horse-battery-staple",
        session_secret="auth-test-session-secret",
        session_hours=24,
    )


def login(client: TestClient, username: str, password: str) -> dict[str, str]:
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['token']}"}


def test_admin_can_create_user_and_user_only_sees_granted_character(tmp_path: Path):
    app = create_app(auth_settings(tmp_path / "auth-test.db"))
    with TestClient(app) as client:
        assert client.get("/api/characters").status_code == 401
        admin_headers = login(client, "root", "correct-horse-battery-staple")
        characters = client.get("/api/characters", headers=admin_headers).json()
        granted = characters[0]

        created = client.post(
            "/api/users",
            headers=admin_headers,
            json={
                "username": "reader",
                "display_name": "Reader",
                "password": "local-password",
                "character_ids": [granted["id"]],
            },
        )
        assert created.status_code == 201
        assert created.json()["character_ids"] == [granted["id"]]

        user_headers = login(client, "reader", "local-password")
        visible = client.get("/api/characters", headers=user_headers)
        assert visible.status_code == 200
        assert [character["id"] for character in visible.json()] == [granted["id"]]

        ungranted = next(character for character in characters if character["id"] != granted["id"])
        denied = client.post(
            "/api/threads",
            headers=user_headers,
            json={"character_id": ungranted["id"], "title": "Nope"},
        )
        assert denied.status_code == 403


def test_disabled_user_cannot_keep_using_existing_token(tmp_path: Path):
    app = create_app(auth_settings(tmp_path / "disabled-test.db"))
    with TestClient(app) as client:
        admin_headers = login(client, "root", "correct-horse-battery-staple")
        character = client.get("/api/characters", headers=admin_headers).json()[0]
        user = client.post(
            "/api/users",
            headers=admin_headers,
            json={
                "username": "sleepy",
                "password": "local-password",
                "character_ids": [character["id"]],
            },
        ).json()
        user_headers = login(client, "sleepy", "local-password")
        assert client.get("/api/characters", headers=user_headers).status_code == 200

        disabled = client.patch(
            f"/api/users/{user['id']}",
            headers=admin_headers,
            json={"disabled": True},
        )
        assert disabled.status_code == 200
        assert client.get("/api/characters", headers=user_headers).status_code == 403
