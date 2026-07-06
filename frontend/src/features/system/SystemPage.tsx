import { useEffect, useState } from "react";

import { api } from "../../api";
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

  useEffect(() => {
    Promise.all([api.health(), api.usage()]).then(([nextHealth, nextUsage]) => {
      setHealth(nextHealth);
      setUsage(nextUsage);
    });
  }, []);

  return (
    <section className="content-page">
      <header className="page-header">
        <div>
          <h1>System</h1>
          <p>Backend availability, daemon state, storage, and cloud usage.</p>
        </div>
      </header>
      {!health ? <p className="empty-copy">Checking local services…</p> : null}
      {health ? (
        <>
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
            <pre>{JSON.stringify(usage, null, 2)}</pre>
          </section>
        </>
      ) : null}
    </section>
  );
}

