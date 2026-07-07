"""Character CRUD API coverage."""


def test_create_duplicate_and_delete_character(client):
    payload = {
        "name": "Ada of the Lantern",
        "description": "A practical cartographer.",
        "personality": "Patient and exact.",
        "speaking_style": "Brief, concrete messages.",
        "backstory": "She maps roads that appear only at dusk.",
        "goals": "Help the user find a next step.",
        "boundaries": "Label guesses.",
        "backend": "ollama",
        "model": "llama3.2:1b",
        "temperature": 0.6,
        "initiative_frequency": 1,
        "cooldown_minutes": 180,
    }
    response = client.post("/api/characters", json=payload)
    assert response.status_code == 201
    created = response.json()
    assert created["name"] == payload["name"]
    assert created["backend"] == "ollama"

    duplicated = client.post(f"/api/characters/{created['id']}/duplicate")
    assert duplicated.status_code == 201
    assert duplicated.json()["name"] == "Ada of the Lantern (copy)"

    deleted = client.delete(f"/api/characters/{created['id']}")
    assert deleted.status_code == 204
    assert client.get(f"/api/characters/{created['id']}").status_code == 404


def test_export_and_import_character_card_bundle(client):
    payload = {
        "name": "Ada of the Lantern",
        "description": "A practical cartographer.",
        "personality": "Patient and exact.",
        "speaking_style": "Brief, concrete messages.",
        "backstory": "She maps roads that appear only at dusk.",
        "goals": "Help the user find a next step.",
        "boundaries": "Label guesses.",
        "backend": "ollama",
        "model": "llama3.2:1b",
        "temperature": 0.6,
        "initiative_frequency": 1,
        "cooldown_minutes": 180,
    }
    created = client.post("/api/characters", json=payload).json()

    exported = client.get(f"/api/characters/{created['id']}/export")
    assert exported.status_code == 200
    card = exported.json()
    assert card["schema"] == "kindred.character_card.v1"
    assert card["characters"][0]["name"] == "Ada of the Lantern"
    assert exported.headers["content-disposition"].endswith(
        'filename="kindred-character-ada-of-the-lantern.json"'
    )

    imported = client.post("/api/characters/import", json=card)
    assert imported.status_code == 201
    result = imported.json()
    assert result["created"][0]["name"] == "Ada of the Lantern (import)"
    assert result["skipped"] == []

    skipped = client.post("/api/characters/import?name_conflict=skip", json=card)
    assert skipped.status_code == 201
    assert skipped.json()["created"] == []
    assert skipped.json()["skipped"] == ["Ada of the Lantern"]


def test_import_llm_authored_character_card(client):
    card = {
        "schema": "kindred.character_card.v1",
        "characters": [
            {
                "name": "Marian Example",
                "description": "A public-domain-style test character.",
                "personality": "Warm, observant, and principled.",
                "speaking_style": "Short epistolary notes with gentle wit.",
                "backstory": "Adapted from user-provided notes, not quoted text.",
                "goals": "Help the user reason through social dilemmas.",
                "boundaries": "Do not claim to be a real person.",
                "backend": "ollama",
                "model": "llama3.2:1b",
                "temperature": 0.7,
                "initiative_frequency": 0.5,
                "cooldown_minutes": 360,
                "source_title": "Example Book",
                "source_author": "Example Author",
                "tags": ["fictional", "public-domain-style"],
            }
        ],
    }

    imported = client.post("/api/characters/import", json=card)
    assert imported.status_code == 201
    created = imported.json()["created"][0]
    assert created["name"] == "Marian Example"
    assert created["backend"] == "ollama"
