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
