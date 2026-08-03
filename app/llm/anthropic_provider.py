import httpx

from app.core.config import settings
from app.llm.base import BaseLLM


class AnthropicProvider(BaseLLM):
    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
    ):
        self.api_key = api_key or settings.ANTHROPIC_API_KEY
        self.model = model or settings.MODEL_NAME
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY is required for AnthropicProvider.")

    async def complete(self, prompt: str, system: str | None = None) -> str:
        payload: dict = {
            "model": self.model,
            "max_tokens": 1024,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            payload["system"] = system

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        parts = data.get("content", [])
        texts = [part.get("text", "") for part in parts if part.get("type") == "text"]
        return "\n".join(texts).strip()
