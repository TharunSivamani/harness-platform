import time

from app.schemas.tool_manifest import ToolManifest
from app.schemas.tool_result import ToolResult
from app.tools.base import BaseTool
from app.tools.filesystem.paths import get_workspace_root, resolve_workspace_path

manifest = ToolManifest(
    name="filesystem",
    description=(
        "List, read, or write files in the workspace. "
        "For code edits prefer read_file / write_file / patch. "
        "action=list|read|write; path relative to workspace; content required for write."
    ),
    keywords=[
        "file",
        "files",
        "filesystem",
        "read",
        "write",
        "list",
        "directory",
        "folder",
        "path",
    ],
    permissions=["filesystem.read", "filesystem.write"],
    parameters={
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["list", "read", "write"],
                "description": "list: directory entries; read: file text; write: write content",
            },
            "path": {
                "type": "string",
                "description": "Relative path (default . for list)",
                "default": ".",
            },
            "content": {
                "type": "string",
                "description": "Text to write when action=write",
            },
        },
        "required": ["action"],
        "additionalProperties": False,
    },
)


class FilesystemTool(BaseTool):
    manifest = manifest

    async def execute(
        self,
        action: str,
        path: str = ".",
        content: str | None = None,
    ) -> ToolResult:
        start = time.perf_counter()

        try:
            action = action.lower().strip()

            if action == "list":
                target = resolve_workspace_path(path)
                if not target.exists():
                    raise FileNotFoundError(f"Path not found: {path}")
                if not target.is_dir():
                    raise NotADirectoryError(f"Not a directory: {path}")

                entries = sorted(
                    [
                        {
                            "name": entry.name,
                            "type": "dir" if entry.is_dir() else "file",
                        }
                        for entry in target.iterdir()
                    ],
                    key=lambda item: item["name"],
                )

                return ToolResult(
                    success=True,
                    output=entries,
                    execution_time=time.perf_counter() - start,
                    metadata={"path": str(target.relative_to(get_workspace_root()))},
                )

            if action == "read":
                target = resolve_workspace_path(path)
                if not target.is_file():
                    raise FileNotFoundError(f"File not found: {path}")

                text = target.read_text(encoding="utf-8")

                return ToolResult(
                    success=True,
                    output=text,
                    execution_time=time.perf_counter() - start,
                    metadata={"path": str(target.relative_to(get_workspace_root()))},
                )

            if action == "write":
                if content is None:
                    raise ValueError("Content is required for write action.")

                target = resolve_workspace_path(path)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8")

                return ToolResult(
                    success=True,
                    output=f"Wrote {len(content)} characters to {path}",
                    execution_time=time.perf_counter() - start,
                    metadata={"path": str(target.relative_to(get_workspace_root()))},
                )

            raise ValueError(
                f"Unsupported action '{action}'. Use list, read, or write."
            )

        except Exception as e:
            return ToolResult(
                success=False,
                error=str(e),
                execution_time=time.perf_counter() - start,
            )
