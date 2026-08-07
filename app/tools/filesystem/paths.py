from pathlib import Path

from app.tools.workspace_paths import session_workspace


def get_workspace_root() -> Path:
    """Unified with project_root / session workspace (no separate global tree)."""
    root = session_workspace()
    root.mkdir(parents=True, exist_ok=True)
    return root


def resolve_workspace_path(relative_path: str = ".") -> Path:
    """
    Resolve a path under the active project/workspace root.

    Raises ValueError if the path escapes the root.
    """
    root = get_workspace_root().resolve()
    candidate = (root / relative_path).resolve()

    if not candidate.is_relative_to(root):
        raise ValueError(
            f"Path '{relative_path}' is outside the workspace."
        )

    return candidate
