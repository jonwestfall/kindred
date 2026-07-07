import { useEffect, useState } from "react";

import { api, systemBackupUrl } from "../../api";
import type { Health } from "../../types";

function ProviderRow({
  name,
  detail,
}: {
  name: string;
  detail: Record<string, unknown>;
}) {
  const available = Boolean(detail.available ?? detail.configured);
  return (
    <article className="provider-row">
      <span className={`status-dot ${available ? "is-ready" : ""}`} />
      <div>
        <strong>{name}</strong>
        <span>{available ? "Available" : "Not available"}</span>
      </div>
      <code>{String(detail.url ?? "")}</code>
      {detail.dry_run === true ? <span className="status-label">Dry run</span> : null}
    </article>
  );
}

export function SystemPage() {
  const [health, setHealth] = useState<Health | null>(null);
  const [usage, setUsage] = useState<Record<string, unknown> | null>(null);
  const [status, setStatus] = useState("");

  useEffect(() => {
    Promise.all([api.health(), api.usage().catch(() => null)]).then(([nextHealth, nextUsage]) => {
      setHealth(nextHealth);
      setUsage(nextUsage);
    });
  }, []);

  async function restoreBackup(file: File | undefined) {
    if (!file) return;
    if (
      !window.confirm(
        "Restore this Kindred backup? This replaces the current database and uploaded files.",
      )
    ) {
      return;
    }
    try {
      const result = await api.system.restore(file);
      setStatus(`Restore complete from ${String(result.manifest.created_at ?? "backup")}.`);
      setHealth(await api.health());
    } catch (caught) {
      setStatus(caught instanceof Error ? caught.message : "Restore failed.");
    }
  }

  async function resetSystem() {
    if (
      !window.confirm(
        "Reset Kindred to its starting state? This deletes local users, chats, imported lore, uploads, and settings.",
      )
    ) {
      return;
    }
    if (!window.confirm("Last check: this cannot be undone unless you have a backup. Reset now?")) {
      return;
    }
    try {
      const result = await api.system.reset();
      setStatus(`Reset complete. Seeded ${result.seeded_characters} starting characters.`);
      const [nextHealth, nextUsage] = await Promise.all([api.health(), api.usage().catch(() => null)]);
      setHealth(nextHealth);
      setUsage(nextUsage);
    } catch (caught) {
      setStatus(caught instanceof Error ? caught.message : "Reset failed.");
    }
  }

  return (
    <section className="content-page">
      <header className="page-header">
        <div>
          <h1>System</h1>
          <p>Backend availability, backups, version metadata, storage, and cloud usage.</p>
        </div>
      </header>
      {status ? <p className="import-status">{status}</p> : null}
      {!health ? <p className="empty-copy">Checking local services…</p> : null}
      {health ? (
        <>
          <section className="system-section system-facts">
            <h2>Version and build</h2>
            <dl>
              <div>
                <dt>Runtime</dt>
                <dd>
                  Python {health.runtime.python} · build {health.runtime.build}
                </dd>
              </div>
              <div>
                <dt>API</dt>
                <dd>
                  v{health.api.version} · build {health.api.build}
                </dd>
              </div>
              <div>
                <dt>Frontend</dt>
                <dd>
                  v{health.frontend.version} · build {health.frontend.build}
                </dd>
              </div>
              <div>
                <dt>Repository</dt>
                <dd>
                  <a href={health.repository_url} rel="noreferrer" target="_blank">
                    {health.repository_url}
                  </a>
                </dd>
              </div>
            </dl>
          </section>
          <section className="system-section system-maintenance">
            <h2>Backup, restore, and reset</h2>
            <p>
              Backups contain the SQLite database plus uploaded local files. Restore and
              reset briefly pause the daemon while local state is replaced.
            </p>
            <div className="maintenance-actions">
              <a className="primary-button" href={systemBackupUrl()}>
                Download backup
              </a>
              <label className="secondary-button file-button">
                Restore backup
                <input
                  accept="application/zip,.zip"
                  type="file"
                  onChange={(event) => void restoreBackup(event.target.files?.[0])}
                />
              </label>
              <button className="secondary-button danger-button" type="button" onClick={resetSystem}>
                Reset to defaults
              </button>
            </div>
          </section>
          <section className="system-section">
            <h2>Model backends</h2>
            <div className="provider-list">
              {Object.entries(health.backends).map(([name, detail]) => (
                <ProviderRow key={name} name={name} detail={detail} />
              ))}
            </div>
          </section>
          <section className="system-section system-facts">
            <h2>Runtime</h2>
            <dl>
              <div>
                <dt>API version</dt>
                <dd>{health.version}</dd>
              </div>
              <div>
                <dt>Environment</dt>
                <dd>{health.environment}</dd>
              </div>
              <div>
                <dt>Host platform</dt>
                <dd>{health.runtime.platform}</dd>
              </div>
              <div>
                <dt>Database</dt>
                <dd>{health.database}</dd>
              </div>
              <div>
                <dt>Daemon process</dt>
                <dd>{health.daemon.process_enabled ? "Enabled" : "Disabled"}</dd>
              </div>
            </dl>
          </section>
          <section className="system-section">
            <h2>Cloud usage windows</h2>
            <pre>{JSON.stringify(usage ?? { unavailable: true }, null, 2)}</pre>
          </section>
        </>
      ) : null}
    </section>
  );
}
