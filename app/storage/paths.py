from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.core.config import settings


class ForgePaths:
    """
    Portable FORGE_HOME layout.

    data/
      forge.db
      users/<user_id>/profile.json
      users/<user_id>/sessions/<session_id>/...
    """

    def __init__(self, root: Path | None = None):
        self.root = Path(root or settings.forge_home).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "users").mkdir(exist_ok=True)
        (self.root / "export").mkdir(exist_ok=True)

    @property
    def db_path(self) -> Path:
        return self.root / "forge.db"

    def user_dir(self, user_id: str) -> Path:
        path = self.root / "users" / user_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def user_profile_path(self, user_id: str) -> Path:
        return self.user_dir(user_id) / "profile.json"

    def session_dir(self, user_id: str, session_id: str) -> Path:
        path = self.user_dir(user_id) / "sessions" / session_id
        for sub in ("uploads", "artifacts", "workspace"):
            (path / sub).mkdir(parents=True, exist_ok=True)
        return path

    def messages_path(self, user_id: str, session_id: str) -> Path:
        return self.session_dir(user_id, session_id) / "messages.jsonl"

    def meta_path(self, user_id: str, session_id: str) -> Path:
        return self.session_dir(user_id, session_id) / "meta.json"

    def workspace_path(self, user_id: str, session_id: str) -> Path:
        return self.session_dir(user_id, session_id) / "workspace"

    def uploads_path(self, user_id: str, session_id: str) -> Path:
        return self.session_dir(user_id, session_id) / "uploads"

    def artifacts_path(self, user_id: str, session_id: str) -> Path:
        return self.session_dir(user_id, session_id) / "artifacts"

    def write_json(self, path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def read_json(self, path: Path, default: dict[str, Any] | None = None) -> dict[str, Any]:
        if not path.exists():
            return default or {}
        return json.loads(path.read_text(encoding="utf-8"))

    def append_jsonl(self, path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, default=str) + "\n")

    def read_jsonl(self, path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        rows: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
        return rows

    def new_id(self) -> str:
        return str(uuid4())


paths = ForgePaths()
