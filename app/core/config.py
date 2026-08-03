from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "ForgeAI"
    APP_VERSION: str = "0.1.0"

    HOST: str = "0.0.0.0"
    PORT: int = 8000

    OPENAI_API_KEY: str | None = None
    MODEL_NAME: str = "gpt-4.1-mini"

    WORKSPACE_ROOT: str = "./workspace"
    TERMINAL_TIMEOUT_SECONDS: int = 10
    TERMINAL_ALLOWLIST: str = "dir,ls,echo,type,cat,pwd,cd,whoami,python,python3,pip"

    BROWSER_TIMEOUT_SECONDS: int = 30
    BROWSER_MAX_TEXT_CHARS: int = 8000

    LLM_PROVIDER: str = "openai"
    PLANNER_MODE: str = "auto"
    ANTHROPIC_API_KEY: str | None = None
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    VLLM_BASE_URL: str = "http://localhost:8001/v1"

    class Config:
        env_file = ".env"

    @property
    def terminal_allowlist(self) -> set[str]:
        return {
            item.strip().lower()
            for item in self.TERMINAL_ALLOWLIST.split(",")
            if item.strip()
        }


settings = Settings()
