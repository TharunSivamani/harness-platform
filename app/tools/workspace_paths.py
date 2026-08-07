from __future__ import annotations

from pathlib import Path

from app.core.config import settings
from app.storage.paths import paths
from app.tools import context as tool_context


def session_scratch_workspace() -> Path:
    """FORGE_HOME per-session scratch folder (uploads mirror, legacy fallback)."""
    user_id = tool_context.current_user_id() or settings.DEFAULT_USER_ID
    session_id = tool_context.current_session_id()
    if session_id:
        return paths.workspace_path(user_id, session_id)
    fallback = settings.forge_home / "workspace"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


def resolve_project_root(raw: str | Path | None) -> Path | None:
    if not raw:
        return None
    root = Path(raw).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        raise ValueError(f"Project root does not exist or is not a directory: {root}")
    return root


def session_workspace() -> Path:
    """
    Active code root for tools.

    Prefer an explicit project_root (OpenCode / Hermes cwd) when set on the
    session or tool context; otherwise fall back to the FORGE_HOME session
    scratch workspace.
    """
    explicit = tool_context.current_project_root()
    if explicit:
        root = Path(explicit).expanduser().resolve()
        if root.exists() and root.is_dir():
            return root

    user_id = tool_context.current_user_id() or settings.DEFAULT_USER_ID
    session_id = tool_context.current_session_id()
    if session_id:
        from app.storage.db import storage

        session = storage.get_session(session_id)
        if session and session.get("user_id") == user_id:
            stored = session.get("project_root")
            if stored:
                root = Path(stored).expanduser().resolve()
                if root.exists() and root.is_dir():
                    return root
            meta = paths.read_json(paths.meta_path(user_id, session_id), {})
            stored = meta.get("project_root")
            if stored:
                root = Path(stored).expanduser().resolve()
                if root.exists() and root.is_dir():
                    return root

    return session_scratch_workspace()


def resolve_in_workspace(relative: str = ".") -> Path:
    root = session_workspace().resolve()
    candidate = (root / relative).resolve()
    if not candidate.is_relative_to(root):
        raise ValueError(f"Path '{relative}' escapes project/workspace root.")
    return candidate
