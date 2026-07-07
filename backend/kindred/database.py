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
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    title TEXT NOT NULL DEFAULT 'Conversation',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    thread_id INTEGER NOT NULL REFERENCES threads(id) ON DELETE CASCADE,
    character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
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
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
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
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL DEFAULT '',
    password_hash TEXT NOT NULL,
    disabled INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS user_character_access (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    PRIMARY KEY(user_id, character_id)
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
_ANY = object()


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
            self._migrate(connection)
            now = iso()
            for section, value in defaults.items():
                connection.execute(
                    "INSERT OR IGNORE INTO app_settings(section, value_json, updated_at) VALUES (?, ?, ?)",
                    (section, json.dumps(value), now),
                )

    def _migrate(self, connection: sqlite3.Connection) -> None:
        """Apply tiny additive migrations for existing local databases."""

        table_columns = {
            table: {row["name"] for row in connection.execute(f"PRAGMA table_info({table})").fetchall()}
            for table in ("threads", "messages", "push_subscriptions")
        }
        if "user_id" not in table_columns["threads"]:
            connection.execute(
                "ALTER TABLE threads ADD COLUMN user_id INTEGER REFERENCES users(id) ON DELETE SET NULL"
            )
        if "user_id" not in table_columns["messages"]:
            connection.execute(
                "ALTER TABLE messages ADD COLUMN user_id INTEGER REFERENCES users(id) ON DELETE SET NULL"
            )
        if "user_id" not in table_columns["push_subscriptions"]:
            connection.execute(
                "ALTER TABLE push_subscriptions ADD COLUMN user_id INTEGER REFERENCES users(id) ON DELETE CASCADE"
            )
        connection.execute("CREATE INDEX IF NOT EXISTS idx_threads_user_time ON threads(user_id, updated_at)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_messages_user_time ON messages(user_id, timestamp)")

    def seed_characters(self, characters: Sequence[dict[str, Any]]) -> int:
        """Insert seed characters only when the character table is empty."""

        with self.connection() as connection:
            count = connection.execute("SELECT COUNT(*) FROM characters").fetchone()[0]
        if count:
            return 0
        for character in characters:
            self.create_character(character)
        return len(characters)

    def list_characters(self, user_id: int | None = None, *, include_all: bool = True) -> list[dict[str, Any]]:
        if user_id is not None and not include_all:
            with self.connection() as connection:
                rows = connection.execute(
                    """SELECT c.* FROM characters c
                       JOIN user_character_access a ON a.character_id = c.id
                       WHERE a.user_id = ?
                       ORDER BY c.name COLLATE NOCASE""",
                    (user_id,),
                ).fetchall()
            return [dict(row) for row in rows]
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

    def character_is_allowed(self, user_id: int | None, character_id: int, *, include_all: bool) -> bool:
        """Return whether an identity can access a character."""

        if include_all:
            return self.get_character(character_id) is not None
        if user_id is None:
            return self.get_character(character_id) is not None
        with self.connection() as connection:
            row = connection.execute(
                "SELECT 1 FROM user_character_access WHERE user_id = ? AND character_id = ?",
                (user_id, character_id),
            ).fetchone()
        return row is not None

    def create_thread(
        self,
        character_id: int,
        title: str = "Conversation",
        *,
        user_id: int | None = None,
    ) -> dict[str, Any]:
        now = iso()
        with self.connection() as connection:
            cursor = connection.execute(
                "INSERT INTO threads(character_id, user_id, title, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (character_id, user_id, title, now, now),
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

    def get_or_create_thread(self, character_id: int, user_id: int | None = None) -> dict[str, Any]:
        user_clause = "user_id IS NULL" if user_id is None else "user_id = ?"
        params: tuple[Any, ...] = (character_id,) if user_id is None else (character_id, user_id)
        with self.connection() as connection:
            row = connection.execute(
                f"SELECT id FROM threads WHERE character_id = ? AND {user_clause} ORDER BY updated_at DESC LIMIT 1",
                params,
            ).fetchone()
        if row:
            return self.get_thread(row["id"])  # type: ignore[return-value]
        return self.create_thread(character_id, user_id=user_id)

    def list_threads(
        self,
        character_id: int | None = None,
        *,
        user_id: int | None = None,
        include_all: bool = True,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if character_id is not None:
            clauses.append("t.character_id = ?")
            params.append(character_id)
        if user_id is not None or not include_all:
            if user_id is None:
                clauses.append("t.user_id IS NULL")
            else:
                clauses.append("t.user_id = ?")
                params.append(user_id)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
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
                tuple(params),
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
        user_id: int | None = None,
        timestamp: datetime | None = None,
    ) -> dict[str, Any]:
        message_time = iso(timestamp)
        with self.connection() as connection:
            cursor = connection.execute(
                """INSERT INTO messages(
                    thread_id, character_id, user_id, sender, content, timestamp, backend, model,
                    prompt_context_summary, character_rationale, initiated
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    thread_id,
                    character_id,
                    user_id,
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

    def thread_belongs_to_user(self, thread_id: int, user_id: int | None, *, include_all: bool) -> bool:
        """Return whether a thread is visible to the requesting identity."""

        if include_all:
            return self.get_thread(thread_id) is not None
        thread = self.get_thread(thread_id)
        if not thread:
            return False
        return thread.get("user_id") == user_id

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
        user_id: int | None = None,
        include_all: bool = True,
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
        if user_id is not None or not include_all:
            if user_id is None:
                clauses.append("m.user_id IS NULL")
            else:
                clauses.append("m.user_id = ?")
                params.append(user_id)
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

    def save_subscription(self, subscription: dict[str, Any], user_id: int | None = None) -> None:
        endpoint = subscription.get("endpoint", "")
        if not endpoint:
            raise ValueError("Push subscription is missing an endpoint")
        with self.connection() as connection:
            connection.execute(
                """INSERT INTO push_subscriptions(user_id, endpoint, subscription_json, created_at)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(endpoint) DO UPDATE SET
                     user_id = excluded.user_id,
                     subscription_json = excluded.subscription_json""",
                (user_id, endpoint, json.dumps(subscription), iso()),
            )

    def list_subscriptions(self, user_id: int | None | object = _ANY) -> list[dict[str, Any]]:
        clause = ""
        params: tuple[Any, ...] = ()
        if user_id is not _ANY:
            if user_id is None:
                clause = "WHERE user_id IS NULL"
            else:
                clause = "WHERE user_id = ?"
                params = (user_id,)
        with self.connection() as connection:
            rows = connection.execute(
                f"SELECT subscription_json FROM push_subscriptions {clause}",
                params,
            ).fetchall()
        return [json.loads(row["subscription_json"]) for row in rows]

    def delete_subscription(self, endpoint: str) -> None:
        with self.connection() as connection:
            connection.execute("DELETE FROM push_subscriptions WHERE endpoint = ?", (endpoint,))

    def create_user(
        self,
        *,
        username: str,
        display_name: str,
        password_hash: str,
        disabled: bool = False,
        character_ids: Sequence[int] = (),
    ) -> dict[str, Any]:
        """Create a regular user and grant their initial character access."""

        now = iso()
        with self.connection() as connection:
            cursor = connection.execute(
                """INSERT INTO users(username, display_name, password_hash, disabled, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (username, display_name, password_hash, int(disabled), now, now),
            )
            user_id = int(cursor.lastrowid)
            self._replace_user_access(connection, user_id, character_ids)
        return self.get_user(user_id)  # type: ignore[return-value]

    def get_user(self, user_id: int | None) -> dict[str, Any] | None:
        """Fetch a user without exposing their password hash."""

        if user_id is None:
            return None
        with self.connection() as connection:
            row = connection.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
            access_rows = connection.execute(
                "SELECT character_id FROM user_character_access WHERE user_id = ? ORDER BY character_id",
                (user_id,),
            ).fetchall()
        if not row:
            return None
        result = dict(row)
        result["disabled"] = bool(result["disabled"])
        result["character_ids"] = [int(access["character_id"]) for access in access_rows]
        result.pop("password_hash", None)
        return result

    def get_user_by_username(self, username: str) -> dict[str, Any] | None:
        """Fetch a user by case-insensitive username, including password hash."""

        with self.connection() as connection:
            row = connection.execute(
                "SELECT * FROM users WHERE lower(username) = lower(?)",
                (username,),
            ).fetchone()
            if not row:
                return None
            access_rows = connection.execute(
                "SELECT character_id FROM user_character_access WHERE user_id = ? ORDER BY character_id",
                (row["id"],),
            ).fetchall()
        result = dict(row)
        result["disabled"] = bool(result["disabled"])
        result["character_ids"] = [int(access["character_id"]) for access in access_rows]
        return result

    def list_users(self) -> list[dict[str, Any]]:
        """List regular users with their character grants."""

        with self.connection() as connection:
            rows = connection.execute("SELECT id FROM users ORDER BY username COLLATE NOCASE").fetchall()
        users: list[dict[str, Any]] = []
        for row in rows:
            user = self.get_user(int(row["id"]))
            if user:
                users.append(user)
        return users

    def update_user(
        self,
        user_id: int,
        *,
        username: str | None = None,
        display_name: str | None = None,
        password_hash: str | None = None,
        disabled: bool | None = None,
        character_ids: Sequence[int] | None = None,
    ) -> dict[str, Any] | None:
        """Patch a user and optionally replace their character allow-list."""

        assignments: list[str] = []
        params: list[Any] = []
        for column, value in (
            ("username", username),
            ("display_name", display_name),
            ("password_hash", password_hash),
        ):
            if value is not None:
                assignments.append(f"{column} = ?")
                params.append(value)
        if disabled is not None:
            assignments.append("disabled = ?")
            params.append(int(disabled))
        with self.connection() as connection:
            if assignments:
                assignments.append("updated_at = ?")
                params.extend([iso(), user_id])
                connection.execute(f"UPDATE users SET {', '.join(assignments)} WHERE id = ?", tuple(params))
            if character_ids is not None:
                self._replace_user_access(connection, user_id, character_ids)
        return self.get_user(user_id)

    def delete_user(self, user_id: int) -> bool:
        """Delete a regular user account."""

        with self.connection() as connection:
            cursor = connection.execute("DELETE FROM users WHERE id = ?", (user_id,))
        return cursor.rowcount > 0

    def _replace_user_access(
        self,
        connection: sqlite3.Connection,
        user_id: int,
        character_ids: Sequence[int],
    ) -> None:
        connection.execute("DELETE FROM user_character_access WHERE user_id = ?", (user_id,))
        now = iso()
        for character_id in sorted({int(value) for value in character_ids}):
            connection.execute(
                """INSERT OR IGNORE INTO user_character_access(user_id, character_id, created_at)
                   VALUES (?, ?, ?)""",
                (user_id, character_id, now),
            )

    def daemon_recipient_user_ids(self, character_id: int) -> list[int | None]:
        """Return users who should receive proactive messages for a character."""

        with self.connection() as connection:
            users = connection.execute(
                """SELECT u.id FROM users u
                   JOIN user_character_access a ON a.user_id = u.id
                   WHERE u.disabled = 0 AND a.character_id = ?
                   ORDER BY u.id""",
                (character_id,),
            ).fetchall()
            legacy_thread = connection.execute(
                "SELECT 1 FROM threads WHERE character_id = ? AND user_id IS NULL LIMIT 1",
                (character_id,),
            ).fetchone()
            user_count = connection.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        recipients: list[int | None] = [int(row["id"]) for row in users]
        if legacy_thread or user_count == 0:
            recipients.insert(0, None)
        return recipients

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
