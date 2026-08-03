from openai import AsyncOpenAI

from app.core.config import settings
from app.llm.base import BaseLLM


class OpenAIProvider(BaseLLM):
    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
    ):
        self.model = model or settings.MODEL_NAME
        self.api_key = api_key if api_key is not None else settings.OPENAI_API_KEY
        self.base_url = base_url
        self._client: AsyncOpenAI | None = None

    @property
    def client(self) -> AsyncOpenAI:
        if self._client is None:
            self._client = AsyncOpenAI(
                api_key=self.api_key or "MISSING_OPENAI_API_KEY",
                base_url=self.base_url,
            )
        return self._client

    async def complete(self, prompt: str, system: str | None = None) -> str:
        if not self.api_key and self.base_url is None:
            raise ValueError("OPENAI_API_KEY is required for OpenAIProvider.")

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0,
        )
        return response.choices[0].message.content or ""
