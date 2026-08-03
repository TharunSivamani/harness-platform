from pathlib import Path

from app.core.config import settings
from app.storage.paths import paths


def get_workspace_root() -> Path:
    root = paths.root / "workspace"
    root.mkdir(parents=True, exist_ok=True)
    return root


def resolve_workspace_path(relative_path: str = ".") -> Path:
    """
    Resolve a path under the workspace root.

    Raises ValueError if the path escapes the workspace.
    """
    root = get_workspace_root()
    candidate = (root / relative_path).resolve()

    if not candidate.is_relative_to(root):
        raise ValueError(
            f"Path '{relative_path}' is outside the workspace."
        )

    return candidate
