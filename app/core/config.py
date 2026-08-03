from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "ForgeAI"
    APP_VERSION: str = "0.1.0"

    HOST: str = "0.0.0.0"
    PORT: int = 8000

    OPENAI_API_KEY: str | None = None
    MODEL_NAME: str = "gpt-4.1-mini"

    WORKSPACE_ROOT: str = "./workspace"
    ARTIFACT_ROOT: str = "./artifacts"
    TERMINAL_TIMEOUT_SECONDS: int = 10
    TERMINAL_ALLOWLIST: str = "dir,ls,echo,type,cat,pwd,cd,whoami,python,python3,pip"

    BROWSER_TIMEOUT_SECONDS: int = 30
    BROWSER_MAX_TEXT_CHARS: int = 8000

    LLM_PROVIDER: str = "openai"
    LLM_FALLBACK_PROVIDERS: str = "ollama,vllm"
    PLANNER_MODE: str = "auto"
    ANTHROPIC_API_KEY: str | None = None
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    VLLM_BASE_URL: str = "http://localhost:8001/v1"

    SANDBOX_BACKEND: str = "local"  # local | docker
    SANDBOX_CPU_LIMIT: float = 1.0
    SANDBOX_MEMORY_MB: int = 512
    SANDBOX_TIMEOUT_SECONDS: int = 30
    SANDBOX_NETWORK: bool = False
    DOCKER_IMAGE: str = "python:3.11-slim"

    API_KEY: str | None = None
    DEFAULT_ROLE: str = "admin"
    DATABASE_URL: str = "sqlite:///./forgeai.db"
    MAX_WORKSPACE_BYTES: int = 100 * 1024 * 1024
    TASK_WORKERS: int = 2

    class Config:
        env_file = ".env"

    @property
    def terminal_allowlist(self) -> set[str]:
        return {
            item.strip().lower()
            for item in self.TERMINAL_ALLOWLIST.split(",")
            if item.strip()
        }

    @property
    def llm_fallback_providers(self) -> list[str]:
        return [
            item.strip().lower()
            for item in self.LLM_FALLBACK_PROVIDERS.split(",")
            if item.strip()
        ]


settings = Settings()
