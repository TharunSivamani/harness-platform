from fastapi import FastAPI

from app.core.config import settings

from app.tools.loader import load_plugins

load_plugins()

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
)


@app.get("/")
async def root():
    return {
        "message": "Welcome to ForgeAI!"
    }


@app.get("/health")
async def health():
    return {
        "status": "healthy"
    }