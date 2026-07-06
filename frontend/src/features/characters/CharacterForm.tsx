import { FormEvent, useState } from "react";

import type { Character, CharacterDraft } from "../../types";
import { Avatar } from "../../components/Avatar";
import { Icon } from "../../components/Icon";

const EMPTY: CharacterDraft = {
  name: "",
  avatar_url: "",
  description: "",
  personality: "",
  speaking_style: "",
  backstory: "",
  goals: "",
  boundaries: "",
  backend: "ollama",
  model: "llama3.2:1b",
  temperature: 0.7,
  initiative_frequency: 1,
  cooldown_minutes: 240,
};

export function CharacterForm({
  character,
  onSave,
  onClose,
}: {
  character?: Character;
  onSave: (draft: CharacterDraft) => Promise<void>;
  onClose: () => void;
}) {
  const [draft, setDraft] = useState<CharacterDraft>(
    character
      ? {
          name: character.name,
          avatar_url: character.avatar_url,
          description: character.description,
          personality: character.personality,
          speaking_style: character.speaking_style,
          backstory: character.backstory,
          goals: character.goals,
          boundaries: character.boundaries,
          backend: character.backend,
          model: character.model,
          temperature: character.temperature,
          initiative_frequency: character.initiative_frequency,
          cooldown_minutes: character.cooldown_minutes,
        }
      : EMPTY,
  );
  const [saving, setSaving] = useState(false);

  function field<K extends keyof CharacterDraft>(key: K, value: CharacterDraft[K]) {
    setDraft((current) => ({ ...current, [key]: value }));
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
    <div className="modal-backdrop" role="presentation" onMouseDown={onClose}>
      <section
        className="character-editor"
        role="dialog"
        aria-modal="true"
        aria-labelledby="character-editor-title"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <header>
          <div>
            <h2 id="character-editor-title">
              {character ? `Edit ${character.name}` : "Create a character"}
            </h2>
            <p>Shape their voice, history, model, and initiative.</p>
          </div>
          <button className="text-button" type="button" onClick={onClose}>
            Close
          </button>
        </header>
        <form onSubmit={submit}>
          <div className="editor-profile">
            <Avatar name={draft.name || "New character"} src={draft.avatar_url} size="large" />
            <label className="field field--grow">
              <span>Name</span>
              <input
                required
                value={draft.name}
                onChange={(event) => field("name", event.target.value)}
                placeholder="Character name"
              />
            </label>
            <label className="field field--grow">
              <span>Avatar URL</span>
              <input
                value={draft.avatar_url}
                onChange={(event) => field("avatar_url", event.target.value)}
                placeholder="Optional local or HTTPS image URL"
              />
            </label>
          </div>
          <div className="editor-grid">
            {(
              [
                ["description", "Description", "Who are they at a glance?"],
                ["personality", "Personality", "Temperament, values, and habits."],
                ["speaking_style", "Speaking style", "Rhythm, vocabulary, length, and quirks."],
                ["backstory", "Backstory", "The history they carry into the chat."],
                ["goals", "Goals", "What are they trying to do for or with the user?"],
                ["boundaries", "Boundaries", "What should they avoid or state plainly?"],
              ] as const
            ).map(([key, label, placeholder]) => (
              <label className="field" key={key}>
                <span>{label}</span>
                <textarea
                  value={draft[key]}
                  onChange={(event) => field(key, event.target.value)}
                  placeholder={placeholder}
                  rows={3}
                />
              </label>
            ))}
          </div>
          <div className="editor-model-grid">
            <label className="field">
              <span>Backend</span>
              <select
                value={draft.backend}
                onChange={(event) =>
                  field("backend", event.target.value as CharacterDraft["backend"])
                }
              >
                <option value="ollama">Ollama (local default)</option>
                <option value="llamacpp">llama.cpp (local)</option>
                <option value="openai_compatible">OpenAI-compatible (cloud)</option>
              </select>
            </label>
            <label className="field">
              <span>Model</span>
              <input
                required
                value={draft.model}
                onChange={(event) => field("model", event.target.value)}
              />
            </label>
            <label className="field">
              <span>Randomness · {draft.temperature.toFixed(2)}</span>
              <input
                type="range"
                min="0"
                max="2"
                step="0.05"
                value={draft.temperature}
                onChange={(event) => field("temperature", Number(event.target.value))}
              />
            </label>
            <label className="field">
              <span>Initiative per day</span>
              <input
                type="number"
                min="0"
                max="24"
                step="0.25"
                value={draft.initiative_frequency}
                onChange={(event) => field("initiative_frequency", Number(event.target.value))}
              />
            </label>
            <label className="field">
              <span>Cooldown · minutes</span>
              <input
                type="number"
                min="15"
                max="10080"
                value={draft.cooldown_minutes}
                onChange={(event) => field("cooldown_minutes", Number(event.target.value))}
              />
            </label>
          </div>
          {draft.backend === "openai_compatible" ? (
            <div className="cloud-warning">
              Cloud mode is opt-in. Calls are blocked when any configured rate, token, spend,
              or daily request limit is reached. Dry-run is enabled by default.
            </div>
          ) : null}
          <footer>
            <button className="secondary-button" type="button" onClick={onClose}>
              Cancel
            </button>
            <button className="primary-button" disabled={saving || !draft.name.trim()}>
              <Icon name="check" size={17} />
              {saving ? "Saving…" : "Save character"}
            </button>
          </footer>
        </form>
      </section>
    </div>
  );
}

