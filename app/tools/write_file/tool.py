import time

from app.schemas.tool_manifest import ToolManifest
from app.schemas.tool_result import ToolResult
from app.tools.base import BaseTool
from app.tools.workspace_paths import resolve_in_workspace

manifest = ToolManifest(
    name="write_file",
    description="Write full file content in the session workspace. Prefer this over echo/heredoc in terminal.",
    keywords=["write", "save", "create file", "edit"],
    permissions=["write_file"],
)


class WriteFileTool(BaseTool):
    manifest = manifest

    async def execute(self, path: str, content: str) -> ToolResult:
        start = time.perf_counter()
        try:
            target = resolve_in_workspace(path)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            return ToolResult(
                success=True,
                output=f"Wrote {len(content)} characters to {path}",
                execution_time=time.perf_counter() - start,
                metadata={"path": path, "bytes": len(content.encode('utf-8'))},
            )
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                error=str(exc),
                execution_time=time.perf_counter() - start,
            )
