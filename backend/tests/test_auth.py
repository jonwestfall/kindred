"""Authentication and multi-user access control coverage."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from kindred.config import Settings
from kindred.main import create_app


def auth_settings(database_path: Path) -> Settings:
    return Settings(
        environment="test",
        build_number="test-build",
        frontend_build_number="test-frontend-build",
        host="127.0.0.1",
        port=8000,
        database_path=database_path,
        cors_origins=("http://testserver",),
        daemon_enabled=False,
        daemon_interval_seconds=60,
        timezone="UTC",
        ollama_base_url="http://127.0.0.1:9",
        ollama_model="test-model",
        embeddings_enabled=False,
        embeddings_provider="ollama",
        embeddings_model="all-minilm",
        embeddings_dimensions=0,
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


def test_admin_thread_listing_defaults_to_own_scope_and_all_scope_is_explicit(tmp_path: Path):
    app = create_app(auth_settings(tmp_path / "thread-scope-test.db"))
    with TestClient(app) as client:
        admin_headers = login(client, "root", "correct-horse-battery-staple")
        character = client.get("/api/characters", headers=admin_headers).json()[0]
        user = client.post(
            "/api/users",
            headers=admin_headers,
            json={
                "username": "reader",
                "display_name": "Reader",
                "password": "local-password",
                "character_ids": [character["id"]],
            },
        ).json()
        user_headers = login(client, "reader", "local-password")

        user_thread = client.post(
            "/api/threads",
            headers=user_headers,
            json={"character_id": character["id"], "title": "Reader thread"},
        ).json()
        admin_thread = client.post(
            "/api/threads",
            headers=admin_headers,
            json={"character_id": character["id"], "title": "Admin thread"},
        ).json()

        assert user_thread["user_id"] == user["id"]
        assert user_thread["owner_label"] == "Reader"
        assert admin_thread["user_id"] is None
        assert admin_thread["owner_label"] == "Administrator"

        admin_default = client.get("/api/threads", headers=admin_headers).json()
        assert {thread["id"] for thread in admin_default} == {admin_thread["id"]}

        admin_all = client.get("/api/threads?scope=all", headers=admin_headers).json()
        assert {thread["id"] for thread in admin_all} == {
            admin_thread["id"],
            user_thread["id"],
        }
        assert {
            thread["owner_label"] for thread in admin_all
        } == {"Administrator", "Reader"}

        user_default = client.get("/api/threads", headers=user_headers).json()
        assert {thread["id"] for thread in user_default} == {user_thread["id"]}
        assert client.get("/api/threads?scope=all", headers=user_headers).status_code == 403


def test_notification_diagnostics_are_account_scoped(tmp_path: Path):
    app = create_app(auth_settings(tmp_path / "notification-scope-test.db"))
    with TestClient(app) as client:
        admin_headers = login(client, "root", "correct-horse-battery-staple")
        character = client.get("/api/characters", headers=admin_headers).json()[0]
        user = client.post(
            "/api/users",
            headers=admin_headers,
            json={
                "username": "reader",
                "display_name": "Reader",
                "password": "local-password",
                "character_ids": [character["id"]],
            },
        ).json()
        app.state.database.save_subscription(
            {
                "endpoint": "https://push.example.test/admin-device",
                "keys": {"p256dh": "admin-key", "auth": "admin-auth"},
            },
            user_id=None,
        )
        app.state.database.save_subscription(
            {
                "endpoint": "https://push.example.test/reader-device",
                "keys": {"p256dh": "reader-key", "auth": "reader-auth"},
            },
            user_id=user["id"],
        )

        user_headers = login(client, "reader", "local-password")
        user_diagnostics = client.get("/api/notifications/diagnostics", headers=user_headers).json()
        assert user_diagnostics["subscription_count"] == 1
        assert user_diagnostics["subscriptions"][0]["owner_label"] == "Reader"
        assert client.get(
            "/api/notifications/diagnostics?scope=all",
            headers=user_headers,
        ).status_code == 403

        admin_all = client.get(
            "/api/notifications/diagnostics?scope=all",
            headers=admin_headers,
        ).json()
        assert admin_all["subscription_count"] == 2
