"""Small, explicit SQLite persistence layer.

The application intentionally uses the standard-library sqlite3 driver. Each
operation gets a short-lived connection, which keeps threading behavior clear
under FastAPI and avoids an ORM footprint on Raspberry Pi hardware.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Iterator, Sequence


SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS characters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    avatar_url TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    personality TEXT NOT NULL DEFAULT '',
    speaking_style TEXT NOT NULL DEFAULT '',
    backstory TEXT NOT NULL DEFAULT '',
    goals TEXT NOT NULL DEFAULT '',
    boundaries TEXT NOT NULL DEFAULT '',
    backend TEXT NOT NULL DEFAULT 'ollama',
    model TEXT NOT NULL DEFAULT 'llama3.2:1b',
    temperature REAL NOT NULL DEFAULT 0.7,
    initiative_frequency REAL NOT NULL DEFAULT 1.0,
    cooldown_minutes INTEGER NOT NULL DEFAULT 240,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS threads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    title TEXT NOT NULL DEFAULT 'Conversation',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    thread_id INTEGER NOT NULL REFERENCES threads(id) ON DELETE CASCADE,
    character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    sender TEXT NOT NULL CHECK(sender IN ('user', 'character', 'system')),
    content TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    backend TEXT NOT NULL DEFAULT '',
    model TEXT NOT NULL DEFAULT '',
    prompt_context_summary TEXT NOT NULL DEFAULT '',
    character_rationale TEXT NOT NULL DEFAULT '',
    initiated INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_messages_thread_time ON messages(thread_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_messages_character_time ON messages(character_id, timestamp);
CREATE TABLE IF NOT EXISTS app_settings (
    section TEXT PRIMARY KEY,
    value_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS usage_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    request_kind TEXT NOT NULL,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    estimated_cost_usd REAL NOT NULL DEFAULT 0,
    dry_run INTEGER NOT NULL DEFAULT 0,
    character_id INTEGER REFERENCES characters(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_usage_time ON usage_logs(timestamp);
CREATE TABLE IF NOT EXISTS push_subscriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    endpoint TEXT NOT NULL UNIQUE,
    subscription_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS daemon_state (
    character_id INTEGER PRIMARY KEY REFERENCES characters(id) ON DELETE CASCADE,
    last_checked_at TEXT,
    last_initiated_at TEXT,
    last_decision_note TEXT NOT NULL DEFAULT ''
);
"""

CHARACTER_COLUMNS = (
    "name",
    "avatar_url",
    "description",
    "personality",
    "speaking_style",
    "backstory",
    "goals",
    "boundaries",
    "backend",
    "model",
    "temperature",
    "initiative_frequency",
    "cooldown_minutes",
)


def utc_now() -> datetime:
    """Return an aware UTC timestamp."""

    return datetime.now(UTC)


def iso(value: datetime | None = None) -> str:
    """Serialize a timestamp consistently for SQLite ordering."""

    return (value or utc_now()).astimezone(UTC).isoformat()


