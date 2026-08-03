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
