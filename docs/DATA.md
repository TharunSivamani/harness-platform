# Portable data (`FORGE_HOME`)

ForgeAI stores **chat memory, LLM profiles, and session assets** under `FORGE_HOME` (default `./data`).
The **code root** is separate: `sessions.project_root` / CLI cwd / UI “Open folder”.

```text
data/
  forge.db
  llm/
    profiles.json      # named provider profiles (api keys live here — treat as secret)
    active.json        # { "profile": "ollama-local" }
  users/<user_id>/profile.json
  users/<user_id>/sessions/<session_id>/
    meta.json          # includes project_root when set
    messages.jsonl
    uploads/
    artifacts/
    workspace/         # scratch fallback when no project is open
```

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
