from __future__ import annotations

_user_id: str | None = None
_session_id: str | None = None
_project_root: str | None = None


def set_session(
    user_id: str,
    session_id: str,
    project_root: str | None = None,
) -> None:
    global _user_id, _session_id, _project_root
    _user_id = user_id
    _session_id = session_id
    _project_root = project_root


def clear_session() -> None:
    global _user_id, _session_id, _project_root
    _user_id = None
    _session_id = None
    _project_root = None


def current_user_id() -> str | None:
    return _user_id


def current_session_id() -> str | None:
    return _session_id


def current_project_root() -> str | None:
    return _project_root
