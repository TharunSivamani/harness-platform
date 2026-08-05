import shlex
import time
from pathlib import Path

from app.core.config import settings
from app.runtime.sandbox import sandbox_manager
from app.schemas.tool_manifest import ToolManifest
from app.schemas.tool_result import ToolResult
from app.tools.base import BaseTool
from app.tools.workspace_paths import session_workspace

manifest = ToolManifest(
    name="terminal",
    description=(
        "Run an allowlisted shell command in the project/workspace root "
        "(e.g. python, git, pytest, npm, ls/dir). Do not use for file edits — use write_file/patch."
    ),
    keywords=[
        "terminal",
        "shell",
        "command",
        "bash",
        "cmd",
        "run",
        "execute",
    ],
    permissions=["terminal.execute"],
    parameters={
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "Full shell command string to run (executable must be allowlisted)",
            },
        },
        "required": ["command"],
        "additionalProperties": False,
    },
)


class TerminalTool(BaseTool):
    manifest = manifest

    async def execute(self, command: str) -> ToolResult:
        start = time.perf_counter()
        workdir: Path | None = None
        cmd = (command or "").strip()

        try:
            if not cmd:
                raise ValueError("Command must not be empty.")

            try:
                parts = shlex.split(cmd, posix=False)
            except ValueError as exc:
                raise ValueError(f"Invalid command: {exc}") from exc

            if not parts:
                raise ValueError("Command must not be empty.")

            executable = parts[0].lower()
            executable_name = executable.replace("\\", "/").split("/")[-1]
            if executable_name.endswith(".exe"):
                executable_name = executable_name[:-4]

            if executable_name not in settings.terminal_allowlist:
                raise PermissionError(
                    f"Command '{executable_name}' is not allowlisted. "
                    f"Allowed: {', '.join(sorted(settings.terminal_allowlist))}"
                )

            workdir = session_workspace()
            meta_base = {
                "command": cmd,
                "executable": executable_name,
                "workdir": str(workdir),
            }

            if settings.SANDBOX_FOR_TERMINAL:
                sandbox = await sandbox_manager.execute(
                    cmd,
                    workdir=workdir,
                    timeout=settings.TERMINAL_TIMEOUT_SECONDS,
                )
                stdout = (sandbox.stdout or "").strip()
                stderr = (sandbox.stderr or "").strip()
                if sandbox.success:
                    return ToolResult(
                        success=True,
                        output=stdout or None,
                        execution_time=time.perf_counter() - start,
                        metadata={
                            **meta_base,
                            "returncode": sandbox.exit_code,
                            "sandbox_id": sandbox.sandbox_id,
                            "sandbox": sandbox.metadata,
                        },
                    )

                error = stderr or stdout or f"Exit code {sandbox.exit_code}"
                return ToolResult(
                    success=False,
                    output=stdout or None,
                    error=error,
                    execution_time=time.perf_counter() - start,
                    metadata={
                        **meta_base,
                        "returncode": sandbox.exit_code,
                        "sandbox_id": sandbox.sandbox_id,
                        "sandbox": sandbox.metadata,
                        "stderr": stderr or None,
                    },
                )

            import asyncio

            process = await asyncio.create_subprocess_shell(
                cmd,
                cwd=str(workdir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout_b, stderr_b = await asyncio.wait_for(
                    process.communicate(),
                    timeout=settings.TERMINAL_TIMEOUT_SECONDS,
                )
            except TimeoutError:
                process.kill()
                await process.communicate()
                raise TimeoutError(
                    f"Command timed out after {settings.TERMINAL_TIMEOUT_SECONDS} seconds."
                )

            output = stdout_b.decode(errors="replace").strip()
            error_output = stderr_b.decode(errors="replace").strip()
            code = process.returncode if process.returncode is not None else -1
            if code != 0:
                return ToolResult(
                    success=False,
                    output=output or None,
                    error=error_output or output or f"Exit code {code}",
                    execution_time=time.perf_counter() - start,
                    metadata={**meta_base, "returncode": code, "stderr": error_output or None},
                )

            return ToolResult(
                success=True,
                output=output or None,
                execution_time=time.perf_counter() - start,
                metadata={**meta_base, "returncode": code},
            )

        except Exception as exc:  # noqa: BLE001
            message = str(exc).strip() or f"{type(exc).__name__}: command failed"
            return ToolResult(
                success=False,
                error=message,
                execution_time=time.perf_counter() - start,
                metadata={
                    "command": cmd or None,
                    "workdir": str(workdir) if workdir else None,
                    "exception": type(exc).__name__,
                },
            )
