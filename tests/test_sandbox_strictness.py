"""
Tests for sandbox backend strictness.

These tests verify that the sandbox manager properly handles
the strict mode when Docker is unavailable.
"""

import pytest
from unittest.mock import patch
from app.runtime.sandbox import SandboxManager, SandboxUnavailableError


class TestSandboxBackendResolution:
    """Test sandbox backend resolution logic."""

    def test_auto_falls_back_to_local(self):
        """Auto mode should fall back to local when Docker unavailable."""
        manager = SandboxManager()
        
        with patch.object(manager, "docker_available", return_value=False):
            with patch("app.runtime.sandbox.settings") as mock_settings:
                mock_settings.SANDBOX_BACKEND = "auto"
                
                backend = manager.resolve_backend(strict=False)
                assert backend == "local"

    def test_auto_uses_docker_when_available(self):
        """Auto mode should use Docker when available."""
        manager = SandboxManager()
        
        with patch.object(manager, "docker_available", return_value=True):
            with patch("app.runtime.sandbox.settings") as mock_settings:
                mock_settings.SANDBOX_BACKEND = "auto"
                
                backend = manager.resolve_backend(strict=False)
                assert backend == "docker"

    def test_docker_mode_fails_when_unavailable(self):
        """
        SECURITY: Docker mode should FAIL (not downgrade) when Docker unavailable.
        """
        manager = SandboxManager()
        
        with patch.object(manager, "docker_available", return_value=False):
            with patch("app.runtime.sandbox.settings") as mock_settings:
                mock_settings.SANDBOX_BACKEND = "docker"
                
                with pytest.raises(SandboxUnavailableError) as exc_info:
                    manager.resolve_backend(strict=True)
                
                assert "docker" in str(exc_info.value).lower()
                assert "not available" in str(exc_info.value).lower()

    def test_local_mode_always_works(self):
        """Local mode should always resolve successfully."""
        manager = SandboxManager()
        
        with patch("app.runtime.sandbox.settings") as mock_settings:
            mock_settings.SANDBOX_BACKEND = "local"
            
            backend = manager.resolve_backend(strict=True)
            assert backend == "local"


class TestSandboxStatus:
    """Test sandbox status reporting."""

    def test_status_shows_docker_availability(self):
        """Status should accurately report Docker availability."""
        manager = SandboxManager()
        
        with patch.object(manager, "docker_available", return_value=True):
            with patch("app.runtime.sandbox.settings") as mock_settings:
                mock_settings.SANDBOX_BACKEND = "auto"
                
                status = manager.get_backend_status()
                
                assert status["docker_available"] is True
                assert status["configured"] == "auto"
                assert status["effective"] == "docker"
                assert status["would_fail_strict"] is False

    def test_status_shows_failure_prediction(self):
        """Status should predict when strict mode would fail."""
        manager = SandboxManager()
        
        with patch.object(manager, "docker_available", return_value=False):
            with patch("app.runtime.sandbox.settings") as mock_settings:
                mock_settings.SANDBOX_BACKEND = "docker"
                
                status = manager.get_backend_status()
                
                assert status["docker_available"] is False
                assert status["would_fail_strict"] is True
