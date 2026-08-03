import time

from app.schemas.tool_manifest import ToolManifest
from app.schemas.tool_result import ToolResult
from app.tools.base import BaseTool
from app.tools.workspace_paths import resolve_in_workspace

manifest = ToolManifest(
    name="read_file",
    description="Read a text file from the session workspace. Prefer this over cat/type in terminal.",
    keywords=["read", "file", "open", "cat"],
    permissions=["read_file"],
)


class ReadFileTool(BaseTool):
    manifest = manifest

    async def execute(self, path: str, offset: int = 1, limit: int = 400) -> ToolResult:
        start = time.perf_counter()
        try:
            target = resolve_in_workspace(path)
            if not target.is_file():
                raise FileNotFoundError(f"File not found: {path}")
            lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
            start_idx = max(offset - 1, 0)
            chunk = lines[start_idx : start_idx + limit]
            numbered = "\n".join(f"{start_idx + i + 1}|{line}" for i, line in enumerate(chunk))
            return ToolResult(
                success=True,
                output=numbered,
                execution_time=time.perf_counter() - start,
                metadata={"path": path, "lines": len(chunk)},
            )
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                error=str(exc),
                execution_time=time.perf_counter() - start,
            )
