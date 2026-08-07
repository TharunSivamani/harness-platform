"""
Tests for session context management.

These tests verify that the contextvars-based session context
properly isolates concurrent async requests.
"""

import asyncio
import pytest
from app.tools.context import (
    SessionContext,
    SessionContextManager,
    session_context_scope,
    set_session,
    clear_session,
    current_user_id,
    current_session_id,
    current_project_root,
    get_session_context,
)


class TestSessionContext:
    """Test basic context operations."""

    def test_default_context_is_empty(self):
        """Fresh context should have None values."""
        # Reset to clean state
        clear_session()
        
        assert current_user_id() is None
        assert current_session_id() is None
        assert current_project_root() is None

    def test_set_and_get_context(self):
        """Setting context should make values available."""
        token = set_session(
            user_id="user-123",
            session_id="session-456",
            project_root="/path/to/project",
        )
        
        try:
            assert current_user_id() == "user-123"
            assert current_session_id() == "session-456"
            assert current_project_root() == "/path/to/project"
        finally:
            clear_session(token)

    def test_clear_session_resets_context(self):
        """Clearing context should reset to None."""
        set_session("user", "session", "/path")
        clear_session()
        
        assert current_user_id() is None
        assert current_session_id() is None


class TestSessionContextManager:
    """Test context manager usage."""

    def test_sync_context_manager(self):
        """Test synchronous context manager."""
        clear_session()
        
        with session_context_scope("user-1", "session-1", "/project/1"):
            assert current_user_id() == "user-1"
            assert current_session_id() == "session-1"
        
        # Should be cleared after exit
        assert current_user_id() is None

    @pytest.mark.asyncio
    async def test_async_context_manager(self):
        """Test async context manager."""
        clear_session()
        
        async with session_context_scope("user-2", "session-2", "/project/2"):
            assert current_user_id() == "user-2"
            assert current_session_id() == "session-2"
        
        # Should be cleared after exit
        assert current_user_id() is None


@pytest.mark.asyncio
class TestConcurrentContextIsolation:
    """Test that concurrent async requests are properly isolated."""

    async def test_concurrent_requests_isolated(self):
        """
        SECURITY: Concurrent async requests should NOT see each other's context.
        
        This test verifies the fix for the race condition where module-level
        globals could cause one user's operations to affect another user's session.
        """
        results = {"task1": [], "task2": []}
        
        async def task1():
            async with session_context_scope("user-A", "session-A", "/project/A"):
                # Record what we see
                results["task1"].append(current_user_id())
                # Simulate some async work
                await asyncio.sleep(0.01)
                # Should still see our own context after await
                results["task1"].append(current_user_id())
        
        async def task2():
            async with session_context_scope("user-B", "session-B", "/project/B"):
                results["task2"].append(current_user_id())
                await asyncio.sleep(0.01)
                results["task2"].append(current_user_id())
        
        # Run both tasks concurrently
        await asyncio.gather(task1(), task2())
        
        # Each task should only see its own user ID
        assert results["task1"] == ["user-A", "user-A"]
        assert results["task2"] == ["user-B", "user-B"]

    async def test_nested_context_isolation(self):
        """Test that nested contexts work correctly."""
        clear_session()
        
        async with session_context_scope("outer-user", "outer-session", "/outer"):
            assert current_user_id() == "outer-user"
            
            # Nested context should override
            with session_context_scope("inner-user", "inner-session", "/inner"):
                assert current_user_id() == "inner-user"
            
            # Should restore to outer after inner exits
            assert current_user_id() == "outer-user"
        
        # Should be cleared after outer exits
        assert current_user_id() is None

    async def test_exception_doesnt_leak_context(self):
        """Context should be cleared even if exception occurs."""
        clear_session()
        
        with pytest.raises(ValueError):
            async with session_context_scope("user", "session", "/path"):
                assert current_user_id() == "user"
                raise ValueError("test error")
        
        # Should still be cleared
        assert current_user_id() is None
