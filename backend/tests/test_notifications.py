"""Notification delivery-test endpoint coverage."""

import json
import sys
from dataclasses import replace
from types import ModuleType

from kindred.notifications import NotificationService
from kindred.schemas import CharacterCreate


def test_notification_test_endpoint_logs_and_counts_subscription(client):
    database = client.app.state.database
    character = database.create_character(
        CharacterCreate(name="Signal", model="tiny-model").model_dump()
    )
    database.save_subscription(
        {
            "endpoint": "https://push.example.test/kindred-test",
            "keys": {"p256dh": "test-public-key", "auth": "test-auth-secret"},
        },
        user_id=None,
    )

    response = client.post(
        "/api/notifications/test",
        json={"character_id": character["id"], "content": "Delivery probe."},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "sent"
    assert body["subscription_count"] == 1
    assert body["message"]["content"] == "Delivery probe."
    assert body["message"]["initiated"] is True
    assert body["message"]["backend"] == "kindred"

    messages = database.list_messages(body["thread_id"])
    assert messages[-1]["content"] == "Delivery probe."
    assert messages[-1]["prompt_context_summary"].startswith("Manual notification")


def test_web_push_payload_identifies_message_and_target_thread(client, monkeypatch):
    database = client.app.state.database
    database.save_subscription(
        {
            "endpoint": "https://push.example.test/kindred-message",
            "keys": {"p256dh": "test-public-key", "auth": "test-auth-secret"},
        },
        user_id=None,
    )
    calls: list[dict] = []
    fake_pywebpush = ModuleType("pywebpush")

    class FakeWebPushException(Exception):
        pass

    def fake_webpush(**kwargs):
        calls.append(
            {
                "subscription_info": kwargs["subscription_info"],
                "payload": json.loads(kwargs["data"]),
                "vapid_claims": kwargs["vapid_claims"],
            }
        )

    fake_pywebpush.WebPushException = FakeWebPushException
    fake_pywebpush.webpush = fake_webpush
    monkeypatch.setitem(sys.modules, "pywebpush", fake_pywebpush)
    service = NotificationService(
        replace(
            client.app.state.settings,
            vapid_private_key="test-private-key",
            vapid_public_key="test-public-key",
        ),
        database,
    )

    service._send_web_push(
        {
            "type": "character_message",
            "message": {"id": 42},
            "thread_id": 7,
            "character_name": "Signal",
            "content": "Thread-targeted push.",
            "user_id": None,
        }
    )

    assert len(calls) == 1
    payload = calls[0]["payload"]
    assert payload["url"] == "/?thread=7"
    assert payload["thread_id"] == 7
    assert payload["message_id"] == 42
    assert payload["tag"] == "kindred-message-42"
    deliveries = database.list_notification_deliveries()
    assert deliveries[0]["status"] == "sent"
    assert deliveries[0]["endpoint_host"] == "push.example.test"
    assert deliveries[0]["endpoint_preview"]


def test_notification_diagnostics_lists_and_deletes_subscriptions(client):
    database = client.app.state.database
    database.save_subscription(
        {
            "endpoint": "https://push.example.test/kindred-diagnostics",
            "keys": {"p256dh": "test-public-key", "auth": "test-auth-secret"},
        },
        user_id=None,
    )
    database.log_notification_delivery(
        channel="web_push",
        status="skipped",
        detail="No saved push subscriptions matched this message.",
        user_id=None,
        thread_id=12,
        message_id=34,
        character_id=56,
    )

    response = client.get("/api/notifications/diagnostics?scope=all")

    assert response.status_code == 200
    body = response.json()
    assert body["scope"] == "all"
    assert body["subscription_count"] == 1
    subscription = body["subscriptions"][0]
    assert subscription["endpoint_host"] == "push.example.test"
    assert "keys" not in subscription
    assert "subscription" not in subscription
    assert body["recent_deliveries"][0]["status"] == "skipped"
    assert body["recent_deliveries"][0]["message_id"] == 34

    deleted = client.delete(f"/api/notifications/subscriptions/{subscription['id']}")
    assert deleted.status_code == 204
    assert client.get("/api/notifications/diagnostics?scope=all").json()["subscription_count"] == 0


def test_expired_web_push_subscription_is_removed_and_logged(client, monkeypatch):
    database = client.app.state.database
    database.save_subscription(
        {
            "endpoint": "https://push.example.test/expired",
            "keys": {"p256dh": "test-public-key", "auth": "test-auth-secret"},
        },
        user_id=None,
    )
    fake_pywebpush = ModuleType("pywebpush")

    class FakeResponse:
        status_code = 410

    class FakeWebPushException(Exception):
        response = FakeResponse()

    def fake_webpush(**kwargs):
        raise FakeWebPushException("gone")

    fake_pywebpush.WebPushException = FakeWebPushException
    fake_pywebpush.webpush = fake_webpush
    monkeypatch.setitem(sys.modules, "pywebpush", fake_pywebpush)
    service = NotificationService(
        replace(
            client.app.state.settings,
            vapid_private_key="test-private-key",
            vapid_public_key="test-public-key",
        ),
        database,
    )

    service._send_web_push(
        {
            "type": "character_message",
            "message": {"id": 99},
            "thread_id": 11,
            "character_name": "Signal",
            "content": "Expired push.",
            "user_id": None,
        }
    )

    assert database.list_subscription_records() == []
    deliveries = database.list_notification_deliveries()
    assert deliveries[0]["status"] == "expired"
    assert "removed" in deliveries[0]["detail"]
