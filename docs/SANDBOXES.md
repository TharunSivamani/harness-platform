# Sandboxes (Hermes-aligned)

ForgeAI follows the Hermes pattern:

1. **`terminal`** runs shell commands on a backend (`local` or `docker`)
2. **File edits** use dedicated tools (`read_file`, `write_file`, `patch`) where the LLM supplies content
3. Workspace is **per session** under `FORGE_HOME/users/<user>/sessions/<id>/workspace`

## Backends

| Backend | Behavior |
|---------|----------|
| `local` | Commands run on host inside the session workspace |
| `docker` | Ephemeral/persistent container with mounted workspace |

```env
SANDBOX_BACKEND=local
SANDBOX_FOR_TERMINAL=true
```

```bash
curl http://127.0.0.1:8000/sandbox/status
```

Do not use shell `echo`/`cat` for edits when `write_file`/`patch` exist — that is the Hermes/Claude Code convention.
