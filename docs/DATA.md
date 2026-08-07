# Portable data (`FORGE_HOME`)

ForgeAI stores **chat memory, LLM profiles, and session assets** under `FORGE_HOME` (default `./data`).
The **code root** is separate: `sessions.project_root` / CLI cwd / UI “Open folder”.

```text
data/
  forge.db                 # SQLite database for users, sessions, messages, token usage
  execution_log.jsonl      # Tool execution traces (auto-rotates at 10MB)
  llm/
    profiles.json          # Named provider profiles (NO secrets - just metadata)
    secrets.json           # API keys stored separately (chmod 0600, treat as secret!)
    active.json            # { "profile": "ollama-local" }
  users/<user_id>/profile.json
  users/<user_id>/sessions/<session_id>/
    meta.json              # includes project_root when set
    messages.jsonl
    uploads/
    artifacts/
    workspace/             # scratch fallback when no project is open
```

## Security Notes

- **API keys are stored in `secrets.json`, NOT in `profiles.json`**. This separation allows sharing profile configurations without exposing secrets.
- `secrets.json` is automatically created with owner-only permissions (`chmod 0600`) where supported.
- Legacy profiles with inline API keys are automatically migrated to the new split format on first load.

- Delete `data/` => wipe chats/tokens/profiles (not your project folder on disk).
- Copy `data/` to another machine => resume users/sessions/profiles; re-bind `project_root` if paths differ.
- Soft users live in SQLite + profile.json (no cloud SSO required).

## LLM profiles

```bash
forge setup                 # interactive
forge profile list
forge profile use NAME
forge chat --profile NAME "hello"
```

Same store in the Web UI: open **LLM profiles** (`/profiles`) after `forgeai ui`.

Precedence: `--profile` → active profile in `data/llm/` → env/settings defaults.
