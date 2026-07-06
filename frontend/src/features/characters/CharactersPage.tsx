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
}: {
  characters: Character[];
  onCreate: () => void;
  onEdit: (character: Character) => void;
  onDuplicate: (character: Character) => void;
  onDelete: (character: Character) => void;
  onChat: (character: Character) => void;
}) {
  return (
    <section className="content-page">
      <header className="page-header">
        <div>
          <h1>Characters</h1>
          <p>Manage the voices who live here.</p>
        </div>
        <button className="primary-button" type="button" onClick={onCreate}>
          <Icon name="plus" size={17} />
          New character
        </button>
      </header>
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

