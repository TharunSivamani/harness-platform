# `workspace/`

Runtime workspace root for session-isolated files.

## Layout

When a session/workspace is created:

```text
workspace/
  session_<id>/
    code/
    data/
    images/
    logs/
    artifacts/
```

## Files

| File | Purpose |
|------|---------|
| `.gitkeep` | Keeps empty root tracked in git |

Session contents are gitignored. Use `WorkspaceManager` or `POST /session` / `POST /upload` to populate.
