from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

from app.agents.chat_loop import chat_loop
from app.core.config import settings
from app.observability.metrics import metrics
from app.runtime.sandbox import sandbox_manager
from app.security.auth import require_api_key
from app.storage.db import storage
from app.storage.paths import paths
from app.tools.loader import load_plugins, registry

load_plugins()

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    dependencies=[Depends(require_api_key)],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class UserCreate(BaseModel):
    name: str = Field(..., min_length=1)
    role: str = "member"


class SessionCreate(BaseModel):
    title: str = "New chat"
    user_id: str | None = None


class ChatRequest(BaseModel):
    content: str = Field(..., min_length=1)
    user_id: str | None = None


def resolve_user_id(x_forge_user: str | None = Header(default=None)) -> str:
    return x_forge_user or settings.DEFAULT_USER_ID


@app.on_event("startup")
async def on_startup():
    storage.ensure_default_user()
    metrics.incr("app.startup")
    storage.audit("startup", {"version": settings.APP_VERSION, "home": str(settings.forge_home)})


@app.get("/")
async def root():
    return {
        "message": "Welcome to ForgeAI!",
        "forge_home": str(settings.forge_home),
        "version": settings.APP_VERSION,
    }


@app.get("/health")
async def health():
    return {"status": "healthy", "version": settings.APP_VERSION}


@app.get("/tools")
async def list_tools():
    return {"tools": [item.model_dump() for item in registry.discover()]}


@app.get("/sandbox/status")
async def sandbox_status():
    return {
        "backend": settings.SANDBOX_BACKEND,
        "cpu_limit": settings.SANDBOX_CPU_LIMIT,
        "memory_mb": settings.SANDBOX_MEMORY_MB,
        "timeout_seconds": settings.SANDBOX_TIMEOUT_SECONDS,
        "network": settings.SANDBOX_NETWORK,
        "docker_image": settings.DOCKER_IMAGE,
        "active": sandbox_manager.list_active(),
        "forge_home": str(settings.forge_home),
    }


@app.post("/users")
async def create_user(request: UserCreate):
    return storage.create_user(name=request.name, role=request.role)


@app.get("/users")
async def list_users():
    return {"users": storage.list_users()}


@app.get("/users/me")
async def users_me(user_id: str = Depends(resolve_user_id)):
    user = storage.get_user(user_id) or storage.ensure_default_user()
    stats = storage.user_stats(user["user_id"])
    return {**user, "stats": stats}


@app.post("/sessions")
async def create_session(
    request: SessionCreate | None = None,
    user_id: str = Depends(resolve_user_id),
):
    uid = (request.user_id if request else None) or user_id
    if not storage.get_user(uid):
        raise HTTPException(status_code=404, detail="User not found")
    title = request.title if request else "New chat"
    return storage.create_session(uid, title=title)


@app.get("/sessions")
async def list_sessions(user_id: str = Depends(resolve_user_id)):
    return {"sessions": storage.list_sessions(user_id)}


@app.get("/sessions/{session_id}")
async def get_session(session_id: str, user_id: str = Depends(resolve_user_id)):
    session = storage.get_session(session_id)
    if not session or session["user_id"] != user_id:
        raise HTTPException(status_code=404, detail="Session not found")
    meta = paths.read_json(paths.meta_path(user_id, session_id), session)
    return meta


@app.get("/sessions/{session_id}/messages")
async def get_messages(session_id: str, user_id: str = Depends(resolve_user_id)):
    session = storage.get_session(session_id)
    if not session or session["user_id"] != user_id:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"messages": storage.list_messages(session_id)}


@app.post("/sessions/{session_id}/chat")
async def session_chat(
    session_id: str,
    request: ChatRequest,
    user_id: str = Depends(resolve_user_id),
):
    uid = request.user_id or user_id
    session = storage.get_session(session_id)
    if not session or session["user_id"] != uid:
        raise HTTPException(status_code=404, detail="Session not found")
    user = storage.get_user(uid)
    metrics.incr("chat.requests")
    result = await chat_loop.run(
        user_id=uid,
        session_id=session_id,
        content=request.content,
        role=user["role"] if user else "owner",
    )
    return result


