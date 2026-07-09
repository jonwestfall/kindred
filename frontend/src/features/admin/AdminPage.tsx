import { FormEvent, useEffect, useMemo, useState } from "react";

import { api } from "../../api";
import type { Character, NotificationDiagnostics, UserAccount, UserDraft } from "../../types";
import { Icon } from "../../components/Icon";
import { formatDateTime } from "../../utils";

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

function NotificationDiagnosticsPanel({
  diagnostics,
  note,
  onRefresh,
  onDeleteSubscription,
}: {
  diagnostics: NotificationDiagnostics | null;
  note: string;
  onRefresh: () => Promise<void>;
  onDeleteSubscription: (subscriptionId: number) => Promise<void>;
}) {
  return (
    <section className="admin-test-card notification-diagnostics-card" aria-labelledby="notification-diagnostics-heading">
      <div className="diagnostics-heading">
        <div>
          <h2 id="notification-diagnostics-heading">Notification diagnostics</h2>
          <p>
            Inspect saved browser push subscriptions, active in-app WebSocket connections, and
            recent Web Push attempts. Use this when testing iPhone/Tailscale delivery.
          </p>
        </div>
        <button className="secondary-button" type="button" onClick={() => void onRefresh()}>
          Refresh
        </button>
      </div>
      {note ? <p className="form-error">{note}</p> : null}
      {diagnostics ? (
        <>
          <div className="diagnostic-metrics">
            <span>
              <strong>{diagnostics.notifications_enabled ? "On" : "Off"}</strong>
              Notifications setting
            </span>
            <span>
              <strong>{diagnostics.web_push_configured ? "Ready" : "Missing"}</strong>
              VAPID / Web Push
            </span>
            <span>
              <strong>{diagnostics.subscription_count}</strong>
              Saved subscription(s)
            </span>
            <span>
              <strong>{diagnostics.active_websocket_count}</strong>
              Active socket(s)
            </span>
          </div>
          <p className="diagnostic-subtle">VAPID subject: {diagnostics.vapid_subject}</p>
          <div className="diagnostic-columns">
            <div>
              <h3>Subscriptions</h3>
              {diagnostics.subscriptions.length === 0 ? (
                <p className="empty-copy">No saved browser subscriptions yet.</p>
              ) : null}
              {diagnostics.subscriptions.map((subscription) => (
                <article className="diagnostic-row" key={subscription.id}>
                  <div>
                    <strong>{subscription.endpoint_host || "Unknown endpoint"}</strong>
                    <span>{subscription.endpoint_preview}</span>
                    <small>
                      {subscription.owner_label} · subscribed {formatDateTime(subscription.created_at)} ·{" "}
                      {subscription.has_keys ? "keys present" : "missing keys"}
                    </small>
                  </div>
                  <button
                    className="icon-button danger"
                    type="button"
                    aria-label={`Remove subscription ${subscription.id}`}
                    onClick={() => {
                      if (!window.confirm("Remove this saved browser notification subscription?")) return;
                      void onDeleteSubscription(subscription.id);
                    }}
                  >
                    <Icon name="trash" />
                  </button>
                </article>
              ))}
            </div>
            <div>
              <h3>Recent Web Push attempts</h3>
              {diagnostics.recent_deliveries.length === 0 ? (
                <p className="empty-copy">No delivery attempts logged yet.</p>
              ) : null}
              {diagnostics.recent_deliveries.map((delivery) => (
                <article className="diagnostic-row diagnostic-row--attempt" key={delivery.id}>
                  <div>
                    <strong>
                      <span className={`status-pill status-pill--${delivery.status}`}>
                        {delivery.status}
                      </span>
                      {delivery.endpoint_host || "No endpoint"}
                    </strong>
                    <span>{delivery.detail}</span>
                    <small>
                      {delivery.owner_label} · {formatDateTime(delivery.timestamp)}
                      {delivery.thread_id ? ` · thread #${delivery.thread_id}` : ""}
                      {delivery.message_id ? ` · message #${delivery.message_id}` : ""}
                    </small>
                  </div>
                </article>
              ))}
            </div>
          </div>
        </>
      ) : (
        <p className="empty-copy">Notification diagnostics have not loaded yet.</p>
      )}
    </section>
  );
}

export function AdminPage({ characters }: { characters: Character[] }) {
  const [users, setUsers] = useState<UserAccount[]>([]);
  const [editing, setEditing] = useState<UserAccount | null>(null);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState("");
  const [diagnostics, setDiagnostics] = useState<NotificationDiagnostics | null>(null);
  const [diagnosticsNote, setDiagnosticsNote] = useState("");
  const [testCharacterId, setTestCharacterId] = useState("");
  const [testResult, setTestResult] = useState("");
  const characterNames = useMemo(
    () => new Map(characters.map((character) => [character.id, character.name])),
    [characters],
  );

  async function refreshDiagnostics() {
    setDiagnosticsNote("");
    try {
      setDiagnostics(await api.notificationDiagnostics("all"));
    } catch (caught) {
      setDiagnosticsNote(caught instanceof Error ? caught.message : "Diagnostics failed.");
    }
  }

  async function refresh() {
    const [nextUsers, nextDiagnostics] = await Promise.all([
      api.users.list(),
      api.notificationDiagnostics("all"),
    ]);
    setUsers(nextUsers);
    setDiagnostics(nextDiagnostics);
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

  async function sendNotificationTest(event: FormEvent) {
    event.preventDefault();
    if (!testCharacterId) return;
    setTestResult("Sending a logged test message through the live notification path…");
    try {
      const result = await api.testNotification(Number(testCharacterId));
      setTestResult(
        [
          `Sent to thread #${result.thread_id}.`,
          result.web_push_configured
            ? "VAPID/Web Push is configured."
            : "VAPID/Web Push is not configured; open tabs still receive WebSocket events.",
          `${result.subscription_count} saved subscription(s) for this signed-in account.`,
        ].join(" "),
      );
      await refreshDiagnostics();
    } catch (caught) {
      setTestResult(caught instanceof Error ? caught.message : "Notification test failed.");
    }
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
      <section className="admin-test-card" aria-labelledby="notification-test-heading">
        <div>
          <h2 id="notification-test-heading">Notification delivery test</h2>
          <p>
            Send a logged character message to this signed-in account without waiting for the
            scheduler or model. This exercises the same WebSocket, toast, service-worker, and Web
            Push fan-out used by real character messages.
          </p>
        </div>
        <form className="notification-test-form" onSubmit={sendNotificationTest}>
          <label className="field">
            <span>Character to send from</span>
            <select
              value={testCharacterId}
              onChange={(event) => setTestCharacterId(event.target.value)}
              required
            >
              <option value="" disabled>
                Choose a character…
              </option>
              {characters.map((character) => (
                <option key={character.id} value={character.id}>
                  {character.name}
                </option>
              ))}
            </select>
          </label>
          <button className="primary-button" type="submit" disabled={!testCharacterId}>
            Send test message
          </button>
        </form>
        {testResult ? <p className="empty-copy">{testResult}</p> : null}
        <p className="admin-test-note">
          To test full autonomous generation too, use Settings → Autonomous messages → Test one
          character now.
        </p>
      </section>
      <NotificationDiagnosticsPanel
        diagnostics={diagnostics}
        note={diagnosticsNote}
        onRefresh={refreshDiagnostics}
        onDeleteSubscription={async (subscriptionId) => {
          await api.deleteNotificationSubscription(subscriptionId);
          await refreshDiagnostics();
        }}
      />
    </section>
  );
}
