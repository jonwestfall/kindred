import { FormEvent, useEffect, useMemo, useState } from "react";

import { api } from "../../api";
import type { Character, UserAccount, UserDraft } from "../../types";
import { Icon } from "../../components/Icon";

const emptyDraft: UserDraft = {
  username: "",
  display_name: "",
  password: "",
  disabled: false,
  character_ids: [],
};

function AccountForm({
  characters,
  editing,
  onSave,
  onCancel,
}: {
  characters: Character[];
  editing: UserAccount | null;
  onSave: (draft: UserDraft) => Promise<void>;
  onCancel: () => void;
}) {
  const [draft, setDraft] = useState<UserDraft>(
    editing
      ? {
          username: editing.username,
          display_name: editing.display_name,
          password: "",
          disabled: editing.disabled,
          character_ids: editing.character_ids,
        }
      : emptyDraft,
  );
  const [saving, setSaving] = useState(false);
  const title = editing ? `Edit ${editing.username}` : "Create user";

  useEffect(() => {
    setDraft(
      editing
        ? {
            username: editing.username,
            display_name: editing.display_name,
            password: "",
            disabled: editing.disabled,
            character_ids: editing.character_ids,
          }
        : emptyDraft,
    );
  }, [editing]);

  function toggleCharacter(characterId: number) {
    setDraft((current) => ({
      ...current,
      character_ids: current.character_ids.includes(characterId)
        ? current.character_ids.filter((id) => id !== characterId)
        : [...current.character_ids, characterId],
    }));
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    try {
      await onSave(draft);
    } finally {
      setSaving(false);
    }
  }

  return (
    <form className="account-form" onSubmit={submit}>
      <div className="form-heading">
        <h2>{title}</h2>
        <button className="icon-button" type="button" onClick={onCancel} aria-label="Cancel">
          ×
        </button>
      </div>
      <label className="field">
        <span>Username</span>
        <input
          value={draft.username}
          onChange={(event) => setDraft({ ...draft, username: event.target.value })}
          required
        />
      </label>
      <label className="field">
        <span>Display name</span>
        <input
          value={draft.display_name}
          onChange={(event) => setDraft({ ...draft, display_name: event.target.value })}
          placeholder="Optional"
        />
      </label>
      <label className="field">
        <span>{editing ? "New password" : "Password"}</span>
        <input
          value={draft.password ?? ""}
          onChange={(event) => setDraft({ ...draft, password: event.target.value })}
          placeholder={editing ? "Leave blank to keep current password" : "At least 8 characters"}
          required={!editing}
          minLength={editing && !(draft.password ?? "") ? undefined : 8}
          type="password"
        />
      </label>
      <label className="toggle-row">
        <span>Disable account</span>
        <input
          type="checkbox"
          checked={draft.disabled}
          onChange={(event) => setDraft({ ...draft, disabled: event.target.checked })}
        />
      </label>
      <fieldset className="character-access-list">
        <legend>Characters this user can chat with</legend>
        {characters.map((character) => (
          <label key={character.id} className="access-check">
            <input
              type="checkbox"
              checked={draft.character_ids.includes(character.id)}
              onChange={() => toggleCharacter(character.id)}
            />
            <span>{character.name}</span>
          </label>
        ))}
      </fieldset>
      <button className="primary-button" disabled={saving}>
        {saving ? "Saving…" : "Save account"}
      </button>
    </form>
  );
}

export function AdminPage({ characters }: { characters: Character[] }) {
  const [users, setUsers] = useState<UserAccount[]>([]);
  const [editing, setEditing] = useState<UserAccount | null>(null);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState("");
  const characterNames = useMemo(
    () => new Map(characters.map((character) => [character.id, character.name])),
    [characters],
  );

  async function refresh() {
    setUsers(await api.users.list());
  }

  useEffect(() => {
    refresh().catch((caught) => setError(caught instanceof Error ? caught.message : "Users failed."));
  }, []);

  async function save(draft: UserDraft) {
    const payload = { ...draft };
    if (!payload.password) delete payload.password;
    if (editing) {
      await api.users.update(editing.id, payload);
    } else {
      await api.users.create({ ...draft, password: draft.password ?? "" });
    }
    setEditing(null);
    setCreating(false);
    await refresh();
  }

  return (
    <section className="content-page">
      <header className="page-header">
        <div>
          <h1>Admin</h1>
          <p>Manage local user accounts, character access, and the shared Kindred boundary.</p>
        </div>
        <button className="primary-button" type="button" onClick={() => setCreating(true)}>
          <Icon name="plus" size={17} />
          Add user
        </button>
      </header>
      {error ? <p className="form-error">{error}</p> : null}
      <div className="admin-grid">
        <div className="account-list">
          {users.length === 0 ? <p className="empty-copy">No regular users yet.</p> : null}
          {users.map((user) => (
            <article className="account-row" key={user.id}>
              <div>
                <strong>{user.display_name || user.username}</strong>
                <span>
                  @{user.username}
                  {user.disabled ? " · disabled" : ""}
                </span>
                <small>
                  {user.character_ids.length
                    ? user.character_ids
                        .map((id) => characterNames.get(id) ?? `#${id}`)
                        .join(", ")
                    : "No character access"}
                </small>
              </div>
              <div className="row-actions">
                <button className="secondary-button" type="button" onClick={() => setEditing(user)}>
                  Edit
                </button>
                <button
                  className="secondary-button"
                  type="button"
                  onClick={async () => {
                    await api.users.update(user.id, { disabled: !user.disabled });
                    await refresh();
                  }}
                >
                  {user.disabled ? "Enable" : "Disable"}
                </button>
                <button
                  className="icon-button danger"
                  type="button"
                  aria-label={`Delete ${user.username}`}
                  onClick={async () => {
                    if (!window.confirm(`Delete user ${user.username}? Their chats remain in logs.`)) return;
                    await api.users.remove(user.id);
                    await refresh();
                  }}
                >
                  <Icon name="trash" />
                </button>
              </div>
            </article>
          ))}
        </div>
        {creating || editing ? (
          <AccountForm
            characters={characters}
            editing={editing}
            onSave={save}
            onCancel={() => {
              setCreating(false);
              setEditing(null);
            }}
          />
        ) : (
          <aside className="admin-note">
            <h2>Environment administrator</h2>
            <p>
              The root administrator is configured in <code>.env</code>, not stored in SQLite.
              Use it as the break-glass account for this local installation.
            </p>
          </aside>
        )}
      </div>
    </section>
  );
}