@app.get("/sessions/{session_id}/stream")
async def session_stream(session_id: str, user_id: str = Depends(resolve_user_id)):
    session = storage.get_session(session_id)
    if not session or session["user_id"] != user_id:
        raise HTTPException(status_code=404, detail="Session not found")

    queue = chat_loop.subscribe(session_id)

    async def event_generator():
        try:
            yield f"data: {json.dumps({'type': 'subscribed', 'payload': {'session_id': session_id}})}\n\n"
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=20.0)
                except TimeoutError:
                    yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"
                    continue
                yield f"data: {json.dumps(event, default=str)}\n\n"
                if event.get("type") == "ChatCompleted":
                    break
        finally:
            chat_loop.unsubscribe(session_id, queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/sessions/{session_id}/upload")
async def upload_file(
    session_id: str,
    file: UploadFile = File(...),
    user_id: str = Depends(resolve_user_id),
):
    session = storage.get_session(session_id)
    if not session or session["user_id"] != user_id:
        raise HTTPException(status_code=404, detail="Session not found")
    uploads = paths.uploads_path(user_id, session_id)
    target = uploads / (file.filename or f"upload-{paths.new_id()}")
    data = await file.read()
    target.write_bytes(data)
    # Also copy into workspace for agent access
    workspace_copy = paths.workspace_path(user_id, session_id) / target.name
    workspace_copy.write_bytes(data)
    storage.add_message(
        session_id=session_id,
        user_id=user_id,
        role="system",
        content=f"Uploaded file: {target.name}",
        metadata={"upload": target.name, "bytes": len(data)},
    )
    return {
        "filename": target.name,
        "bytes": len(data),
        "path": str(target),
        "workspace_path": str(workspace_copy),
    }


@app.get("/sessions/{session_id}/files")
async def list_session_files(session_id: str, user_id: str = Depends(resolve_user_id)):
    session = storage.get_session(session_id)
    if not session or session["user_id"] != user_id:
        raise HTTPException(status_code=404, detail="Session not found")

    def _list(folder: Path, kind: str):
        if not folder.exists():
            return []
        return [
            {
                "name": item.name,
                "kind": kind,
                "size": item.stat().st_size,
                "path": str(item),
            }
            for item in folder.iterdir()
            if item.is_file()
        ]

    return {
        "uploads": _list(paths.uploads_path(user_id, session_id), "upload"),
        "artifacts": _list(paths.artifacts_path(user_id, session_id), "artifact"),
        "workspace": _list(paths.workspace_path(user_id, session_id), "workspace"),
    }


@app.get("/sessions/{session_id}/files/{kind}/{filename}")
async def download_session_file(
    session_id: str,
    kind: str,
    filename: str,
    user_id: str = Depends(resolve_user_id),
):
    session = storage.get_session(session_id)
    if not session or session["user_id"] != user_id:
        raise HTTPException(status_code=404, detail="Session not found")
    mapping = {
        "upload": paths.uploads_path(user_id, session_id),
        "artifact": paths.artifacts_path(user_id, session_id),
        "workspace": paths.workspace_path(user_id, session_id),
    }
    folder = mapping.get(kind)
    if folder is None:
        raise HTTPException(status_code=400, detail="Invalid kind")
    target = (folder / filename).resolve()
    if not target.is_relative_to(folder.resolve()) or not target.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(target, filename=filename)


@app.get("/sessions/{session_id}/stats")
async def session_stats(session_id: str, user_id: str = Depends(resolve_user_id)):
    session = storage.get_session(session_id)
    if not session or session["user_id"] != user_id:
        raise HTTPException(status_code=404, detail="Session not found")
    return storage.session_stats(session_id)


@app.get("/stats/me")
async def stats_me(user_id: str = Depends(resolve_user_id)):
    return storage.user_stats(user_id)


@app.get("/metrics")
async def get_metrics():
    return metrics.snapshot()