class Database:
    """Repository-style access to Kindred's single SQLite database."""

    def __init__(self, path: Path):
        self.path = path

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        """Open a configured connection and commit or roll back atomically."""

        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self, defaults: dict[str, Any]) -> None:
        """Create tables and fill only missing safe default settings."""

        with self.connection() as connection:
            connection.executescript(SCHEMA)
            now = iso()
            for section, value in defaults.items():
                connection.execute(
                    "INSERT OR IGNORE INTO app_settings(section, value_json, updated_at) VALUES (?, ?, ?)",
                    (section, json.dumps(value), now),
                )

    def seed_characters(self, characters: Sequence[dict[str, Any]]) -> int:
        """Insert seed characters only when the character table is empty."""

        with self.connection() as connection:
            count = connection.execute("SELECT COUNT(*) FROM characters").fetchone()[0]
        if count:
            return 0
        for character in characters:
            self.create_character(character)
        return len(characters)

    def list_characters(self) -> list[dict[str, Any]]:
        with self.connection() as connection:
            rows = connection.execute("SELECT * FROM characters ORDER BY name COLLATE NOCASE").fetchall()
        return [dict(row) for row in rows]

    def get_character(self, character_id: int) -> dict[str, Any] | None:
        with self.connection() as connection:
            row = connection.execute("SELECT * FROM characters WHERE id = ?", (character_id,)).fetchone()
        return dict(row) if row else None

    def create_character(self, values: dict[str, Any]) -> dict[str, Any]:
        now = iso()
        columns = ", ".join(CHARACTER_COLUMNS)
        placeholders = ", ".join("?" for _ in CHARACTER_COLUMNS)
        params = [values.get(column, "") for column in CHARACTER_COLUMNS]
        with self.connection() as connection:
            cursor = connection.execute(
                f"INSERT INTO characters ({columns}, created_at, updated_at) "
                f"VALUES ({placeholders}, ?, ?)",
                (*params, now, now),
            )
            character_id = cursor.lastrowid
        return self.get_character(int(character_id))  # type: ignore[arg-type, return-value]

    def update_character(self, character_id: int, values: dict[str, Any]) -> dict[str, Any] | None:
        safe = {key: value for key, value in values.items() if key in CHARACTER_COLUMNS}
        if not safe:
            return self.get_character(character_id)
        assignments = ", ".join(f"{key} = ?" for key in safe)
        with self.connection() as connection:
            connection.execute(
                f"UPDATE characters SET {assignments}, updated_at = ? WHERE id = ?",
                (*safe.values(), iso(), character_id),
            )
        return self.get_character(character_id)

    def delete_character(self, character_id: int) -> bool:
        with self.connection() as connection:
            cursor = connection.execute("DELETE FROM characters WHERE id = ?", (character_id,))
        return cursor.rowcount > 0

    def duplicate_character(self, character_id: int) -> dict[str, Any] | None:
        original = self.get_character(character_id)
        if not original:
            return None
        values = {column: original[column] for column in CHARACTER_COLUMNS}
        values["name"] = f"{values['name']} (copy)"
        return self.create_character(values)

    def create_thread(self, character_id: int, title: str = "Conversation") -> dict[str, Any]:
        now = iso()
        with self.connection() as connection:
            cursor = connection.execute(
                "INSERT INTO threads(character_id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (character_id, title, now, now),
            )
            thread_id = cursor.lastrowid
        return self.get_thread(int(thread_id))  # type: ignore[arg-type, return-value]

    def get_thread(self, thread_id: int) -> dict[str, Any] | None:
        with self.connection() as connection:
            row = connection.execute(
                """SELECT t.*, c.name AS character_name, c.avatar_url
                   FROM threads t JOIN characters c ON c.id = t.character_id
                   WHERE t.id = ?""",
                (thread_id,),
            ).fetchone()
        return dict(row) if row else None

    def get_or_create_thread(self, character_id: int) -> dict[str, Any]:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT id FROM threads WHERE character_id = ? ORDER BY updated_at DESC LIMIT 1",
                (character_id,),
            ).fetchone()
        if row:
            return self.get_thread(row["id"])  # type: ignore[return-value]
        return self.create_thread(character_id)

    def list_threads(self, character_id: int | None = None) -> list[dict[str, Any]]:
        where = "WHERE t.character_id = ?" if character_id is not None else ""
        params: tuple[Any, ...] = (character_id,) if character_id is not None else ()
        with self.connection() as connection:
            rows = connection.execute(
                f"""SELECT t.*, c.name AS character_name, c.avatar_url,
                       (SELECT content FROM messages m WHERE m.thread_id = t.id
                        ORDER BY m.timestamp DESC LIMIT 1) AS last_message,
                       (SELECT timestamp FROM messages m WHERE m.thread_id = t.id
                        ORDER BY m.timestamp DESC LIMIT 1) AS last_message_at
                    FROM threads t JOIN characters c ON c.id = t.character_id
                    {where}
                    ORDER BY COALESCE(last_message_at, t.updated_at) DESC""",
                params,
            ).fetchall()
        return [dict(row) for row in rows]

    def add_message(
        self,
        thread_id: int,
        character_id: int,
        sender: str,
        content: str,
        *,
        backend: str = "",
        model: str = "",
        prompt_context_summary: str = "",
        character_rationale: str = "",
        initiated: bool = False,
        timestamp: datetime | None = None,
    ) -> dict[str, Any]:
        message_time = iso(timestamp)
        with self.connection() as connection:
            cursor = connection.execute(
                """INSERT INTO messages(
                    thread_id, character_id, sender, content, timestamp, backend, model,
                    prompt_context_summary, character_rationale, initiated
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    thread_id,
                    character_id,
                    sender,
                    content,
                    message_time,
                    backend,
                    model,
                    prompt_context_summary,
                    character_rationale,
                    int(initiated),
                ),
            )
            connection.execute("UPDATE threads SET updated_at = ? WHERE id = ?", (message_time, thread_id))
            message_id = cursor.lastrowid
            row = connection.execute("SELECT * FROM messages WHERE id = ?", (message_id,)).fetchone()
        result = dict(row)
        result["initiated"] = bool(result["initiated"])
        return result

    def list_messages(self, thread_id: int, limit: int = 200) -> list[dict[str, Any]]:
        with self.connection() as connection:
            rows = connection.execute(
                """SELECT * FROM (
                       SELECT * FROM messages WHERE thread_id = ?
                       ORDER BY timestamp DESC LIMIT ?
                   ) ORDER BY timestamp ASC""",
                (thread_id, limit),
            ).fetchall()
        messages = [dict(row) for row in rows]
        for message in messages:
            message["initiated"] = bool(message["initiated"])
        return messages

    def latest_message_time(self, character_id: int) -> datetime | None:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT timestamp FROM messages WHERE character_id = ? ORDER BY timestamp DESC LIMIT 1",
                (character_id,),
            ).fetchone()
        return datetime.fromisoformat(row["timestamp"]) if row else None

    def count_initiated_since(self, since: datetime, character_id: int | None = None) -> int:
        clause = "AND character_id = ?" if character_id is not None else ""
        params: tuple[Any, ...] = (iso(since), character_id) if character_id is not None else (iso(since),)
        with self.connection() as connection:
            return int(
                connection.execute(
                    f"SELECT COUNT(*) FROM messages WHERE initiated = 1 AND timestamp >= ? {clause}",
                    params,
                ).fetchone()[0]
            )

    def get_settings(self) -> dict[str, Any]:
        with self.connection() as connection:
            rows = connection.execute("SELECT section, value_json FROM app_settings").fetchall()
        return {row["section"]: json.loads(row["value_json"]) for row in rows}

    def set_setting(self, section: str, value: Any) -> None:
        with self.connection() as connection:
            connection.execute(
                """INSERT INTO app_settings(section, value_json, updated_at) VALUES (?, ?, ?)
                   ON CONFLICT(section) DO UPDATE SET value_json = excluded.value_json,
                   updated_at = excluded.updated_at""",
                (section, json.dumps(value), iso()),
            )

    def log_usage(
        self,
        *,
        provider: str,
        model: str,
        request_kind: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        estimated_cost_usd: float = 0,
        dry_run: bool = False,
        character_id: int | None = None,
    ) -> None:
        with self.connection() as connection:
            connection.execute(
                """INSERT INTO usage_logs(
                    timestamp, provider, model, request_kind, input_tokens, output_tokens,
                    estimated_cost_usd, dry_run, character_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    iso(),
                    provider,
                    model,
                    request_kind,
                    input_tokens,
                    output_tokens,
                    estimated_cost_usd,
                    int(dry_run),
                    character_id,
                ),
            )

    def usage_since(self, since: datetime, request_kind: str | None = None) -> dict[str, float]:
        clause = "AND request_kind = ?" if request_kind else ""
        params: tuple[Any, ...] = (iso(since), request_kind) if request_kind else (iso(since),)
        with self.connection() as connection:
            row = connection.execute(
                f"""SELECT COUNT(*) AS requests,
                           COALESCE(SUM(input_tokens + output_tokens), 0) AS tokens,
                           COALESCE(SUM(estimated_cost_usd), 0) AS cost
                    FROM usage_logs WHERE timestamp >= ? {clause}""",
                params,
            ).fetchone()
        return {"requests": float(row["requests"]), "tokens": float(row["tokens"]), "cost": float(row["cost"])}

    def search_logs(
        self,
        *,
        character_id: int | None = None,
        keyword: str = "",
        date_from: str = "",
        date_to: str = "",
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if character_id is not None:
            clauses.append("m.character_id = ?")
            params.append(character_id)
        if keyword:
            clauses.append("m.content LIKE ?")
            params.append(f"%{keyword}%")
        if date_from:
            clauses.append("m.timestamp >= ?")
            params.append(date_from)
        if date_to:
            clauses.append("m.timestamp <= ?")
            params.append(f"{date_to}T23:59:59.999999+00:00" if "T" not in date_to else date_to)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        with self.connection() as connection:
            rows = connection.execute(
                f"""SELECT m.*, c.name AS character_name, t.title AS thread_title
                    FROM messages m
                    JOIN characters c ON c.id = m.character_id
                    JOIN threads t ON t.id = m.thread_id
                    {where}
                    ORDER BY m.timestamp DESC LIMIT ?""",
                tuple(params),
            ).fetchall()
        results = [dict(row) for row in rows]
        for result in results:
            result["initiated"] = bool(result["initiated"])
        return results

    def save_subscription(self, subscription: dict[str, Any]) -> None:
        endpoint = subscription.get("endpoint", "")
        if not endpoint:
            raise ValueError("Push subscription is missing an endpoint")
        with self.connection() as connection:
            connection.execute(
                """INSERT INTO push_subscriptions(endpoint, subscription_json, created_at)
                   VALUES (?, ?, ?)
                   ON CONFLICT(endpoint) DO UPDATE SET subscription_json = excluded.subscription_json""",
                (endpoint, json.dumps(subscription), iso()),
            )

    def list_subscriptions(self) -> list[dict[str, Any]]:
        with self.connection() as connection:
            rows = connection.execute("SELECT subscription_json FROM push_subscriptions").fetchall()
        return [json.loads(row["subscription_json"]) for row in rows]

    def delete_subscription(self, endpoint: str) -> None:
        with self.connection() as connection:
            connection.execute("DELETE FROM push_subscriptions WHERE endpoint = ?", (endpoint,))

    def get_daemon_state(self, character_id: int) -> dict[str, Any]:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT * FROM daemon_state WHERE character_id = ?", (character_id,)
            ).fetchone()
        return dict(row) if row else {
            "character_id": character_id,
            "last_checked_at": None,
            "last_initiated_at": None,
            "last_decision_note": "",
        }

    def set_daemon_state(
        self,
        character_id: int,
        *,
        checked_at: datetime,
        initiated_at: datetime | None,
        note: str,
    ) -> None:
        current = self.get_daemon_state(character_id)
        last_initiated = iso(initiated_at) if initiated_at else current.get("last_initiated_at")
        with self.connection() as connection:
            connection.execute(
                """INSERT INTO daemon_state(character_id, last_checked_at, last_initiated_at, last_decision_note)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(character_id) DO UPDATE SET
                     last_checked_at = excluded.last_checked_at,
                     last_initiated_at = excluded.last_initiated_at,
                     last_decision_note = excluded.last_decision_note""",
                (character_id, iso(checked_at), last_initiated, note),
            )

