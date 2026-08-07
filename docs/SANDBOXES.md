# Sandboxes (Hermes-aligned)

ForgeAI follows the Hermes pattern:

1. **`terminal`** runs shell commands on a backend (`auto` / `local` / `docker`)
2. **File edits** use dedicated tools (`read_file`, `write_file`, `patch`) where the LLM supplies content
3. **Code root** is the session `project_root` when set (opened folder / CLI cwd); otherwise the scratch folder under `FORGE_HOME/users/<user>/sessions/<id>/workspace`

## Backends

| Backend | Behavior |
|---------|----------|
| `auto` (default) | Use Docker when the `docker` CLI is available, else local |
| `local` | Commands run on host inside the project/workspace root (inherits env) |
| `docker` | Ephemeral `docker run --rm` with project/workspace mounted at `/workspace` |

```env
SANDBOX_BACKEND=auto
SANDBOX_FOR_TERMINAL=true
```

```bash
curl http://127.0.0.1:8000/sandbox/status
```

Do not use shell `echo`/`cat` for edits when `write_file`/`patch` exist — that is the Hermes/Claude Code convention.
