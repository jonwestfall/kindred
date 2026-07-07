"""Lore/fact-pack import, assignment, export, and retrieval coverage."""

from dataclasses import replace

import pytest

from kindred.llm import LLMService
from kindred.llm import system_prompt


FACT_PACK = {
    "schema": "kindred.fact_pack.v1",
    "name": "Lantern Roads facts",
    "description": "Grounding facts for Ada of the Lantern.",
    "source_title": "Example Field Notes",
    "source_author": "Kindred Tests",
    "source_reference": "test fixture",
    "facts": [
        {
            "title": "Dusk roads",
            "content": "The lantern roads appear only after sunset and fade at dawn.",
            "keywords": ["lantern", "roads", "dusk"],
            "tags": ["setting"],
            "source_reference": "notes:1",
            "weight": 1.5,
        },
        {
            "title": "Cartographer habit",
            "content": "Ada marks uncertain routes with a blue pin.",
            "keywords": ["Ada", "cartographer", "blue pin"],
            "tags": ["character"],
            "source_reference": "notes:2",
            "weight": 1.0,
        },
    ],
}


def test_import_assign_export_and_search_lore_pack(client):
    character = client.post(
        "/api/characters",
        json={
            "name": "Ada of the Lantern",
            "description": "A practical cartographer.",
            "goals": "Map lantern roads safely.",
            "backend": "ollama",
            "model": "llama3.2:1b",
            "temperature": 0.7,
            "initiative_frequency": 1,
            "cooldown_minutes": 240,
        },
    ).json()

    imported = client.post("/api/lore-packs/import", json=FACT_PACK)
    assert imported.status_code == 201
    pack = imported.json()
    assert pack["name"] == "Lantern Roads facts"
    assert pack["fact_count"] == 2

    assigned = client.put(
        f"/api/characters/{character['id']}/lore-packs",
        json={"pack_ids": [pack["id"]]},
    )
    assert assigned.status_code == 200
    assert assigned.json()["pack_ids"] == [pack["id"]]

    found = client.app.state.database.search_lore(
        character["id"],
        "When do the lantern roads fade?",
        limit=1,
    )
    assert found[0]["title"] == "Dusk roads"
    assert found[0]["pack_name"] == "Lantern Roads facts"

    exported = client.get(f"/api/lore-packs/{pack['id']}/export")
    assert exported.status_code == 200
    payload = exported.json()
    assert payload["schema"] == "kindred.fact_pack.v1"
    assert payload["facts"][0]["content"].startswith("The lantern roads")


def test_system_prompt_includes_retrieved_lore_without_reasoning():
    prompt = system_prompt(
        {
            "name": "Ada",
            "description": "Cartographer.",
            "personality": "",
            "speaking_style": "",
            "backstory": "",
            "goals": "",
            "boundaries": "Do not reveal hidden reasoning.",
        },
        lore_facts=[
            {
                "title": "Dusk roads",
                "content": "The lantern roads fade at dawn.",
                "source_reference": "notes:1",
                "pack_name": "Lantern Roads facts",
            }
        ],
    )

    assert "Relevant lore/facts" in prompt
    assert "The lantern roads fade at dawn." in prompt
    assert "Do not reveal hidden reasoning" in prompt


@pytest.mark.asyncio
async def test_semantic_lore_retrieval_caches_embeddings(client, monkeypatch):
    character = client.post(
        "/api/characters",
        json={
            "name": "Ada Semantic",
            "description": "A practical cartographer.",
            "backend": "ollama",
            "model": "llama3.2:1b",
            "temperature": 0.7,
            "initiative_frequency": 1,
            "cooldown_minutes": 240,
        },
    ).json()
    pack = client.post("/api/lore-packs/import", json=FACT_PACK).json()
    client.put(f"/api/characters/{character['id']}/lore-packs", json={"pack_ids": [pack["id"]]})

    settings = replace(
        client.app.state.settings,
        embeddings_enabled=True,
        embeddings_model="test-embed",
    )
    service = LLMService(settings, client.app.state.database)

    async def fake_embed(inputs: list[str]) -> list[list[float]]:
        vectors = []
        for value in inputs:
            lowered = value.lower()
            if "show doubt" in lowered or "blue pin" in lowered or "uncertain routes" in lowered:
                vectors.append([0.0, 1.0])
            else:
                vectors.append([1.0, 0.0])
        return vectors

    monkeypatch.setattr(service, "_ollama_embed", fake_embed)

    retrieved, mode = await service._retrieve_lore(
        character["id"],
        "How does Ada show doubt on a map?",
        limit=1,
    )

    assert mode == "semantic embeddings"
    assert retrieved[0]["title"] == "Cartographer habit"
    with client.app.state.database.connection() as connection:
        count = connection.execute("SELECT COUNT(*) FROM lore_fact_embeddings").fetchone()[0]
    assert count == 2
