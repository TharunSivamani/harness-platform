from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from app.agents.orchestrator import MultiAgentOrchestrator
from app.agents.planner import PlannerAgent
from app.core.config import settings
from app.memory.session import session_manager
from app.memory.system import memory_system
from app.tools.loader import load_plugins, registry

load_plugins()

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
)

planner = PlannerAgent()
orchestrator = MultiAgentOrchestrator()


class AgentRunRequest(BaseModel):
    input: str = Field(..., min_length=1)
    session_id: str | None = None


class SessionCreateRequest(BaseModel):
    metadata: dict = Field(default_factory=dict)


class MemoryStoreRequest(BaseModel):
    content: str = Field(..., min_length=1)
    tags: list[str] = Field(default_factory=list)


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


@app.post("/session")
async def create_session(request: SessionCreateRequest | None = None):
    metadata = request.metadata if request else {}
    session = session_manager.create(metadata=metadata)
    return {
        "session_id": session.session_id,
        "created_at": session.created_at,
    }


@app.get("/session/{session_id}")
async def get_session(session_id: str):
    try:
        session = session_manager.get(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return {
        "session_id": session.session_id,
        "created_at": session.created_at,
        "summary": session.summary,
        "messages": [
            {
                "role": message.role,
                "content": message.content,
                "timestamp": message.timestamp,
                "metadata": message.metadata,
            }
            for message in session.messages
        ],
    }


@app.post("/memory")
async def store_memory(request: MemoryStoreRequest):
    item = memory_system.remember(content=request.content, tags=request.tags)
    return {
        "memory_id": item.memory_id,
        "content": item.content,
        "tags": item.tags,
    }


@app.get("/memory")
async def recall_memory(query: str, limit: int = 5):
    items = memory_system.recall(query=query, limit=limit)
    return {
        "results": [
            {
                "memory_id": item.memory_id,
                "content": item.content,
                "tags": item.tags,
                "created_at": item.created_at,
            }
            for item in items
        ]
    }


@app.post("/agent/run")
async def agent_run(request: AgentRunRequest):
    session = None
    if request.session_id is not None:
        session = session_manager.get_or_create(request.session_id)
        session_manager.add_message(session.session_id, "user", request.input)

    memories = memory_system.recall(request.input, limit=3)
    enriched_input = request.input
    if memories:
        memory_block = "\n".join(f"- {item.content}" for item in memories)
        enriched_input = (
            f"Relevant memory:\n{memory_block}\n\nUser request:\n{request.input}"
        )

    result = await planner.run(enriched_input)

    if session is not None:
        session_manager.add_message(
            session.session_id,
            "assistant",
            str(result.output if result.success else result.error),
            metadata={"success": result.success},
        )
        memory_system.summarize_session(session.session_id)

    payload = result.model_dump()
    if session is not None:
        payload["session_id"] = session.session_id
    return payload


@app.post("/agent/multi")
async def agent_multi(request: AgentRunRequest):
    result = await orchestrator.run(request.input)
    return result.model_dump()
