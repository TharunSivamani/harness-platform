# `app/tools/search/`

Web search via DuckDuckGo HTML results (Instant Answer fallback).

## Files

| File | Purpose |
|------|---------|
| `__init__.py` | Exports `tool = SearchTool()` |
| `tool.py` | Async search + result parsing |

## Permissions

- `search`

## Example

```python
result = await kernel.execute("search", query="Python asyncio", max_results=3)
for item in result.output:
    print(item["title"], item["url"])
```
