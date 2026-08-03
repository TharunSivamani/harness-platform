from fastapi import FastAPI
from pydantic import BaseModel, Field

from app.agents.planner import PlannerAgent
from app.core.config import settings
from app.tools.loader import load_plugins, registry

load_plugins()

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
)

planner = PlannerAgent()


class AgentRunRequest(BaseModel):
    input: str = Field(..., min_length=1)


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


@app.get("/tools")
async def list_tools():
    manifests = registry.discover()
    return {
        "tools": [manifest.model_dump() for manifest in manifests]
    }


@app.post("/agent/run")
async def agent_run(request: AgentRunRequest):
    result = await planner.run(request.input)
    return result.model_dump()
