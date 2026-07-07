"""System metadata, backup, restore, and reset coverage."""

import zipfile
from io import BytesIO


CHARACTER_PAYLOAD = {
    "name": "Backup Marker",
    "description": "A character that should survive backup restore.",
    "personality": "Careful.",
    "speaking_style": "Brief.",
    "backstory": "",
    "goals": "",
    "boundaries": "",
    "backend": "ollama",
    "model": "llama3.2:1b",
    "temperature": 0.7,
    "initiative_frequency": 1,
    "cooldown_minutes": 240,
}


def test_health_reports_versions_builds_and_repository(client):
    response = client.get("/api/health")

    assert response.status_code == 200
    health = response.json()
    assert health["repository_url"] == "https://github.com/jonwestfall/kindred"
    assert health["api"]["version"]
    assert health["api"]["build"] == "test-build"
    assert health["frontend"]["build"] == "test-frontend-build"
    assert health["runtime"]["python"]


def test_backup_and_restore_round_trip(client):
    created = client.post("/api/characters", json=CHARACTER_PAYLOAD)
    assert created.status_code == 201

    backup = client.get("/api/system/backup")
    assert backup.status_code == 200
    with zipfile.ZipFile(BytesIO(backup.content)) as archive:
        assert "manifest.json" in archive.namelist()
        assert "database/kindred.db" in archive.namelist()

    post_backup_payload = {**CHARACTER_PAYLOAD, "name": "Post Backup Marker"}
    assert client.post("/api/characters", json=post_backup_payload).status_code == 201
    names_before_restore = {character["name"] for character in client.get("/api/characters").json()}
    assert "Post Backup Marker" in names_before_restore

    restored = client.post(
        "/api/system/restore",
        files={"file": ("kindred-backup.zip", backup.content, "application/zip")},
    )
    assert restored.status_code == 200
    assert restored.json()["status"] == "restored"
    names_after_restore = {character["name"] for character in client.get("/api/characters").json()}
    assert "Backup Marker" in names_after_restore
    assert "Post Backup Marker" not in names_after_restore


def test_reset_returns_to_seed_state(client):
    assert client.post("/api/characters", json=CHARACTER_PAYLOAD).status_code == 201

    bad_reset = client.post("/api/system/reset", json={"confirm": "nope"})
    assert bad_reset.status_code == 422

    reset = client.post("/api/system/reset", json={"confirm": "RESET"})
    assert reset.status_code == 200
    assert reset.json()["status"] == "reset"

    names = {character["name"] for character in client.get("/api/characters").json()}
    assert names == {"Mara Vey", "The Archivist"}
