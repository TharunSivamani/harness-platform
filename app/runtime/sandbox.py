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


@dataclass
class SandboxResult:
    success: bool
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    execution_time: float = 0.0
    sandbox_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class SandboxManager:
    """
    Ephemeral execution sandbox.

    Backends:
    - auto: docker when the CLI is available, else local
    - local: subprocess with timeout (host env, project/workdir cwd)
    - docker: containerized run when Docker is available
    """

    def __init__(self):
        self._active: dict[str, dict[str, Any]] = {}

    def resolve_backend(self) -> str:
        configured = (settings.SANDBOX_BACKEND or "auto").lower().strip()
        if configured == "auto":
            return "docker" if shutil.which("docker") else "local"
        if configured == "docker":
            return "docker"
        return "local"

    def docker_available(self) -> bool:
        return shutil.which("docker") is not None

    async def execute(
        self,
        command: list[str] | str,
        *,
        workdir: str | Path | None = None,
        env: dict[str, str] | None = None,
        timeout: int | None = None,
        network: bool | None = None,
        mounts: dict[str, str] | None = None,
    ) -> SandboxResult:
        sandbox_id = str(uuid4())
        timeout = timeout or settings.SANDBOX_TIMEOUT_SECONDS
        network = settings.SANDBOX_NETWORK if network is None else network
        workdir = Path(workdir or tempfile.mkdtemp(prefix="forge-sandbox-"))
        workdir.mkdir(parents=True, exist_ok=True)
        backend = self.resolve_backend()

        self._active[sandbox_id] = {
            "started": time.time(),
            "workdir": str(workdir),
            "backend": backend,
            "configured": settings.SANDBOX_BACKEND,
        }

        try:
            if backend == "docker":
                return await self._execute_docker(
                    sandbox_id=sandbox_id,
                    command=command,
                    workdir=workdir,
                    env=env or {},
                    timeout=timeout,
                    network=network,
                    mounts=mounts or {},
                )
            return await self._execute_local(
                sandbox_id=sandbox_id,
                command=command,
                workdir=workdir,
                env=env or {},
                timeout=timeout,
            )
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
        if shutil.which("docker") is None:
            logger.warning("Docker not found; falling back to local sandbox")
            return await self._execute_local(
                sandbox_id=sandbox_id,
                command=command,
                workdir=workdir,
                env=env,
                timeout=timeout,
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
