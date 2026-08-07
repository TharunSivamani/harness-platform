from __future__ import annotations

from fastapi import Header, HTTPException

from app.core.config import settings


async def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    """
    Optional API key gate. Disabled when settings.API_KEY is unset.
    """
    expected_key = settings.get_api_key()
    if not expected_key:
        return
    if x_api_key != expected_key:
        raise HTTPException(status_code=401, detail="Invalid or missing API key.")


def resolve_role(x_forge_role: str | None = Header(default=None)) -> str:
    return x_forge_role or settings.DEFAULT_ROLE
