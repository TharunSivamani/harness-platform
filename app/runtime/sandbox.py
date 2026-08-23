"""
Sandbox execution manager with configurable backends.

SECURITY: When SANDBOX_BACKEND is set to 'docker' (not 'auto'), downgrade to
local execution is now a hard failure. This prevents silent security degradation
when Docker is expected but unavailable.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.core.config import settings
from app.core.logger import logger


class SandboxUnavailableError(Exception):
    """Raised when the requested sandbox backend is not available."""

    pass


@dataclass
class SandboxResult:
    success: bool
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    execution_time: float = 0.0
    sandbox_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    # Track if we downgraded from requested backend
    downgraded: bool = False
    original_backend: str | None = None


class SandboxManager:
    """
    Ephemeral execution sandbox.

    Backends:
    - auto: docker when the CLI is available, else local (with warning)
    - local: subprocess with timeout (host env, project/workdir cwd)
    - docker: containerized run - FAILS if Docker unavailable (no silent downgrade)

    SECURITY NOTE:
    - 'auto' mode will warn but continue if Docker is unavailable
    - 'docker' mode will FAIL if Docker is unavailable (no silent downgrade)
    - This prevents deployments from silently losing sandbox protection
    """

    def __init__(self):
        self._active: dict[str, dict[str, Any]] = {}
        self._downgrade_warned: bool = False

    def resolve_backend(self, strict: bool = False) -> str:
        """
        Resolve the effective backend to use.

        Args:
            strict: If True, raise SandboxUnavailableError instead of downgrading.
                   This is set automatically when SANDBOX_BACKEND='docker'.

        Returns:
            The backend name ('docker' or 'local')

        Raises:
            SandboxUnavailableError: If strict=True and Docker is unavailable.
        """
        configured = (settings.SANDBOX_BACKEND or "auto").lower().strip()

        if configured == "docker":
            if not self.docker_available():
                if strict or configured == "docker":
                    raise SandboxUnavailableError(
                        "SANDBOX_BACKEND is set to 'docker' but Docker CLI is not available. "
                        "Either install Docker, set SANDBOX_BACKEND='auto' to allow fallback, "
                        "or set SANDBOX_BACKEND='local' if sandboxing is not required."
                    )
            return "docker"

        if configured == "auto":
            if self.docker_available():
                return "docker"
            # Log warning on first downgrade
            if not self._downgrade_warned:
                logger.warning(
                    "SANDBOX_BACKEND='auto' but Docker is not available. "
                    "Falling back to local (unsandboxed) execution. "
                    "For production deployments, set SANDBOX_BACKEND='docker' "
                    "to fail loudly when Docker is unavailable."
                )
                self._downgrade_warned = True
            return "local"

        return "local"

    def docker_available(self) -> bool:
        return shutil.which("docker") is not None

    def get_backend_status(self) -> dict[str, Any]:
        """
        Get detailed status about sandbox backend configuration.
        Useful for health checks and debugging.
        """
        configured = (settings.SANDBOX_BACKEND or "auto").lower().strip()
        docker_ok = self.docker_available()

        try:
            effective = self.resolve_backend(strict=False)
            error = None
        except SandboxUnavailableError as e:
            effective = None
            error = str(e)

        return {
            "configured": configured,
            "effective": effective,
            "docker_available": docker_ok,
            "would_fail_strict": configured == "docker" and not docker_ok,
            "error": error,
        }

    async def execute(
        self,
        command: list[str] | str,
        *,
        workdir: str | Path | None = None,
        env: dict[str, str] | None = None,
        timeout: int | None = None,
        network: bool | None = None,
        mounts: dict[str, str] | None = None,
        strict: bool | None = None,
    ) -> SandboxResult:
        """
        Execute a command in the configured sandbox backend.

        Args:
            command: Command to execute (string or argv list)
            workdir: Working directory for execution
            env: Additional environment variables
            timeout: Execution timeout in seconds
            network: Allow network access (Docker only)
            mounts: Additional volume mounts (Docker only)
            strict: If True, fail if Docker unavailable when SANDBOX_BACKEND='docker'.
                   Default: True when SANDBOX_BACKEND='docker', False otherwise.

        Returns:
            SandboxResult with execution output

        Raises:
            SandboxUnavailableError: If strict=True and requested backend unavailable.
        """
        sandbox_id = str(uuid4())
        timeout = timeout or settings.SANDBOX_TIMEOUT_SECONDS
        network = settings.SANDBOX_NETWORK if network is None else network
        workdir = Path(workdir or tempfile.mkdtemp(prefix="forge-sandbox-"))
        workdir.mkdir(parents=True, exist_ok=True)

        # Determine strictness: default to strict when explicitly configured for docker
        configured = (settings.SANDBOX_BACKEND or "auto").lower().strip()
        if strict is None:
            strict = configured == "docker"

        # This will raise SandboxUnavailableError if strict and Docker unavailable
        backend = self.resolve_backend(strict=strict)

        # Track if we downgraded
        downgraded = (
            configured in ("docker", "auto") and backend == "local" and not self.docker_available()
        )

        self._active[sandbox_id] = {
            "started": time.time(),
            "workdir": str(workdir),
            "backend": backend,
            "configured": configured,
            "downgraded": downgraded,
        }

        try:
            if backend == "docker":
                result = await self._execute_docker(
                    sandbox_id=sandbox_id,
                    command=command,
                    workdir=workdir,
                    env=env or {},
                    timeout=timeout,
                    network=network,
                    mounts=mounts or {},
                )
            else:
                result = await self._execute_local(
                    sandbox_id=sandbox_id,
                    command=command,
                    workdir=workdir,
                    env=env or {},
                    timeout=timeout,
                )

            # Mark if execution was downgraded from requested backend
            if downgraded:
                result.downgraded = True
                result.original_backend = configured
                result.metadata["warning"] = (
                    "Execution ran in LOCAL mode (no sandbox isolation) "
                    f"because Docker was unavailable. Original config: {configured}"
                )

            return result
        finally:
            self._active.pop(sandbox_id, None)

    async def _execute_local(
        self,
        *,
        sandbox_id: str,
        command: list[str] | str,
        workdir: Path,
        env: dict[str, str],
        timeout: int,
    ) -> SandboxResult:
        start = time.perf_counter()
        merged_env = os.environ.copy()
        merged_env.update(env)

        if isinstance(command, str):
            process = await asyncio.create_subprocess_shell(
                command,
                cwd=str(workdir),
                env=merged_env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        else:
            process = await asyncio.create_subprocess_exec(
                *command,
                cwd=str(workdir),
                env=merged_env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
        except TimeoutError:
            process.kill()
            await process.communicate()
            return SandboxResult(
                success=False,
                stderr=f"Sandbox timed out after {timeout}s",
                exit_code=124,
                execution_time=time.perf_counter() - start,
                sandbox_id=sandbox_id,
            )

        return SandboxResult(
            success=process.returncode == 0,
            stdout=stdout.decode(errors="replace"),
            stderr=stderr.decode(errors="replace"),
            exit_code=process.returncode or 0,
            execution_time=time.perf_counter() - start,
            sandbox_id=sandbox_id,
            metadata={
                "backend": "local",
                "workdir": str(workdir),
                "cpu_limit": settings.SANDBOX_CPU_LIMIT,
            },
        )

    async def _execute_docker(
        self,
        *,
        sandbox_id: str,
        command: list[str] | str,
        workdir: Path,
        env: dict[str, str],
        timeout: int,
        network: bool,
        mounts: dict[str, str],
    ) -> SandboxResult:
        # SECURITY: No fallback here - caller must handle via resolve_backend()
        # This ensures strict mode works correctly
        if shutil.which("docker") is None:
            raise SandboxUnavailableError(
                "Docker backend was selected but Docker CLI is not available. "
                "This should not happen if resolve_backend() was called first."
            )

        cmd_parts = command if isinstance(command, list) else ["bash", "-lc", command]
        docker_cmd = [
            "docker",
            "run",
            "--rm",
            "--name",
            f"forge-{sandbox_id[:8]}",
            f"--cpus={settings.SANDBOX_CPU_LIMIT}",
            f"--memory={settings.SANDBOX_MEMORY_MB}m",
            "-v",
            f"{workdir.resolve()}:/workspace",
            "-w",
            "/workspace",
        ]
        if not network:
            docker_cmd.append("--network=none")
        for host_path, container_path in mounts.items():
            docker_cmd.extend(["-v", f"{Path(host_path).resolve()}:{container_path}"])
        for key, value in env.items():
            docker_cmd.extend(["-e", f"{key}={value}"])
        docker_cmd.append(settings.DOCKER_IMAGE)
        docker_cmd.extend(cmd_parts)

        start = time.perf_counter()
        process = await asyncio.create_subprocess_exec(
            *docker_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
        except TimeoutError:
            process.kill()
            await process.communicate()
            return SandboxResult(
                success=False,
                stderr=f"Docker sandbox timed out after {timeout}s",
                exit_code=124,
                execution_time=time.perf_counter() - start,
                sandbox_id=sandbox_id,
                metadata={"backend": "docker"},
            )

        return SandboxResult(
            success=process.returncode == 0,
            stdout=stdout.decode(errors="replace"),
            stderr=stderr.decode(errors="replace"),
            exit_code=process.returncode or 0,
            execution_time=time.perf_counter() - start,
            sandbox_id=sandbox_id,
            metadata={
                "backend": "docker",
                "image": settings.DOCKER_IMAGE,
                "memory_mb": settings.SANDBOX_MEMORY_MB,
                "workdir": str(workdir),
            },
        )

    def list_active(self) -> list[str]:
        return list(self._active.keys())


sandbox_manager = SandboxManager()
