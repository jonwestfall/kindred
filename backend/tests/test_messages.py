"""Conversation persistence and export metadata coverage."""

from kindred.schemas import CharacterCreate


def test_message_logging_includes_audit_fields(database):
    character = database.create_character(
        CharacterCreate(name="Mira", model="tiny-model").model_dump()
    )
    thread = database.create_thread(character["id"], "First light")
    database.add_message(
        thread["id"],
        character["id"],
        "user",
        "Are you there?",
        prompt_context_summary="User-authored message.",
    )
    reply = database.add_message(
        thread["id"],
        character["id"],
        "character",
        "By the window.",
        backend="ollama",
        model="tiny-model",
        prompt_context_summary="Character profile + 1 recent message.",
        character_rationale="Reply based on profile and recent conversation.",
    )

    messages = database.list_messages(thread["id"])
    assert [message["sender"] for message in messages] == ["user", "character"]
    assert reply["backend"] == "ollama"
    assert reply["character_rationale"].startswith("Reply based")

    logs = database.search_logs(character_id=character["id"], keyword="window")
    assert len(logs) == 1
    assert logs[0]["thread_title"] == "First light"


def test_thread_rename_and_delete_routes(client):
    character = client.post(
        "/api/characters",
        json={"name": "Mira Threads", "model": "tiny-model"},
    ).json()
    thread = client.post(
        "/api/threads",
        json={"character_id": character["id"], "title": "First light"},
    ).json()

    updated = client.patch(
        f"/api/threads/{thread['id']}",
        json={"title": "Moonlit platform"},
    )
    assert updated.status_code == 200
    assert updated.json()["title"] == "Moonlit platform"

    threads = client.get("/api/threads").json()
    assert threads[0]["title"] == "Moonlit platform"

    deleted = client.delete(f"/api/threads/{thread['id']}")
    assert deleted.status_code == 204
    assert client.get(f"/api/threads/{thread['id']}/messages").status_code == 404
