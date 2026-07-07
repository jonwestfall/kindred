import { useRef, useState } from "react";

import { characterExportUrl, charactersExportUrl } from "../../api";
import type { Character } from "../../types";
import { Avatar } from "../../components/Avatar";
import { Icon } from "../../components/Icon";

export function CharactersPage({
  characters,
  onCreate,
  onEdit,
  onDuplicate,
  onDelete,
  onChat,
  onImportBundle,
}: {
  characters: Character[];
  onCreate: () => void;
  onEdit: (character: Character) => void;
  onDuplicate: (character: Character) => void;
  onDelete: (character: Character) => void;
  onChat: (character: Character) => void;
  onImportBundle: (bundle: unknown) => Promise<{ created: Character[]; skipped: string[] }>;
}) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [importStatus, setImportStatus] = useState("");
  const [importing, setImporting] = useState(false);

  async function importFile(file: File) {
    setImporting(true);
    setImportStatus("");
    try {
      const bundle = JSON.parse(await file.text()) as unknown;
      const result = await onImportBundle(bundle);
      const created = result.created.length;
      const skipped = result.skipped.length;
      setImportStatus(`Imported ${created} character${created === 1 ? "" : "s"}${skipped ? `; skipped ${skipped}` : ""}.`);
    } catch (caught) {
      setImportStatus(caught instanceof Error ? caught.message : "Import failed.");
    } finally {
      setImporting(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  return (
    <section className="content-page">
      <header className="page-header">
        <div>
          <h1>Characters</h1>
          <p>Manage the voices who live here.</p>
        </div>
        <div className="header-actions">
          <a className="secondary-button" href={charactersExportUrl()}>
            Export all
          </a>
          <button
            className="secondary-button"
            type="button"
            disabled={importing}
            onClick={() => fileInputRef.current?.click()}
          >
            Import JSON
          </button>
          <button className="primary-button" type="button" onClick={onCreate}>
            <Icon name="plus" size={17} />
            New character
          </button>
        </div>
      </header>
      <input
        ref={fileInputRef}
        className="visually-hidden"
        type="file"
        accept="application/json,.json"
        onChange={(event) => {
          const file = event.currentTarget.files?.[0];
          if (file) void importFile(file);
        }}
      />
      {importStatus ? <p className="import-status">{importStatus}</p> : null}
      <div className="character-table" role="list">
        {characters.map((character) => (
          <article className="character-row" role="listitem" key={character.id}>
            <button className="character-identity" type="button" onClick={() => onChat(character)}>
              <Avatar name={character.name} src={character.avatar_url} size="large" />
              <span>
                <strong>{character.name}</strong>
                <span>{character.description || "No description yet."}</span>
              </span>
            </button>
            <div className="character-model">
              <strong>{character.model}</strong>
              <span>
                {character.backend === "openai_compatible" ? "Cloud" : "Local"} ·{" "}
                {character.initiative_frequency}/day
              </span>
            </div>
            <div className="row-actions">
              <a
                className="icon-button"
                href={characterExportUrl(character.id)}
                title="Export character"
                aria-label={`Export ${character.name}`}
              >
                <Icon name="activity" />
              </a>
              <button
                className="icon-button"
                type="button"
                onClick={() => onEdit(character)}
                title="Edit character"
                aria-label={`Edit ${character.name}`}
              >
                <Icon name="edit" />
              </button>
              <button
                className="icon-button"
                type="button"
                onClick={() => onDuplicate(character)}
                title="Duplicate character"
                aria-label={`Duplicate ${character.name}`}
              >
                <Icon name="duplicate" />
              </button>
              <button
                className="icon-button danger"
                type="button"
                onClick={() => onDelete(character)}
                title="Delete character"
                aria-label={`Delete ${character.name}`}
              >
                <Icon name="trash" />
              </button>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
