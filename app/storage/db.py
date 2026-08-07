from __future__ import annotations

import json
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
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
                    project_root TEXT,
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
            cols = {
                row[1]
                for row in conn.execute("PRAGMA table_info(sessions)").fetchall()
            }
            if "project_root" not in cols:
                conn.execute("ALTER TABLE sessions ADD COLUMN project_root TEXT")

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
        project_root: str | None = None,
    ) -> dict[str, Any]:
        session_id = paths.new_id()
        now = _now()
        model = model or settings.MODEL_NAME
        root = None
        if project_root:
            resolved = Path(project_root).expanduser().resolve()
            if not resolved.exists() or not resolved.is_dir():
                raise ValueError(f"Invalid project_root: {resolved}")
            root = str(resolved)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO sessions(
                    session_id, user_id, title, model, project_root, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (session_id, user_id, title, model, root, now, now),
            )
        meta = {
            "session_id": session_id,
            "user_id": user_id,
            "title": title,
            "model": model,
            "project_root": root,
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
        return [self._hydrate_session(dict(row)) for row in rows]

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        return self._hydrate_session(dict(row)) if row else None

    def _hydrate_session(self, session: dict[str, Any]) -> dict[str, Any]:
        """Merge meta.json project_root when column is empty (older sessions)."""
        if session.get("project_root"):
            return session
        meta = paths.read_json(
            paths.meta_path(session["user_id"], session["session_id"]),
            {},
        )
        if meta.get("project_root"):
            session["project_root"] = meta["project_root"]
        return session

    def set_project_root(self, session_id: str, user_id: str, project_root: str | None) -> dict[str, Any]:
        session = self.get_session(session_id)
        if not session or session["user_id"] != user_id:
            raise KeyError(f"Session '{session_id}' not found for user.")
        root = None
        if project_root:
            resolved = Path(project_root).expanduser().resolve()
            if not resolved.exists() or not resolved.is_dir():
                raise ValueError(f"Invalid project_root: {resolved}")
            root = str(resolved)
        now = _now()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE sessions
                SET project_root = ?, updated_at = ?
                WHERE session_id = ? AND user_id = ?
                """,
                (root, now, session_id, user_id),
            )
        meta = paths.read_json(paths.meta_path(user_id, session_id), session)
        meta["project_root"] = root
        meta["updated_at"] = now
        paths.write_json(paths.meta_path(user_id, session_id), meta)
        self.audit(
            "session.project_root",
            {"session_id": session_id, "user_id": user_id, "project_root": root},
        )
        updated = self.get_session(session_id)
        assert updated is not None
        return updated

    def _preserve_session_artifacts(
        self,
        user_id: str,
        session_id: str,
        session_title: str,
    ) -> int:
        """Move session artifacts aside so they survive chat/session deletion."""
        source = paths.artifacts_path(user_id, session_id)
        if not source.exists():
            return 0
        files = [item for item in source.iterdir() if item.is_file()]
        if not files:
            return 0

        dest = paths.retained_artifacts_session_dir(user_id, session_id)
        meta_path = dest / "_meta.json"
        meta = paths.read_json(
            meta_path,
            {
                "session_id": session_id,
                "session_title": session_title,
                "retained_at": _now(),
            },
        )
        meta["session_title"] = session_title or meta.get("session_title") or "Deleted chat"
        meta["retained_at"] = _now()
        paths.write_json(meta_path, meta)

        moved = 0
        for file_path in files:
            target = dest / file_path.name
            if target.exists():
                stem = file_path.stem
                suffix = file_path.suffix
                target = dest / f"{stem}-{paths.new_id()[:8]}{suffix}"
            shutil.move(str(file_path), str(target))
            moved += 1
        return moved

    def delete_session(
        self,
        session_id: str,
        user_id: str,
        *,
        keep_artifacts: bool = True,
    ) -> bool:
        session = self.get_session(session_id)
        if not session or session["user_id"] != user_id:
            return False

        retained = 0
        if keep_artifacts:
            retained = self._preserve_session_artifacts(
                user_id,
                session_id,
                session.get("title") or "Deleted chat",
            )

        with self._connect() as conn:
            conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
            conn.execute("DELETE FROM token_usage WHERE session_id = ?", (session_id,))
            conn.execute(
                "DELETE FROM sessions WHERE session_id = ? AND user_id = ?",
                (session_id, user_id),
            )
        session_path = paths.user_dir(user_id) / "sessions" / session_id
        if session_path.exists():
            shutil.rmtree(session_path, ignore_errors=True)
        self.audit(
            "session.deleted",
            {
                "session_id": session_id,
                "user_id": user_id,
                "keep_artifacts": keep_artifacts,
                "artifacts_retained": retained,
            },
        )
        return True

    def delete_all_sessions(
        self,
        user_id: str,
        *,
        keep_artifacts: bool = True,
    ) -> dict[str, Any]:
        sessions = self.list_sessions(user_id)
        deleted = 0
        artifacts_retained = 0
        for session in sessions:
            session_id = session["session_id"]
            if keep_artifacts:
                artifacts_retained += self._preserve_session_artifacts(
                    user_id,
                    session_id,
                    session.get("title") or "Deleted chat",
                )
            # Artifacts already moved above; skip a second preserve pass.
            if self.delete_session(session_id, user_id, keep_artifacts=False):
                deleted += 1
        self.audit(
            "sessions.cleared",
            {
                "user_id": user_id,
                "deleted": deleted,
                "keep_artifacts": keep_artifacts,
                "artifacts_retained": artifacts_retained,
            },
        )
        return {
            "deleted": deleted,
            "keep_artifacts": keep_artifacts,
            "artifacts_retained": artifacts_retained,
        }

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

    def update_message_metadata(
        self,
        message_id: str,
        metadata: dict[str, Any],
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE messages SET metadata = ? WHERE message_id = ?",
                (json.dumps(metadata), message_id),
            )

    def _folder_for_kind(self, user_id: str, session_id: str, kind: str) -> Path | None:
        mapping = {
            "upload": paths.uploads_path,
            "uploads": paths.uploads_path,
            "artifact": paths.artifacts_path,
            "artifacts": paths.artifacts_path,
            "workspace": paths.workspace_path,
        }
        fn = mapping.get(kind)
        return fn(user_id, session_id) if fn else None

    def list_user_files(self, user_id: str) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for session in self.list_sessions(user_id):
            session_id = session["session_id"]
            for kind in ("upload", "artifact", "workspace"):
                folder = self._folder_for_kind(user_id, session_id, kind)
                if folder is None or not folder.exists():
                    continue
                for file_path in folder.iterdir():
                    if not file_path.is_file():
                        continue
                    stat = file_path.stat()
                    items.append(
                        {
                            "session_id": session_id,
                            "session_title": session["title"],
                            "kind": kind,
                            "name": file_path.name,
                            "size": stat.st_size,
                            "modified_at": datetime.fromtimestamp(
                                stat.st_mtime, tz=timezone.utc
                            ).isoformat(),
                            "url": f"/sessions/{session_id}/files/{kind}/{file_path.name}",
                            "retained": False,
                        }
                    )

        retained_root = paths.retained_artifacts_dir(user_id)
        if retained_root.exists():
            for session_dir in retained_root.iterdir():
                if not session_dir.is_dir():
                    continue
                meta = paths.read_json(session_dir / "_meta.json", {})
                title = meta.get("session_title") or "Deleted chat"
                for file_path in session_dir.iterdir():
                    if not file_path.is_file() or file_path.name == "_meta.json":
                        continue
                    stat = file_path.stat()
                    items.append(
                        {
                            "session_id": session_dir.name,
                            "session_title": title,
                            "kind": "artifact",
                            "name": file_path.name,
                            "size": stat.st_size,
                            "modified_at": datetime.fromtimestamp(
                                stat.st_mtime, tz=timezone.utc
                            ).isoformat(),
                            "url": (
                                f"/retained-artifacts/{session_dir.name}/"
                                f"{file_path.name}"
                            ),
                            "retained": True,
                        }
                    )

        items.sort(key=lambda row: row["modified_at"], reverse=True)
        return items

    def delete_retained_artifact(
        self,
        *,
        user_id: str,
        session_id: str,
        filename: str,
    ) -> dict[str, Any] | None:
        folder = paths.retained_artifacts_session_dir(user_id, session_id)
        name = Path(filename).name
        if name == "_meta.json":
            return None
        target = (folder / name).resolve()
        if not target.is_relative_to(folder.resolve()) or not target.exists():
            return None
        target.unlink(missing_ok=True)
        payload = {
            "session_id": session_id,
            "kind": "artifact",
            "name": name,
            "retained": True,
            "deleted_at": _now(),
        }
        self.audit("retained_artifact.deleted", {"user_id": user_id, **payload})
        return payload

    def delete_session_file(
        self,
        *,
        user_id: str,
        session_id: str,
        kind: str,
        filename: str,
    ) -> dict[str, Any] | None:
        session = self.get_session(session_id)
        if not session or session["user_id"] != user_id:
            return None
        name = Path(filename).name
        folder = self._folder_for_kind(user_id, session_id, kind)
        if folder is None:
            return None
        target = (folder / name).resolve()
        if not target.is_relative_to(folder.resolve()) or not target.exists():
            return None

        target.unlink(missing_ok=True)
        # Uploads are mirrored into workspace — remove the twin if present.
        if kind in {"upload", "uploads"}:
            twin = paths.workspace_path(user_id, session_id) / name
            if twin.exists() and twin.is_file():
                twin.unlink(missing_ok=True)

        deleted_at = _now()
        touched = 0
        for message in self.list_messages(session_id):
            meta = dict(message.get("metadata") or {})
            attachments = meta.get("attachments")
            if not isinstance(attachments, list):
                continue
            changed = False
            for attachment in attachments:
                if attachment.get("name") != name:
                    continue
                attachment["missing"] = True
                attachment["deleted_at"] = deleted_at
                changed = True
            if changed:
                meta["attachments"] = attachments
                self.update_message_metadata(message["message_id"], meta)
                touched += 1

        normalized_kind = {
            "uploads": "upload",
            "artifacts": "artifact",
        }.get(kind, kind)
        payload = {
            "session_id": session_id,
            "kind": normalized_kind,
            "name": name,
            "messages_updated": touched,
            "deleted_at": deleted_at,
        }
        self.audit("file.deleted", {"user_id": user_id, **payload})
        return payload

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
