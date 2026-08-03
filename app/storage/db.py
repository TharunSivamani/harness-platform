from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any

from app.core.config import settings
from app.storage.paths import paths


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Storage:
    """
    Portable SQLite store under FORGE_HOME/forge.db.
    """

    def __init__(self):
        self.path = paths.db_path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self.ensure_default_user()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'owner',
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    model TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES users(user_id)
                );

                CREATE TABLE IF NOT EXISTS messages (
                    message_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    metadata TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(session_id) REFERENCES sessions(session_id)
                );

                CREATE TABLE IF NOT EXISTS token_usage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    message_id TEXT,
                    prompt_tokens INTEGER NOT NULL DEFAULT 0,
                    completion_tokens INTEGER NOT NULL DEFAULT 0,
                    total_tokens INTEGER NOT NULL DEFAULT 0,
                    model TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS kv (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    action TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
                """
            )

    def ensure_default_user(self) -> dict[str, Any]:
        user = self.get_user(settings.DEFAULT_USER_ID)
        if user:
            return user
        return self.create_user(
            user_id=settings.DEFAULT_USER_ID,
            name=settings.DEFAULT_USER_NAME,
            role=settings.DEFAULT_ROLE,
        )

    def create_user(
        self,
        *,
        name: str,
        role: str = "member",
        user_id: str | None = None,
    ) -> dict[str, Any]:
        user_id = user_id or paths.new_id()
        created = _now()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO users(user_id, name, role, created_at) VALUES (?, ?, ?, ?)",
                (user_id, name, role, created),
            )
        profile = {
            "user_id": user_id,
            "name": name,
            "role": role,
            "created_at": created,
        }
        paths.write_json(paths.user_profile_path(user_id), profile)
        return profile

    def get_user(self, user_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE user_id = ?",
                (user_id,),
            ).fetchone()
        return dict(row) if row else None

    def list_users(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM users ORDER BY created_at").fetchall()
        return [dict(row) for row in rows]

    def create_session(
        self,
        user_id: str,
        title: str = "New chat",
        model: str | None = None,
    ) -> dict[str, Any]:
        session_id = paths.new_id()
        now = _now()
        model = model or settings.MODEL_NAME
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO sessions(session_id, user_id, title, model, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (session_id, user_id, title, model, now, now),
            )
        meta = {
            "session_id": session_id,
            "user_id": user_id,
            "title": title,
            "model": model,
            "created_at": now,
            "updated_at": now,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }
        paths.write_json(paths.meta_path(user_id, session_id), meta)
        paths.session_dir(user_id, session_id)
        return meta

    def list_sessions(self, user_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM sessions
                WHERE user_id = ?
                ORDER BY updated_at DESC
                """,
                (user_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        return dict(row) if row else None

    def touch_session(self, session_id: str, title: str | None = None) -> None:
        now = _now()
        with self._connect() as conn:
            if title:
                conn.execute(
                    "UPDATE sessions SET updated_at = ?, title = ? WHERE session_id = ?",
                    (now, title, session_id),
                )
            else:
                conn.execute(
                    "UPDATE sessions SET updated_at = ? WHERE session_id = ?",
                    (now, session_id),
                )
        session = self.get_session(session_id)
        if session:
            meta = paths.read_json(paths.meta_path(session["user_id"], session_id), session)
            meta["updated_at"] = now
            if title:
                meta["title"] = title
            paths.write_json(paths.meta_path(session["user_id"], session_id), meta)

    def add_message(
        self,
        *,
        session_id: str,
        user_id: str,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
        message_id: str | None = None,
    ) -> dict[str, Any]:
        message_id = message_id or paths.new_id()
        created = _now()
        meta = metadata or {}
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO messages(message_id, session_id, user_id, role, content, metadata, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    message_id,
                    session_id,
                    user_id,
                    role,
                    content,
                    json.dumps(meta),
                    created,
                ),
            )
        row = {
            "message_id": message_id,
            "session_id": session_id,
            "user_id": user_id,
            "role": role,
            "content": content,
            "metadata": meta,
            "created_at": created,
        }
        paths.append_jsonl(paths.messages_path(user_id, session_id), row)
        self.touch_session(session_id)
        return row

    def list_messages(self, session_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM messages
                WHERE session_id = ?
                ORDER BY created_at ASC
                """,
                (session_id,),
            ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["metadata"] = json.loads(item["metadata"] or "{}")
            result.append(item)
        return result

    def record_tokens(
        self,
        *,
        user_id: str,
        session_id: str,
        prompt_tokens: int,
        completion_tokens: int,
        model: str | None = None,
        message_id: str | None = None,
    ) -> dict[str, int]:
        total = prompt_tokens + completion_tokens
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO token_usage(
                    user_id, session_id, message_id,
                    prompt_tokens, completion_tokens, total_tokens, model, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    session_id,
                    message_id,
                    prompt_tokens,
                    completion_tokens,
                    total,
                    model or settings.MODEL_NAME,
                    _now(),
                ),
            )
        meta_path = paths.meta_path(user_id, session_id)
        meta = paths.read_json(meta_path, {})
        meta["prompt_tokens"] = int(meta.get("prompt_tokens", 0)) + prompt_tokens
        meta["completion_tokens"] = int(meta.get("completion_tokens", 0)) + completion_tokens
        meta["total_tokens"] = int(meta.get("total_tokens", 0)) + total
        paths.write_json(meta_path, meta)
        return {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total,
        }

    def session_stats(self, session_id: str) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT
                    COALESCE(SUM(prompt_tokens), 0) AS prompt_tokens,
                    COALESCE(SUM(completion_tokens), 0) AS completion_tokens,
                    COALESCE(SUM(total_tokens), 0) AS total_tokens,
                    COUNT(*) AS events
                FROM token_usage
                WHERE session_id = ?
                """,
                (session_id,),
            ).fetchone()
            msg_count = conn.execute(
                "SELECT COUNT(*) AS c FROM messages WHERE session_id = ?",
                (session_id,),
            ).fetchone()["c"]
        return {
            "session_id": session_id,
            "prompt_tokens": row["prompt_tokens"],
            "completion_tokens": row["completion_tokens"],
            "total_tokens": row["total_tokens"],
            "token_events": row["events"],
            "message_count": msg_count,
        }

    def user_stats(self, user_id: str) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT
                    COALESCE(SUM(prompt_tokens), 0) AS prompt_tokens,
                    COALESCE(SUM(completion_tokens), 0) AS completion_tokens,
                    COALESCE(SUM(total_tokens), 0) AS total_tokens
                FROM token_usage
                WHERE user_id = ?
                """,
                (user_id,),
            ).fetchone()
            sessions = conn.execute(
                "SELECT COUNT(*) AS c FROM sessions WHERE user_id = ?",
                (user_id,),
            ).fetchone()["c"]
            messages = conn.execute(
                "SELECT COUNT(*) AS c FROM messages WHERE user_id = ?",
                (user_id,),
            ).fetchone()["c"]
        return {
            "user_id": user_id,
            "prompt_tokens": row["prompt_tokens"],
            "completion_tokens": row["completion_tokens"],
            "total_tokens": row["total_tokens"],
            "session_count": sessions,
            "message_count": messages,
        }

    def set(self, key: str, value: Any) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO kv(key, value) VALUES (?, ?)",
                (key, json.dumps(value)),
            )

    def get(self, key: str, default: Any = None) -> Any:
        with self._connect() as conn:
            row = conn.execute("SELECT value FROM kv WHERE key = ?", (key,)).fetchone()
        if row is None:
            return default
        return json.loads(row["value"])

    def audit(self, action: str, payload: dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO audit_log(action, payload) VALUES (?, ?)",
                (action, json.dumps(payload)),
            )


storage = Storage()
