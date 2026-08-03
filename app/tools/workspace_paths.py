from __future__ import annotations

from pathlib import Path

from app.core.config import settings
from app.storage.paths import paths
from app.tools import context as tool_context


def session_workspace() -> Path:
    user_id = tool_context.current_user_id() or settings.DEFAULT_USER_ID
    session_id = tool_context.current_session_id()
    if session_id:
        return paths.workspace_path(user_id, session_id)
    fallback = settings.forge_home / "workspace"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


def resolve_in_workspace(relative: str = ".") -> Path:
    root = session_workspace().resolve()
    candidate = (root / relative).resolve()
    if not candidate.is_relative_to(root):
        raise ValueError(f"Path '{relative}' escapes session workspace.")
    return candidate
