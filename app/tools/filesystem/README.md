# `app/tools/filesystem/`

Read/write/list files under the configured workspace root.

## Files

| File | Purpose |
|------|---------|
| `__init__.py` | Exports `tool = FilesystemTool()` |
| `tool.py` | Filesystem actions: `list`, `read`, `write` |
| `paths.py` | Workspace path resolution + confinement helpers |

## Permissions

- `filesystem.read`
- `filesystem.write`

## Example

```python
kernel = ExecutionKernel()
await kernel.execute("filesystem", action="write", path="notes.txt", content="hi")
print(await kernel.execute("filesystem", action="read", path="notes.txt"))
print(await kernel.execute("filesystem", action="list", path="."))
```
