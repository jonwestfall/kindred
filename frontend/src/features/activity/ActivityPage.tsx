import { FormEvent, useEffect, useState } from "react";

import { api, exportUrl } from "../../api";
import type { Character, LogRecord } from "../../types";
import { formatDateTime } from "../../utils";
import { Avatar } from "../../components/Avatar";
import { Icon } from "../../components/Icon";

export function ActivityPage({ characters }: { characters: Character[] }) {
  const [logs, setLogs] = useState<LogRecord[]>([]);
  const [keyword, setKeyword] = useState("");
  const [characterId, setCharacterId] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [loading, setLoading] = useState(true);

  async function search(event?: FormEvent) {
    event?.preventDefault();
    setLoading(true);
    const params = new URLSearchParams();
    if (keyword) params.set("keyword", keyword);
    if (characterId) params.set("character_id", characterId);
    if (dateFrom) params.set("date_from", dateFrom);
    if (dateTo) params.set("date_to", dateTo);
    try {
      setLogs(await api.logs(params));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void search();
    // Initial load only; filter submits are explicit.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const filters = {
    ...(keyword ? { keyword } : {}),
    ...(characterId ? { character_id: characterId } : {}),
    ...(dateFrom ? { date_from: dateFrom } : {}),
    ...(dateTo ? { date_to: dateTo } : {}),
  };

  return (
    <section className="content-page">
      <header className="page-header">
        <div>
          <h1>Activity</h1>
          <p>Search every locally stored conversation.</p>
        </div>
        <div className="header-actions">
          <a className="secondary-button" href={exportUrl("json", filters)}>
            Export JSON
          </a>
          <a className="primary-button" href={exportUrl("markdown", filters)}>
            Export Markdown
          </a>
        </div>
      </header>
      <form className="filter-bar" onSubmit={search}>
        <label className="search-field">
          <Icon name="search" size={18} />
          <input
            value={keyword}
            onChange={(event) => setKeyword(event.target.value)}
            placeholder="Search message text"
            aria-label="Keyword"
          />
        </label>
        <select
          value={characterId}
          onChange={(event) => setCharacterId(event.target.value)}
          aria-label="Character"
        >
          <option value="">All characters</option>
          {characters.map((character) => (
            <option key={character.id} value={character.id}>
              {character.name}
            </option>
          ))}
        </select>
        <input
          type="date"
          value={dateFrom}
          onChange={(event) => setDateFrom(event.target.value)}
          aria-label="From date"
        />
        <input
          type="date"
          value={dateTo}
          onChange={(event) => setDateTo(event.target.value)}
          aria-label="To date"
        />
        <button className="secondary-button" type="submit">
          Filter
        </button>
      </form>
      <div className="activity-list">
        {loading ? <p className="empty-copy">Loading activity…</p> : null}
        {!loading && logs.length === 0 ? (
          <p className="empty-copy">No messages match these filters.</p>
        ) : null}
        {logs.map((record) => (
          <article className="activity-row" key={record.id}>
            <Avatar
              name={record.sender === "user" ? "You" : record.character_name}
              size="small"
            />
            <div>
              <div className="activity-meta">
                <strong>{record.sender === "user" ? "You" : record.character_name}</strong>
                <span>with {record.character_name}</span>
                <time>{formatDateTime(record.timestamp)}</time>
              </div>
              <p>{record.content}</p>
              {record.backend ? (
                <details>
                  <summary>
                    {record.backend} · {record.model}
                  </summary>
                  <p>Context: {record.prompt_context_summary || "n/a"}</p>
                  <p>Character rationale: {record.character_rationale || "n/a"}</p>
                </details>
              ) : null}
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

