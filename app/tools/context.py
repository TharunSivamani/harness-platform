from __future__ import annotations

_user_id: str | None = None
_session_id: str | None = None


def set_session(user_id: str, session_id: str) -> None:
    global _user_id, _session_id
    _user_id = user_id
    _session_id = session_id


def clear_session() -> None:
    global _user_id, _session_id
    _user_id = None
    _session_id = None


def current_user_id() -> str | None:
    return _user_id


def current_session_id() -> str | None:
    return _session_id
