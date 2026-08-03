# Sandboxes in ForgeAI

ForgeAI isolates untrusted execution through `SandboxManager` (`app/runtime/sandbox.py`).

## What exists today

| Backend | How it works | Best for |
|---------|--------------|----------|
| `local` (default) | Subprocess in a workdir with timeout | Dev / Windows |
| `docker` | `docker run --rm` with CPU/memory limits, optional `--network=none` | Stronger isolation |

Config (`.env`):

```env
SANDBOX_BACKEND=local          # or docker
SANDBOX_CPU_LIMIT=1.0
SANDBOX_MEMORY_MB=512
SANDBOX_TIMEOUT_SECONDS=30
SANDBOX_NETWORK=false
DOCKER_IMAGE=python:3.11-slim
SANDBOX_FOR_TERMINAL=true
SANDBOX_FOR_PYTHON_SCRIPTS=true
```

## What uses the sandbox

- **Terminal tool** — commands run via `SandboxManager` when `SANDBOX_FOR_TERMINAL=true`
- **Python scripts** — multi-line / `import` / `print` code runs in sandbox (`mode=script` or auto-detect); simple expressions still use restricted AST eval
- **Autonomous agent runs** — tools still go through the kernel; terminal/python inherit sandbox policy

Check live status:

```bash
curl http://127.0.0.1:8000/sandbox/status
```

## Example

```python
from app.runtime.sandbox import sandbox_manager
from app.tools.filesystem.paths import get_workspace_root

result = await sandbox_manager.execute(
    "echo hello",
    workdir=get_workspace_root(),
)
print(result.success, result.stdout)
```

Docker mode:

```env
SANDBOX_BACKEND=docker
```

Requires Docker Desktop/engine installed. If Docker is missing, ForgeAI falls back to local.

## Roadmap (not yet)

- Firecracker microVMs
- gVisor / Kata Containers
- Per-run ephemeral containers with stricter seccomp
- Network allowlists instead of all-or-nothing

These are future backends behind the same `SandboxManager.execute(...)` interface.
