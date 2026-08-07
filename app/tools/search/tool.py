import re
import time

import httpx

from app.schemas.tool_manifest import ToolManifest
from app.schemas.tool_result import ToolResult
from app.tools.base import BaseTool

manifest = ToolManifest(
    name="search",
    description="Search the web (DuckDuckGo) and return titled results with URLs and snippets.",
    keywords=[
        "search",
        "google",
        "web",
        "lookup",
        "find",
        "query",
        "internet",
    ],
    permissions=["search"],
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query string",
            },
            "max_results": {
                "type": "integer",
                "description": "Number of results to return (1-10, default 5)",
                "default": 5,
                "minimum": 1,
                "maximum": 10,
            },
        },
        "required": ["query"],
        "additionalProperties": False,
    },
)


class SearchTool(BaseTool):
    manifest = manifest

    async def execute(self, query: str, max_results: int = 5) -> ToolResult:
        start = time.perf_counter()

        try:
            query = query.strip()
            if not query:
                raise ValueError("Query must not be empty.")

            max_results = max(1, min(max_results, 10))
            results = await self._search_duckduckgo(query, max_results)

            return ToolResult(
                success=True,
                output=results,
                execution_time=time.perf_counter() - start,
                metadata={"query": query, "count": len(results)},
            )

        except Exception as e:
            return ToolResult(
                success=False,
                error=str(e),
                execution_time=time.perf_counter() - start,
            )

    async def _search_duckduckgo(self, query: str, max_results: int) -> list[dict]:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (compatible; ForgeAI/0.1; +https://localhost)"
            ),
        }

        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            response = await client.post(
                "https://html.duckduckgo.com/html/",
                data={"q": query},
                headers=headers,
            )
            response.raise_for_status()
            html = response.text

        results: list[dict] = []
        pattern = re.compile(
            r'class="result__a"[^>]*href="(?P<href>[^"]+)"[^>]*>'
            r"(?P<title>.*?)</a>.*?class=\"result__snippet\"[^>]*>"
            r"(?P<snippet>.*?)</(?:a|td|div)>",
            re.IGNORECASE | re.DOTALL,
        )

        for match in pattern.finditer(html):
            title = re.sub(r"<[^>]+>", "", match.group("title")).strip()
            snippet = re.sub(r"<[^>]+>", "", match.group("snippet")).strip()
            href = match.group("href")

            # DuckDuckGo wraps outbound links; unwrap when possible.
            uddg = re.search(r"[?&]uddg=([^&]+)", href)
            if uddg:
                from urllib.parse import unquote

                href = unquote(uddg.group(1))

            if not title or not href:
                continue

            results.append(
                {
                    "title": title,
                    "url": href,
                    "snippet": snippet,
                }
            )

            if len(results) >= max_results:
                break

        if not results:
            # Fallback: Instant Answer API (often sparse, but better than empty).
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(
                    "https://api.duckduckgo.com/",
                    params={
                        "q": query,
                        "format": "json",
                        "no_html": 1,
                        "skip_disambig": 1,
                    },
                )
                response.raise_for_status()
                data = response.json()

            if data.get("AbstractText"):
                results.append(
                    {
                        "title": data.get("Heading") or query,
                        "url": data.get("AbstractURL") or "",
                        "snippet": data.get("AbstractText"),
                    }
                )

            for topic in data.get("RelatedTopics", [])[:max_results]:
                if isinstance(topic, dict) and topic.get("Text"):
                    results.append(
                        {
                            "title": topic.get("Text", "")[:80],
                            "url": topic.get("FirstURL") or "",
                            "snippet": topic.get("Text"),
                        }
                    )
                if len(results) >= max_results:
                    break

        return results[:max_results]
