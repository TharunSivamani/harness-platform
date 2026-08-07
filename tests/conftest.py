"""
Pytest configuration and shared fixtures.
"""

import pytest
import tempfile
from pathlib import Path


@pytest.fixture
def temp_workspace():
    """Create a temporary workspace directory for tests."""
    with tempfile.TemporaryDirectory(prefix="forge-test-") as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_project(temp_workspace):
    """Create a sample project structure for testing."""
    # Create some sample files
    (temp_workspace / "README.md").write_text("# Test Project\n")
    (temp_workspace / "main.py").write_text("print('hello')\n")
    (temp_workspace / "src").mkdir()
    (temp_workspace / "src" / "app.py").write_text("# App code\n")
    return temp_workspace
