import { useEffect, useMemo, useState } from "react";

import { api, lorePackExportUrl } from "../../api";
import type { Character, LorePack } from "../../types";

function packCharacterNames(pack: LorePack, characters: Character[]): string {
  const names = pack.character_ids
    .map((id) => characters.find((character) => character.id === id)?.name)
    .filter(Boolean);
  return names.length ? names.join(", ") : "Not assigned yet";
}

export function LorePage({ characters }: { characters: Character[] }) {
  const [packs, setPacks] = useState<LorePack[]>([]);
  const [selectedCharacterId, setSelectedCharacterId] = useState<number | "">("");
  const [selectedPackIds, setSelectedPackIds] = useState<number[]>([]);
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(true);

  const selectedCharacter = useMemo(
    () => characters.find((character) => character.id === selectedCharacterId),
    [characters, selectedCharacterId],
  );

  async function refresh() {
    setPacks(await api.lore.list());
  }

  useEffect(() => {
    refresh()
      .catch((caught) =>
        setStatus(caught instanceof Error ? caught.message : "Lore packs could not load."),
      )
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!selectedCharacterId) {
      setSelectedPackIds([]);
      return;
    }
    api.lore
      .getAssignment(selectedCharacterId)
      .then((assignment) => setSelectedPackIds(assignment.pack_ids))
      .catch((caught) =>
        setStatus(caught instanceof Error ? caught.message : "Assignment could not load."),
      );
  }, [selectedCharacterId]);

  async function importPack(file: File | undefined) {
    if (!file) return;
    try {
      const bundle = JSON.parse(await file.text()) as unknown;
      const pack = await api.lore.importPack(bundle);
      await refresh();
      setStatus(`Imported ${pack.name} with ${pack.fact_count} fact(s).`);
    } catch (caught) {
      setStatus(caught instanceof Error ? caught.message : "Fact pack import failed.");
    }
  }

  async function saveAssignment() {
    if (!selectedCharacterId) return;
    await api.lore.setAssignment(selectedCharacterId, selectedPackIds);
    await refresh();
    setStatus(`Updated lore for ${selectedCharacter?.name ?? "character"}.`);
  }

  function togglePack(packId: number) {
    setSelectedPackIds((current) =>
      current.includes(packId)
        ? current.filter((id) => id !== packId)
        : [...current, packId].sort((left, right) => left - right),
    );
  }

  return (
    <section className="content-page">
      <header className="page-header">
        <div>
          <h1>Lore & fact packs</h1>
          <p className="page-kicker">
            Import local JSON fact files, attach them to characters, and Kindred will retrieve
            relevant facts during chat generation.
          </p>
        </div>
        <label className="secondary-button file-button">
          Import fact pack
          <input
            accept="application/json,.json"
            type="file"
            onChange={(event) => void importPack(event.target.files?.[0])}
          />
        </label>
      </header>

      {status ? <p className="import-status">{status}</p> : null}

      <div className="lore-grid">
        <section className="lore-packs">
          <h2>Imported packs</h2>
          {loading ? <p className="empty-copy">Loading lore packs…</p> : null}
          {!loading && packs.length === 0 ? (
            <p className="empty-copy">
              No fact packs yet. Generate one with the prompt in the docs, then import it here.
            </p>
          ) : null}
          {packs.map((pack) => (
            <article className="lore-pack-card" key={pack.id}>
              <div>
                <h3>{pack.name}</h3>
                <p>{pack.description || "No description provided."}</p>
                <small>
                  {pack.fact_count} facts · {pack.source_title || "Unspecified source"} · assigned to{" "}
                  {packCharacterNames(pack, characters)}
                </small>
              </div>
              <div className="row-actions">
                <a className="secondary-button" href={lorePackExportUrl(pack.id)}>
                  Export
                </a>
                <button
                  className="secondary-button"
                  type="button"
                  onClick={async () => {
                    if (!window.confirm(`Delete the ${pack.name} fact pack?`)) return;
                    await api.lore.remove(pack.id);
                    await refresh();
                  }}
                >
                  Delete
                </button>
              </div>
            </article>
          ))}
        </section>

        <aside className="lore-assignment">
          <h2>Assign to character</h2>
          <p>
            A character only retrieves facts from packs assigned here. This keeps unrelated
            worlds from bleeding into chats.
          </p>
          <label>
            Character
            <select
              value={selectedCharacterId}
              onChange={(event) =>
                setSelectedCharacterId(event.target.value ? Number(event.target.value) : "")
              }
            >
              <option value="">Choose a character</option>
              {characters.map((character) => (
                <option key={character.id} value={character.id}>
                  {character.name}
                </option>
              ))}
            </select>
          </label>
          <fieldset className="character-access-list">
            <legend>Fact packs</legend>
            {packs.map((pack) => (
              <label className="access-check" key={pack.id}>
                <input
                  checked={selectedPackIds.includes(pack.id)}
                  disabled={!selectedCharacterId}
                  type="checkbox"
                  onChange={() => togglePack(pack.id)}
                />
                <span>{pack.name}</span>
              </label>
            ))}
          </fieldset>
          <button
            className="primary-button"
            disabled={!selectedCharacterId}
            type="button"
            onClick={() => void saveAssignment()}
          >
            Save lore assignment
          </button>
        </aside>
      </div>
    </section>
  );
}
