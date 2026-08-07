# Sandboxes (Hermes-aligned)

ForgeAI follows the Hermes pattern:

1. **`terminal`** runs shell commands on a backend (`auto` / `local` / `docker`)
2. **File edits** use dedicated tools (`read_file`, `write_file`, `patch`) where the LLM supplies content
3. **Code root** is the session `project_root` when set (opened folder / CLI cwd); otherwise the scratch folder under `FORGE_HOME/users/<user>/sessions/<id>/workspace`

## Backends

| Backend | Behavior |
|---------|----------|
| `auto` (default) | Use Docker when the `docker` CLI is available, else local (logs warning) |
| `local` | Commands run on host inside the project/workspace root (inherits env, **no isolation**) |
| `docker` | Ephemeral `docker run --rm` with project/workspace mounted at `/workspace`. **FAILS if Docker unavailable** |

### Important: Backend Strictness

- **`SANDBOX_BACKEND=auto`**: Falls back to local with a warning if Docker is unavailable. Suitable for development.
- **`SANDBOX_BACKEND=docker`**: **Fails with error** if Docker is unavailable. Use this in production to prevent silent security degradation.
- **`SANDBOX_BACKEND=local`**: No isolation. Commands run directly on the host.

### Docker Requirements

When using `docker` or `auto` backend, the Docker CLI must be available in the PATH of the process running the ForgeAI API. This means:

- When running directly: Install Docker Desktop or Docker Engine
- When running in a container: Mount the Docker socket (`-v /var/run/docker.sock:/var/run/docker.sock`) AND include Docker CLI in the container image

**Note:** The default `docker-compose.yml` uses `python:3.11-slim` which does NOT include Docker CLI. If you need sandboxed execution in a containerized deployment, use `SANDBOX_BACKEND=local` or build a custom image with Docker-in-Docker support.

```env
SANDBOX_BACKEND=auto        # Falls back to local if Docker unavailable
SANDBOX_BACKEND=docker      # Fails if Docker unavailable (recommended for production)
SANDBOX_FOR_TERMINAL=true
```

```bash
curl http://127.0.0.1:8000/sandbox/status
```

Do not use shell `echo`/`cat` for edits when `write_file`/`patch` exist — that is the Hermes/Claude Code convention.

## Security Notes

The terminal tool validates commands against an allowlist and blocks shell metacharacters (`;`, `&&`, `|`, etc.) to prevent command injection. Even with sandbox isolation, the allowlist provides defense-in-depth.
