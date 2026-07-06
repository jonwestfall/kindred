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

