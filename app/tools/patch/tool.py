import time

from app.schemas.tool_manifest import ToolManifest
from app.schemas.tool_result import ToolResult
from app.tools.base import BaseTool
from app.tools.workspace_paths import resolve_in_workspace

manifest = ToolManifest(
    name="patch",
    description=(
        "Exact string replace in a project file: replace old_string with new_string. "
        "Prefer this over sed/awk. old_string must match uniquely unless replace_all is true."
    ),
    keywords=["patch", "replace", "edit", "diff"],
    permissions=["patch"],
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Relative path of the file to patch",
            },
            "old_string": {
                "type": "string",
                "description": "Exact text to find in the file (must be unique unless replace_all)",
            },
            "new_string": {
                "type": "string",
                "description": "Replacement text",
            },
            "replace_all": {
                "type": "boolean",
                "description": "If true, replace every occurrence; if false, require a unique match",
                "default": False,
            },
        },
        "required": ["path", "old_string", "new_string"],
        "additionalProperties": False,
    },
)


class PatchTool(BaseTool):
    manifest = manifest

    async def execute(
        self,
        path: str,
        old_string: str,
        new_string: str,
        replace_all: bool = False,
    ) -> ToolResult:
        start = time.perf_counter()
        try:
            target = resolve_in_workspace(path)
            if not target.is_file():
                raise FileNotFoundError(f"File not found: {path}")
            text = target.read_text(encoding="utf-8")
            if old_string not in text:
                raise ValueError("old_string not found in file.")
            count = text.count(old_string)
            if not replace_all and count > 1:
                raise ValueError(
                    f"old_string found {count} times; set replace_all=true or make it unique."
                )
            updated = (
                text.replace(old_string, new_string)
                if replace_all
                else text.replace(old_string, new_string, 1)
            )
            target.write_text(updated, encoding="utf-8")
            return ToolResult(
                success=True,
                output=f"Patched {path} ({count if replace_all else 1} replacement(s))",
                execution_time=time.perf_counter() - start,
                metadata={"path": path, "replacements": count if replace_all else 1},
            )
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                error=str(exc),
                execution_time=time.perf_counter() - start,
            )
