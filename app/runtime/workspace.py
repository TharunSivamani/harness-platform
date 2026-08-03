from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.core.config import settings


@dataclass
class Workspace:
    workspace_id: str
    path: Path
    session_id: str | None = None
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    metadata: dict[str, Any] = field(default_factory=dict)


class WorkspaceManager:
    """
    Isolated per-session filesystem workspaces.
    """

    def __init__(self, root: str | Path | None = None):
        self.root = Path(root or settings.WORKSPACE_ROOT).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self._workspaces: dict[str, Workspace] = {}

    def create(self, session_id: str | None = None, metadata: dict | None = None) -> Workspace:
        workspace_id = session_id or str(uuid4())
        path = self.root / f"session_{workspace_id}"
        for sub in ("code", "data", "images", "logs", "artifacts"):
            (path / sub).mkdir(parents=True, exist_ok=True)

        workspace = Workspace(
            workspace_id=workspace_id,
            path=path,
            session_id=session_id,
            metadata=metadata or {},
        )
        self._workspaces[workspace_id] = workspace
        return workspace

    def get(self, workspace_id: str) -> Workspace:
        if workspace_id in self._workspaces:
            return self._workspaces[workspace_id]
        path = self.root / f"session_{workspace_id}"
        if not path.exists():
            raise KeyError(f"Workspace '{workspace_id}' not found.")
        workspace = Workspace(workspace_id=workspace_id, path=path, session_id=workspace_id)
        self._workspaces[workspace_id] = workspace
        return workspace

    def get_or_create(self, workspace_id: str | None = None) -> Workspace:
        if workspace_id:
            try:
                return self.get(workspace_id)
            except KeyError:
                return self.create(session_id=workspace_id)
        return self.create()

    def resolve(self, workspace_id: str, relative: str = ".") -> Path:
        workspace = self.get(workspace_id)
        candidate = (workspace.path / relative).resolve()
        if not candidate.is_relative_to(workspace.path.resolve()):
            raise ValueError("Path escapes workspace boundary.")
        return candidate

    def size_bytes(self, workspace_id: str) -> int:
        workspace = self.get(workspace_id)
        return sum(path.stat().st_size for path in workspace.path.rglob("*") if path.is_file())

    def enforce_quota(self, workspace_id: str) -> None:
        size = self.size_bytes(workspace_id)
        if size > settings.MAX_WORKSPACE_BYTES:
            raise RuntimeError(
                f"Workspace quota exceeded ({size} > {settings.MAX_WORKSPACE_BYTES} bytes)."
            )

    def delete(self, workspace_id: str) -> None:
        workspace = self.get(workspace_id)
        shutil.rmtree(workspace.path, ignore_errors=True)
        self._workspaces.pop(workspace_id, None)

    def list_workspaces(self) -> list[str]:
        return sorted(
            {
                *[item.name.replace("session_", "", 1) for item in self.root.glob("session_*")],
                *self._workspaces.keys(),
            }
        )


workspace_manager = WorkspaceManager()
