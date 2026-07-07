"""Notification delivery-test endpoint coverage."""

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
