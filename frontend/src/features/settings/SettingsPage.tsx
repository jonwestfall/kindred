import { FormEvent, useEffect, useState } from "react";

import { api } from "../../api";
import type { AppSettings, Character } from "../../types";
import { NotificationButton } from "../../components/NotificationButton";

export function SettingsPage({ characters }: { characters: Character[] }) {
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [saved, setSaved] = useState("");
  const [daemonResult, setDaemonResult] = useState("");

  useEffect(() => {
    api.settings.get().then(setSettings);
  }, []);

  if (!settings) {
    return <p className="empty-copy page-loading">Loading settings…</p>;
  }

  async function save(event: FormEvent) {
    event.preventDefault();
    if (!settings) return;
    const sections: Array<keyof AppSettings> = [
      "daemon",
      "limits",
      "notifications",
      "world_notes",
    ];
    let updated = settings;
    for (const section of sections) {
      updated = await api.settings.update(section, settings[section]);
    }
    setSettings(updated);
    setSaved("Saved locally");
    window.setTimeout(() => setSaved(""), 2500);
  }

  async function testDaemon(characterId: number) {
    setDaemonResult("Generating a forced autonomous message…");
    const result = await api.daemonRun(characterId);
    setDaemonResult(String(result[0]?.note ?? "Daemon cycle complete."));
  }

  return (
    <section className="content-page">
      <header className="page-header">
        <div>
          <h1>Settings</h1>
          <p>Local behavior, limits, notifications, and world context.</p>
        </div>
        <div className="save-state">{saved}</div>
      </header>
      <form className="settings-sections" onSubmit={save}>
        <section className="settings-section">
          <div className="settings-copy">
            <h2>Autonomous messages</h2>
            <p>
              The daemon checks elapsed time and each character's initiative, then enforces quiet
              hours and cooldowns before generating anything.
            </p>
          </div>
          <div className="settings-fields">
            <label className="toggle-row">
              <span>Enable scheduled checks</span>
              <input
                type="checkbox"
                checked={settings.daemon.enabled}
                onChange={(event) =>
                  setSettings({
                    ...settings,
                    daemon: { ...settings.daemon, enabled: event.target.checked },
                  })
                }
              />
            </label>
            <div className="two-fields">
              <label className="field">
                <span>Quiet hours start</span>
                <input
                  type="time"
                  value={settings.daemon.quiet_hours_start}
                  onChange={(event) =>
                    setSettings({
                      ...settings,
                      daemon: { ...settings.daemon, quiet_hours_start: event.target.value },
                    })
                  }
                />
              </label>
              <label className="field">
                <span>Quiet hours end</span>
                <input
                  type="time"
                  value={settings.daemon.quiet_hours_end}
                  onChange={(event) =>
                    setSettings({
                      ...settings,
                      daemon: { ...settings.daemon, quiet_hours_end: event.target.value },
                    })
                  }
                />
              </label>
            </div>
            <label className="field">
              <span>Test one character now</span>
              <select
                defaultValue=""
                onChange={(event) => {
                  if (event.target.value) void testDaemon(Number(event.target.value));
                  event.target.value = "";
                }}
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
              {daemonResult ? <small>{daemonResult}</small> : null}
            </label>
          </div>
        </section>

        <section className="settings-section">
          <div className="settings-copy">
            <h2>Cloud protection</h2>
            <p>
              Every OpenAI-compatible or image call is checked before dispatch. Local calls cost
              nothing and are not counted here.
            </p>
          </div>
          <div className="settings-fields two-fields">
            {(
              [
                ["requests_per_hour", "Requests per hour", 1],
                ["requests_per_day", "Requests per day", 1],
                ["tokens_per_day", "Tokens per day", 100],
                ["cloud_spend_ceiling_usd", "Spend ceiling · USD", 0.25],
                ["image_generations_per_day", "Images per day", 1],
              ] as const
            ).map(([key, label, step]) => (
              <label className="field" key={key}>
                <span>{label}</span>
                <input
                  type="number"
                  min="0"
                  step={step}
                  value={settings.limits[key]}
                  onChange={(event) =>
                    setSettings({
                      ...settings,
                      limits: { ...settings.limits, [key]: Number(event.target.value) },
                    })
                  }
                />
              </label>
            ))}
          </div>
        </section>

        <section className="settings-section">
          <div className="settings-copy">
            <h2>Notifications</h2>
            <p>
              Open tabs receive WebSocket events. Background delivery uses a service worker and
              Web Push when VAPID keys and HTTPS are configured.
            </p>
          </div>
          <div className="settings-fields notification-settings">
            <NotificationButton />
            <p>Use the bell to request browser permission and register this browser.</p>
          </div>
        </section>

        <section className="settings-section">
          <div className="settings-copy">
            <h2>Project and world notes</h2>
            <p>
              Optional context shared with characters. Avoid secrets: it is sent to a cloud
              provider when—and only when—the selected character uses one.
            </p>
          </div>
          <div className="settings-fields">
            <label className="field">
              <span>Notes</span>
              <textarea
                rows={8}
                value={settings.world_notes}
                onChange={(event) =>
                  setSettings({ ...settings, world_notes: event.target.value })
                }
                placeholder="Places, projects, continuity notes, or shared context…"
              />
            </label>
          </div>
        </section>
        <footer className="settings-footer">
          <button className="primary-button">Save settings</button>
        </footer>
      </form>
    </section>
  );
}
