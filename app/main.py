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
from app.llm.profiles import (
    PROVIDERS,
    LLMProfile,
    default_base_url,
    fetch_models_detailed,
    profile_public,
    profile_store,
    resolve_llm_config,
)
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
    project_root: str | None = None


class ProjectRootRequest(BaseModel):
    path: str = Field(..., min_length=1)


class ChatRequest(BaseModel):
    content: str = ""
    user_id: str | None = None
    attachments: list[str] = Field(default_factory=list)


class LLMProfileCreate(BaseModel):
    name: str = Field(..., min_length=1)
    provider: str = Field(..., min_length=1)
    base_url: str | None = None
    api_key: str | None = None
    model: str | None = None
    activate: bool = True


class LLMModelsRequest(BaseModel):
    provider: str = Field(..., min_length=1)
    base_url: str | None = None
    api_key: str | None = None
    profile: str | None = None


def resolve_user_id(x_forge_user: str | None = Header(default=None)) -> str:
    return x_forge_user or settings.DEFAULT_USER_ID


_SKIP_TREE_NAMES = {
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    ".next",
    "dist",
    "build",
    ".tox",
    ".mypy_cache",
    ".pytest_cache",
}


def _project_root_for_session(session: dict, user_id: str) -> Path:
    raw = session.get("project_root")
    if not raw:
        raise HTTPException(status_code=400, detail="Session has no project_root")
    root = Path(raw).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        raise HTTPException(status_code=404, detail="Project root missing on disk")
    return root


def _resolve_under_project(root: Path, relative: str) -> Path:
    candidate = (root / (relative or ".")).resolve()
    if not candidate.is_relative_to(root):
        raise HTTPException(status_code=400, detail="Path escapes project root")
    return candidate


def _list_project_tree(root: Path, relative: str = ".", depth: int = 2) -> list[dict]:
    base = _resolve_under_project(root, relative)
    if not base.exists():
        raise HTTPException(status_code=404, detail="Path not found")
    if base.is_file():
        return [
            {
                "name": base.name,
                "path": str(base.relative_to(root)).replace("\\", "/"),
                "type": "file",
                "size": base.stat().st_size,
            }
        ]

    entries: list[dict] = []

    def walk(folder: Path, remaining: int) -> None:
        try:
            children = sorted(folder.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        except PermissionError:
            return
        for child in children:
            if child.name in _SKIP_TREE_NAMES or child.name.startswith("."):
                continue
            rel = str(child.relative_to(root)).replace("\\", "/")
            if child.is_dir():
                entries.append({"name": child.name, "path": rel, "type": "dir"})
                if remaining > 0:
                    walk(child, remaining - 1)
            else:
                entries.append(
                    {
                        "name": child.name,
                        "path": rel,
                        "type": "file",
                        "size": child.stat().st_size,
                    }
                )

    walk(base, max(depth, 0))
    return entries


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
        "configured": settings.SANDBOX_BACKEND,
        "backend": sandbox_manager.resolve_backend(),
        "effective": sandbox_manager.resolve_backend(),
        "docker_available": sandbox_manager.docker_available(),
        "cpu_limit": settings.SANDBOX_CPU_LIMIT,
        "memory_mb": settings.SANDBOX_MEMORY_MB,
        "timeout_seconds": settings.SANDBOX_TIMEOUT_SECONDS,
        "network": settings.SANDBOX_NETWORK,
        "docker_image": settings.DOCKER_IMAGE,
        "active": sandbox_manager.list_active(),
        "forge_home": str(settings.forge_home),
    }


def _resolved_public(name: str | None = None) -> dict:
    resolved = resolve_llm_config(name)
    return {
        "profile": resolved.profile_name,
        "provider": resolved.provider,
        "model": resolved.model,
        "base_url": resolved.base_url,
    }


@app.get("/llm/providers")
async def list_llm_providers():
    return {
        "providers": list(PROVIDERS),
        "defaults": {provider: default_base_url(provider) for provider in PROVIDERS},
    }


@app.get("/llm/profiles")
async def list_llm_profiles():
    active = profile_store.get_active_name()
    return {
        "active": active,
        "resolved": _resolved_public(),
        "profiles": [profile_public(item) for item in profile_store.list_profiles()],
    }


@app.post("/llm/profiles")
async def create_llm_profile(request: LLMProfileCreate):
    try:
        existing = profile_store.get_profile(request.name)
        api_key = request.api_key
        # Keep existing secret when the UI omits/blank-leaves the key on edit.
        if (api_key is None or api_key == "") and existing and existing.api_key:
            api_key = existing.api_key
        profile = LLMProfile(
            name=request.name,
            provider=request.provider,
            base_url=request.base_url or default_base_url(request.provider),
            api_key=api_key,
            model=request.model,
        )
        saved = profile_store.upsert_profile(profile, activate=request.activate)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return profile_public(saved)


@app.post("/llm/profiles/{name}/activate")
async def activate_llm_profile(name: str):
    try:
        profile_store.set_active(name)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"active": name, "resolved": _resolved_public(name)}


@app.delete("/llm/profiles/{name}")
async def delete_llm_profile(name: str):
    if not profile_store.delete_profile(name):
        raise HTTPException(status_code=404, detail="Profile not found")
    return {"deleted": True, "name": name, "active": profile_store.get_active_name()}


