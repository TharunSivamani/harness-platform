from __future__ import annotations

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.agents.orchestrator import MultiAgentOrchestrator
from app.agents.planner import PlannerAgent
from app.core.config import settings
from app.kernel.kernel import ExecutionKernel
from app.memory.session import session_manager
from app.memory.system import memory_system
from app.observability.metrics import metrics
from app.runtime.artifacts import artifact_manager
from app.runtime.events import event_bus
from app.runtime.queue import task_queue
from app.runtime.recorder import execution_recorder
from app.runtime.scheduler import resource_scheduler
from app.runtime.state import TaskState, state_machine
from app.runtime.workflow import WorkflowEngine, WorkflowNode
from app.runtime.workspace import workspace_manager
from app.security.auth import require_api_key, resolve_role
from app.storage.db import storage
from app.tools.loader import load_plugins, registry

load_plugins()

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    dependencies=[Depends(require_api_key)],
)

planner = PlannerAgent()
orchestrator = MultiAgentOrchestrator()
kernel = ExecutionKernel()


class AgentRunRequest(BaseModel):
    input: str = Field(..., min_length=1)
    session_id: str | None = None


class SessionCreateRequest(BaseModel):
    metadata: dict = Field(default_factory=dict)


class MemoryStoreRequest(BaseModel):
    content: str = Field(..., min_length=1)
    tags: list[str] = Field(default_factory=list)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    session_id: str | None = None


class ToolExecuteRequest(BaseModel):
    tool: str
    arguments: dict = Field(default_factory=dict)


class WorkflowRequest(BaseModel):
    input: str = Field(..., min_length=1)


class UploadRequest(BaseModel):
    name: str
    content: str
    media_type: str = "text/plain"
    workspace_id: str | None = None


@app.on_event("startup")
async def on_startup():
    async def _tool_job(job):
        return await kernel.execute(job.payload["tool"], **job.payload.get("arguments", {}))

    task_queue.register("tool.execute", _tool_job)
    await task_queue.start()
    metrics.incr("app.startup")
    storage.audit("startup", {"version": settings.APP_VERSION})


@app.get("/")
async def root():
    return {"message": "Welcome to ForgeAI!"}


@app.get("/health")
async def health():
    return {"status": "healthy", "version": settings.APP_VERSION}


@app.get("/tools")
async def list_tools():
    manifests = registry.discover()
    return {"tools": [manifest.model_dump() for manifest in manifests]}


@app.get("/metrics")
async def get_metrics():
    snapshot = metrics.snapshot()
    snapshot["resources"] = resource_scheduler.usage
    return snapshot


@app.post("/session")
async def create_session(request: SessionCreateRequest | None = None):
    metadata = request.metadata if request else {}
    session = session_manager.create(metadata=metadata)
    workspace = workspace_manager.create(session_id=session.session_id)
    return {
        "session_id": session.session_id,
        "workspace_id": workspace.workspace_id,
        "workspace_path": str(workspace.path),
        "created_at": session.created_at,
    }


@app.get("/sessions")
async def list_sessions():
    return {"sessions": session_manager.list_sessions()}


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


@app.post("/chat")
async def chat(request: ChatRequest, role: str = Depends(resolve_role)):
    metrics.incr("chat.requests")
    task = state_machine.create(request.message)
    state_machine.transition(task.task_id, TaskState.PLANNING)
    await event_bus.publish("TaskStarted", {"task_id": task.task_id})

    run = AgentRunRequest(input=request.message, session_id=request.session_id)
    result = await _run_agent(run, role=role)

    state_machine.transition(
        task.task_id,
        TaskState.COMPLETED if result.get("success") else TaskState.FAILED,
        output=result.get("output"),
        error=result.get("error"),
    )
    await event_bus.publish("TaskCompleted", {"task_id": task.task_id, "result": result})
    return {"task_id": task.task_id, **result}


@app.post("/agent/run")
async def agent_run(request: AgentRunRequest, role: str = Depends(resolve_role)):
    return await _run_agent(request, role=role)


@app.post("/agent/multi")
async def agent_multi(request: AgentRunRequest):
    result = await orchestrator.run(request.input)
    return result.model_dump()


@app.post("/tool")
async def execute_tool(request: ToolExecuteRequest, role: str = Depends(resolve_role)):
    metrics.incr("tool.requests")
    result = await kernel.execute(request.tool, role=role, **request.arguments)
    return result.model_dump()


