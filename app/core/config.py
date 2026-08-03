from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "ForgeAI"
    APP_VERSION: str = "0.1.0"

    HOST: str = "0.0.0.0"
    PORT: int = 8000

    OPENAI_API_KEY: str | None = None
    MODEL_NAME: str = "gpt-4.1-mini"

    class Config:
        env_file = ".env"


settings = Settings()