@app.post("/llm/models")
async def list_llm_models(request: LLMModelsRequest):
    """
    Autofetch models for a provider URL (setup wizard) or an existing profile name.
    Works with LiteLLM / OpenAI-compatible proxies that expose GET /v1/models.
    """
    provider = request.provider
    base_url = request.base_url
    api_key = request.api_key
    if request.profile:
        profile = profile_store.get_profile(request.profile)
        if not profile:
            raise HTTPException(status_code=404, detail="Profile not found")
        provider = profile.provider
        base_url = base_url or profile.base_url
        if not api_key:
            api_key = profile.api_key
    models, error = await fetch_models_detailed(
        provider=provider,
        base_url=base_url,
        api_key=api_key,
    )
    return {
        "provider": provider.lower().strip(),
        "base_url": (base_url or default_base_url(provider) or "").rstrip("/") or None,
        "models": models,
        "count": len(models),
        "error": error,
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
    project_root = request.project_root if request else None
    try:
        return storage.create_session(uid, title=title, project_root=project_root)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/sessions")
async def list_sessions(user_id: str = Depends(resolve_user_id)):
    return {"sessions": storage.list_sessions(user_id)}


@app.delete("/sessions/{session_id}")
async def delete_session(session_id: str, user_id: str = Depends(resolve_user_id)):
    if not storage.delete_session(session_id, user_id):
        raise HTTPException(status_code=404, detail="Session not found")
    return {"deleted": True, "session_id": session_id}


@app.get("/sessions/{session_id}")
async def get_session(session_id: str, user_id: str = Depends(resolve_user_id)):
    session = storage.get_session(session_id)
    if not session or session["user_id"] != user_id:
        raise HTTPException(status_code=404, detail="Session not found")
    meta = paths.read_json(paths.meta_path(user_id, session_id), session)
    meta["project_root"] = session.get("project_root") or meta.get("project_root")
    return meta


@app.put("/sessions/{session_id}/project")
async def set_session_project(
    session_id: str,
    request: ProjectRootRequest,
    user_id: str = Depends(resolve_user_id),
):
    try:
        return storage.set_project_root(session_id, user_id, request.path)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/sessions/{session_id}/project")
async def get_session_project(session_id: str, user_id: str = Depends(resolve_user_id)):
    session = storage.get_session(session_id)
    if not session or session["user_id"] != user_id:
        raise HTTPException(status_code=404, detail="Session not found")
    root = session.get("project_root")
    return {
        "session_id": session_id,
        "project_root": root,
        "exists": bool(root and Path(root).exists()),
    }


@app.get("/sessions/{session_id}/project/tree")
async def session_project_tree(
    session_id: str,
    path: str = ".",
    depth: int = 2,
    user_id: str = Depends(resolve_user_id),
):
    session = storage.get_session(session_id)
    if not session or session["user_id"] != user_id:
        raise HTTPException(status_code=404, detail="Session not found")
    root = _project_root_for_session(session, user_id)
    entries = _list_project_tree(root, path, depth=min(max(depth, 0), 4))
    return {
        "session_id": session_id,
        "project_root": str(root),
        "path": path,
        "entries": entries,
    }


@app.get("/sessions/{session_id}/project/file")
async def session_project_file(
    session_id: str,
    path: str,
    user_id: str = Depends(resolve_user_id),
):
    session = storage.get_session(session_id)
    if not session or session["user_id"] != user_id:
        raise HTTPException(status_code=404, detail="Session not found")
    root = _project_root_for_session(session, user_id)
    target = _resolve_under_project(root, path)
    if not target.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    if target.stat().st_size > 512_000:
        raise HTTPException(status_code=400, detail="File too large to preview")
    try:
        text = target.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Binary file") from None
    return {
        "path": path,
        "content": text,
        "size": target.stat().st_size,
    }


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
    if not (request.content or "").strip() and not request.attachments:
        raise HTTPException(status_code=400, detail="content or attachments required")
    user = storage.get_user(uid)
    metrics.incr("chat.requests")
    try:
        result = await chat_loop.run(
            user_id=uid,
            session_id=session_id,
            content=request.content,
            role=user["role"] if user else "owner",
            attachments=request.attachments,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return result


@app.post("/sessions/{session_id}/chat/cancel")
async def cancel_session_chat(session_id: str, user_id: str = Depends(resolve_user_id)):
    session = storage.get_session(session_id)
    if not session or session["user_id"] != user_id:
        raise HTTPException(status_code=404, detail="Session not found")
    chat_loop.request_cancel(session_id)
    return {"cancelled": True, "session_id": session_id}


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

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/sessions/{session_id}/upload")
async def upload_file(
    session_id: str,
    file: UploadFile = File(...),
    attach: bool = False,
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
    # Message-scoped attaches are linked when the chat message is sent.
    if not attach:
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
        "attach": attach,
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


@app.delete("/sessions/{session_id}/files/{kind}/{filename}")
async def delete_session_file(
    session_id: str,
    kind: str,
    filename: str,
    user_id: str = Depends(resolve_user_id),
):
    result = storage.delete_session_file(
        user_id=user_id,
        session_id=session_id,
        kind=kind,
        filename=filename,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="File not found")
    return result


@app.get("/artifacts")
async def list_artifacts(user_id: str = Depends(resolve_user_id)):
    """
    Cumulative uploads/artifacts/workspace files across the user's sessions.
    """
    return {"artifacts": storage.list_user_files(user_id)}


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