@app.post("/workflow")
async def run_workflow(request: WorkflowRequest):
    metrics.incr("workflow.requests")
    task = state_machine.create(request.input)
    state_machine.transition(task.task_id, TaskState.PLANNING)

    engine = WorkflowEngine()
    workflow_id = engine.create()

    async def research_step(context, outputs):
        return await kernel.execute("search", query=context["input"], max_results=3)

    async def python_step(context, outputs):
        return await kernel.execute("python", code="sum([1, 2, 3])")

    async def review_step(context, outputs):
        return {"reviewed_nodes": list(outputs.keys())}

    engine.add_node(
        workflow_id,
        WorkflowNode(node_id="research", name="research", handler=research_step),
    )
    engine.add_node(
        workflow_id,
        WorkflowNode(
            node_id="python",
            name="python",
            handler=python_step,
            depends_on=["research"],
        ),
    )
    engine.add_node(
        workflow_id,
        WorkflowNode(
            node_id="review",
            name="review",
            handler=review_step,
            depends_on=["python"],
        ),
    )

    state_machine.transition(task.task_id, TaskState.RUNNING)
    result = await engine.run(workflow_id, context={"input": request.input})
    state_machine.transition(
        task.task_id,
        TaskState.COMPLETED if result.success else TaskState.FAILED,
        output=result.outputs,
        error=str(result.errors) if result.errors else None,
    )
    return {
        "task_id": task.task_id,
        "workflow_id": result.workflow_id,
        "success": result.success,
        "outputs": {
            key: value.model_dump() if hasattr(value, "model_dump") else value
            for key, value in result.outputs.items()
        },
        "errors": result.errors,
    }


@app.post("/upload")
async def upload(request: UploadRequest):
    workspace = workspace_manager.get_or_create(request.workspace_id)
    target = workspace_manager.resolve(workspace.workspace_id, f"data/{request.name}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(request.content, encoding="utf-8")
    workspace_manager.enforce_quota(workspace.workspace_id)

    artifact = artifact_manager.store(
        target,
        name=request.name,
        media_type=request.media_type,
        metadata={"workspace_id": workspace.workspace_id},
    )
    await event_bus.publish(
        "ArtifactCreated",
        {"artifact_id": artifact.artifact_id, "name": artifact.name},
    )
    return {
        "workspace_id": workspace.workspace_id,
        "path": str(target),
        "artifact_id": artifact.artifact_id,
    }


@app.get("/artifacts")
async def list_artifacts(name: str | None = None):
    items = artifact_manager.list(name=name)
    return {
        "artifacts": [
            {
                "artifact_id": item.artifact_id,
                "name": item.name,
                "media_type": item.media_type,
                "size": item.size,
                "version": item.version,
                "created_at": item.created_at,
                "metadata": item.metadata,
            }
            for item in items
        ]
    }


@app.get("/artifacts/{artifact_id}")
async def download_artifact(artifact_id: str):
    try:
        artifact = artifact_manager.get(artifact_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return FileResponse(artifact.path, media_type=artifact.media_type, filename=artifact.name)


@app.get("/events")
async def list_events(event_type: str | None = None, limit: int = 50):
    events = event_bus.history(event_type=event_type, limit=limit)
    return {
        "events": [
            {
                "event_id": event.event_id,
                "type": event.type,
                "payload": event.payload,
                "timestamp": event.timestamp,
            }
            for event in events
        ]
    }


@app.get("/executions")
async def list_executions(limit: int = 50):
    records = execution_recorder.list(limit=limit)
    return {
        "executions": [
            {
                "record_id": record.record_id,
                "tool": record.tool,
                "success": record.success,
                "duration": record.duration,
                "error": record.error,
                "created_at": record.created_at,
            }
            for record in records
        ]
    }


@app.get("/workspaces")
async def list_workspaces():
    return {"workspaces": workspace_manager.list_workspaces()}


async def _run_agent(request: AgentRunRequest, role: str = "admin") -> dict:
    session = None
    if request.session_id is not None:
        session = session_manager.get_or_create(request.session_id)
        session_manager.add_message(session.session_id, "user", request.input)
        workspace_manager.get_or_create(session.session_id)

    memories = memory_system.recall(request.input, limit=3)
    enriched_input = request.input
    if memories:
        memory_block = "\n".join(f"- {item.content}" for item in memories)
        enriched_input = (
            f"Relevant memory:\n{memory_block}\n\nUser request:\n{request.input}"
        )

    # Temporarily set kernel role via planner kernel
    planner.kernel.role = role
    result = await planner.run(enriched_input)
    metrics.observe("agent.latency", result.execution_time)
    metrics.incr("agent.success" if result.success else "agent.failure")
    storage.audit("agent.run", {"input": request.input, "success": result.success})

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
