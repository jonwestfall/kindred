"""System metadata, backup, restore, and reset coverage."""

import sqlite3
import zipfile
from io import BytesIO
from pathlib import Path


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
    assert health["database_schema_version"] == 1


def test_backup_and_restore_round_trip(client):
    created = client.post("/api/characters", json=CHARACTER_PAYLOAD)
    assert created.status_code == 201

    backup = client.get("/api/system/backup")
    assert backup.status_code == 200
    with zipfile.ZipFile(BytesIO(backup.content)) as archive:
        assert "manifest.json" in archive.namelist()
        assert "database/kindred.db" in archive.namelist()
        manifest = archive.read("manifest.json")
    assert b'"database_schema_version": 1' in manifest

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


def test_restore_rejects_future_schema_without_replacing_current_database(client, tmp_path: Path):
    payload = {**CHARACTER_PAYLOAD, "name": "Future Restore Guard"}
    assert client.post("/api/characters", json=payload).status_code == 201
    backup = client.get("/api/system/backup")
    assert backup.status_code == 200

    extract_dir = tmp_path / "future-backup"
    extract_dir.mkdir()
    with zipfile.ZipFile(BytesIO(backup.content)) as archive:
        archive.extractall(extract_dir)
    database_path = extract_dir / "database/kindred.db"
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """INSERT OR REPLACE INTO schema_migrations(version, description, applied_at)
               VALUES (999, 'Future schema', '2099-01-01T00:00:00+00:00')"""
        )
    future_backup = BytesIO()
    with zipfile.ZipFile(future_backup, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in extract_dir.rglob("*"):
            if path.is_file():
                archive.write(path, path.relative_to(extract_dir).as_posix())

    restored = client.post(
        "/api/system/restore",
        files={"file": ("future-kindred-backup.zip", future_backup.getvalue(), "application/zip")},
    )

    assert restored.status_code == 400
    assert "newer than this Kindred build" in restored.json()["detail"]
    names_after_failed_restore = {character["name"] for character in client.get("/api/characters").json()}
    assert "Future Restore Guard" in names_after_failed_restore


def test_reset_returns_to_seed_state(client):
    assert client.post("/api/characters", json=CHARACTER_PAYLOAD).status_code == 201

    bad_reset = client.post("/api/system/reset", json={"confirm": "nope"})
    assert bad_reset.status_code == 422

    reset = client.post("/api/system/reset", json={"confirm": "RESET"})
    assert reset.status_code == 200
    assert reset.json()["status"] == "reset"

    names = {character["name"] for character in client.get("/api/characters").json()}
    assert names == {"Mara Vey", "The Archivist"}
