"""
Session context management using contextvars for async safety.

SECURITY FIX: Previously used module-level globals which caused race conditions
when multiple concurrent requests could interleave and overwrite each other's
session context mid-tool-call. This could cause one user's file/terminal
operations to execute against another user's project directory.

Now uses contextvars.ContextVar which provides proper coroutine-local storage,
ensuring each async request maintains its own isolated session context.
"""

from __future__ import annotations

from contextvars import ContextVar, Token
from dataclasses import dataclass
from typing import Any


@dataclass
class SessionContext:
    """Immutable session context data."""

    user_id: str | None = None
    session_id: str | None = None
    project_root: str | None = None


# ContextVar provides coroutine-local storage - safe for concurrent async requests
_session_context: ContextVar[SessionContext] = ContextVar(
    "session_context", default=SessionContext()
)


class SessionContextManager:
    """
    Context manager for setting session context within a scope.

    Usage:
        async with session_context_scope(user_id="u1", session_id="s1", project_root="/path"):
            # All calls to current_user_id(), etc. return the scoped values
            result = await some_tool.execute()
        # Context automatically cleared after scope exits
    """

    def __init__(
        self,
        user_id: str,
        session_id: str,
        project_root: str | None = None,
    ):
        self._context = SessionContext(
            user_id=user_id,
            session_id=session_id,
            project_root=project_root,
        )
        self._token: Token[SessionContext] | None = None

    def __enter__(self) -> SessionContextManager:
        self._token = _session_context.set(self._context)
        return self

    def __exit__(self, *args: Any) -> None:
        if self._token is not None:
            _session_context.reset(self._token)
            self._token = None

    async def __aenter__(self) -> SessionContextManager:
        return self.__enter__()

    async def __aexit__(self, *args: Any) -> None:
        self.__exit__(*args)


def session_context_scope(
    user_id: str,
    session_id: str,
    project_root: str | None = None,
) -> SessionContextManager:
    """
    Create a context manager scope for session context.

    Preferred over set_session/clear_session for proper cleanup.

    Example:
        async with session_context_scope(user_id, session_id, project_root):
            await tool.execute()
    """
    return SessionContextManager(user_id, session_id, project_root)


def set_session(
    user_id: str,
    session_id: str,
    project_root: str | None = None,
) -> Token[SessionContext]:
    """
    Set the current session context.

    Returns a token that can be used to reset the context.
    Prefer using session_context_scope() for automatic cleanup.

    IMPORTANT: Call clear_session() or reset with the returned token
    when done to avoid context leaking between requests.
    """
    context = SessionContext(
        user_id=user_id,
        session_id=session_id,
        project_root=project_root,
    )
    return _session_context.set(context)


def clear_session(token: Token[SessionContext] | None = None) -> None:
    """
    Clear/reset the current session context.

    Args:
        token: If provided, reset to the state before the corresponding set_session().
               If None, reset to the default (empty) context.
    """
    if token is not None:
        _session_context.reset(token)
    else:
        _session_context.set(SessionContext())


def current_user_id() -> str | None:
    """Get the current user ID from context."""
    return _session_context.get().user_id


def current_session_id() -> str | None:
    """Get the current session ID from context."""
    return _session_context.get().session_id


def current_project_root() -> str | None:
    """Get the current project root from context."""
    return _session_context.get().project_root


def get_session_context() -> SessionContext:
    """Get the full current session context object."""
    return _session_context.get()
