# `app/tools/browser/`

Playwright-powered browser automation.

## Files

| File | Purpose |
|------|---------|
| `__init__.py` | Exports `tool = BrowserTool()` |
| `tool.py` | Actions: `navigate`, `content`, `screenshot` |

## Permissions

- `browser.navigate`
- `browser.screenshot`

## Setup

```bash
pip install playwright
playwright install chromium
```

## Example

```python
result = await kernel.execute(
    "browser",
    action="content",
    url="https://example.com",
)
print(result.output["title"])
```
