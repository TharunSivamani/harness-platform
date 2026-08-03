import httpx

from app.core.config import settings
from app.llm.base import BaseLLM


class OllamaProvider(BaseLLM):
    def __init__(
        self,
        model: str | None = None,
        base_url: str | None = None,
    ):
        self.model = model or settings.MODEL_NAME
        self.base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")

    async def complete(self, prompt: str, system: str | None = None) -> str:
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
        }
        if system:
            payload["system"] = system

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self.base_url}/api/generate",
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        return data.get("response", "")
