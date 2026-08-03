import shlex
import time

from app.core.config import settings
from app.runtime.sandbox import sandbox_manager
from app.schemas.tool_manifest import ToolManifest
from app.schemas.tool_result import ToolResult
from app.tools.base import BaseTool
from app.tools.workspace_paths import session_workspace

manifest = ToolManifest(
    name="terminal",
    description="Run allowlisted shell commands inside the workspace sandbox.",
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
)


class TerminalTool(BaseTool):
    manifest = manifest

    async def execute(self, command: str) -> ToolResult:
        start = time.perf_counter()

        try:
            command = command.strip()
            if not command:
                raise ValueError("Command must not be empty.")

            try:
                parts = shlex.split(command, posix=False)
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
                    f"Command '{executable_name}' is not allowlisted."
                )

            workdir = session_workspace()

            if settings.SANDBOX_FOR_TERMINAL:
                sandbox = await sandbox_manager.execute(
                    command,
                    workdir=workdir,
                    timeout=settings.TERMINAL_TIMEOUT_SECONDS,
                )
                return ToolResult(
                    success=sandbox.success,
                    output=sandbox.stdout.strip() or None,
                    error=None if sandbox.success else (sandbox.stderr.strip() or f"Exit {sandbox.exit_code}"),
                    execution_time=time.perf_counter() - start,
                    metadata={
                        "returncode": sandbox.exit_code,
                        "command": command,
                        "sandbox_id": sandbox.sandbox_id,
                        "sandbox": sandbox.metadata,
                    },
                )

            import asyncio

            process = await asyncio.create_subprocess_shell(
                command,
                cwd=str(workdir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=settings.TERMINAL_TIMEOUT_SECONDS,
                )
            except TimeoutError:
                process.kill()
                await process.communicate()
                raise TimeoutError(
                    f"Command timed out after {settings.TERMINAL_TIMEOUT_SECONDS} seconds."
                )

            output = stdout.decode(errors="replace").strip()
            error_output = stderr.decode(errors="replace").strip()
            if process.returncode != 0:
                return ToolResult(
                    success=False,
                    output=output or None,
                    error=error_output or f"Exit code {process.returncode}",
                    execution_time=time.perf_counter() - start,
                    metadata={"returncode": process.returncode, "command": command},
                )

            return ToolResult(
                success=True,
                output=output,
                execution_time=time.perf_counter() - start,
                metadata={"returncode": process.returncode, "command": command},
            )

        except Exception as e:
            return ToolResult(
                success=False,
                error=str(e),
                execution_time=time.perf_counter() - start,
            )
