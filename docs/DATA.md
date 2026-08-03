# Portable data (`FORGE_HOME`)

ForgeAI stores all durable state under `FORGE_HOME` (default `./data`).

```text
data/
  forge.db
  users/<user_id>/profile.json
  users/<user_id>/sessions/<session_id>/
    meta.json
    messages.jsonl
    uploads/
    artifacts/
    workspace/
```

- Delete `data/` => wipe everything (standalone).
- Copy `data/` to another machine => resume users/sessions/files/tokens.
- Soft users live in SQLite + profile.json (no cloud SSO required).
