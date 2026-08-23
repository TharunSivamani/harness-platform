"""
Smoke-test LLM factory wiring without calling remote APIs.
"""

from app.llm.factory import get_llm
from app.llm.ollama_provider import OllamaProvider
from app.llm.openai_provider import OpenAIProvider
from app.llm.vllm_provider import VLLMProvider


def main():
    openai = get_llm("openai")
    ollama = get_llm("ollama")
    vllm = get_llm("vllm")

    assert isinstance(openai, OpenAIProvider)
    assert isinstance(ollama, OllamaProvider)
    assert isinstance(vllm, VLLMProvider)
    print("LLM providers OK:", type(openai).__name__, type(ollama).__name__, type(vllm).__name__)


if __name__ == "__main__":
    main()
