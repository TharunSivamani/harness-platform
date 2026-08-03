import time

from app.core.config import settings
from app.schemas.tool_manifest import ToolManifest
from app.schemas.tool_result import ToolResult
from app.tools.base import BaseTool
from app.tools.filesystem.paths import get_workspace_root, resolve_workspace_path

manifest = ToolManifest(
    name="browser",
    description="Navigate pages, extract text, and take screenshots with Playwright.",
    keywords=[
        "browser",
        "browse",
        "navigate",
        "webpage",
        "website",
        "screenshot",
        "playwright",
        "url",
        "open",
    ],
)


class BrowserTool(BaseTool):
    manifest = manifest

    async def execute(
        self,
        action: str,
        url: str | None = None,
        path: str = "screenshot.png",
    ) -> ToolResult:
        start = time.perf_counter()

        try:
            try:
                from playwright.async_api import async_playwright
            except ImportError as exc:
                raise RuntimeError(
                    "Playwright is not installed. Run: pip install playwright "
                    "&& playwright install chromium"
                ) from exc

            action = action.lower().strip()
            if action not in {"navigate", "content", "screenshot"}:
                raise ValueError(
                    "Unsupported action. Use navigate, content, or screenshot."
                )

            if not url:
                raise ValueError("URL is required.")

            timeout_ms = settings.BROWSER_TIMEOUT_SECONDS * 1000

            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch(headless=True)
                try:
                    page = await browser.new_page()
                    await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)

                    if action == "navigate":
                        output = {
                            "url": page.url,
                            "title": await page.title(),
                        }
                    elif action == "content":
                        text = await page.inner_text("body")
                        output = {
                            "url": page.url,
                            "title": await page.title(),
                            "text": text[: settings.BROWSER_MAX_TEXT_CHARS],
                        }
                    else:
                        target = resolve_workspace_path(path)
                        target.parent.mkdir(parents=True, exist_ok=True)
                        await page.screenshot(path=str(target), full_page=True)
                        relative = str(target.relative_to(get_workspace_root()))
                        output = {
                            "url": page.url,
                            "title": await page.title(),
                            "screenshot": relative,
                        }
                finally:
                    await browser.close()

            return ToolResult(
                success=True,
                output=output,
                execution_time=time.perf_counter() - start,
                metadata={"action": action},
            )

        except Exception as e:
            return ToolResult(
                success=False,
                error=str(e),
                execution_time=time.perf_counter() - start,
            )
