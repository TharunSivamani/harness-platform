from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "ForgeAI"
    APP_VERSION: str = "0.2.0"

    HOST: str = "0.0.0.0"
    PORT: int = 8000

    FORGE_HOME: str = "./data"
    DEFAULT_USER_ID: str = "local"
    DEFAULT_USER_NAME: str = "Local User"
    DEFAULT_ROLE: str = "owner"

    OPENAI_API_KEY: str | None = None
    MODEL_NAME: str = "qwen3-vl:2b-thinking"

    TERMINAL_TIMEOUT_SECONDS: int = 30
    TERMINAL_ALLOWLIST: str = (
        "dir,ls,echo,type,cat,pwd,cd,whoami,python,python3,py,pip,pip3,"
        "mkdir,rm,rmdir,del,copy,cp,mv,move,git,pytest,node,npm,npx"
    )

    BROWSER_TIMEOUT_SECONDS: int = 30
    BROWSER_MAX_TEXT_CHARS: int = 8000

    LLM_PROVIDER: str = "ollama"
    LLM_FALLBACK_PROVIDERS: str = ""
    PLANNER_MODE: str = "auto"
    ANTHROPIC_API_KEY: str | None = None
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_THINK: bool = True
    VLLM_BASE_URL: str = "http://localhost:8001/v1"

    SANDBOX_BACKEND: str = "auto"  # auto | local | docker
    SANDBOX_CPU_LIMIT: float = 1.0
    SANDBOX_MEMORY_MB: int = 512
    SANDBOX_TIMEOUT_SECONDS: int = 30
    SANDBOX_NETWORK: bool = False
    DOCKER_IMAGE: str = "python:3.11-slim"
    SANDBOX_FOR_TERMINAL: bool = True
    SANDBOX_FOR_PYTHON_SCRIPTS: bool = True

    # Optional default project when CLI/API omit an explicit path (empty = none).
    DEFAULT_PROJECT_ROOT: str | None = None

    API_KEY: str | None = None
    MAX_WORKSPACE_BYTES: int = 100 * 1024 * 1024
    TASK_WORKERS: int = 2
    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"

    AGENT_MAX_STEPS: int = 12
    AGENT_AUTO_APPROVE: bool = True
    AGENT_APPROVAL_TOOLS: str = "terminal,write_file,patch,browser"

    class Config:
        env_file = ".env"

    @property
    def forge_home(self) -> Path:
        path = Path(self.FORGE_HOME).resolve()
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def database_path(self) -> Path:
        return self.forge_home / "forge.db"

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

    @property
    def cors_origins(self) -> list[str]:
        return [
            item.strip()
            for item in self.CORS_ORIGINS.split(",")
            if item.strip()
        ]

    @property
    def agent_approval_tools(self) -> set[str]:
        return {
            item.strip().lower()
            for item in self.AGENT_APPROVAL_TOOLS.split(",")
            if item.strip()
        }


settings = Settings()
