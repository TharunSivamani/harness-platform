from app.core.config import settings
from app.llm.openai_provider import OpenAIProvider


class VLLMProvider(OpenAIProvider):
    """
    vLLM exposes an OpenAI-compatible API.
    """

    def __init__(
        self,
        model: str | None = None,
        base_url: str | None = None,
        api_key: str = "EMPTY",
    ):
        super().__init__(
            api_key=api_key,
            model=model or settings.MODEL_NAME,
            base_url=base_url or settings.VLLM_BASE_URL,
        )
