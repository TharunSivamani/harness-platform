from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from app.core.config import settings


class Storage:
    """
    SQLite-backed key/value and audit storage for development.
    """

    def __init__(self, url: str | None = None):
        raw = url or settings.DATABASE_URL
        if raw.startswith("sqlite:///"):
            path = Path(raw.replace("sqlite:///", "", 1))
        else:
            path = Path("./forgeai.db")
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS kv (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    action TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

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
