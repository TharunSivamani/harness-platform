from __future__ import annotations

import getpass
import os
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

import httpx

from app.core.config import settings
from app.storage.paths import paths

PROVIDERS = ("ollama", "openai", "anthropic", "vllm", "openai_compatible", "litellm")

# Thread/process override for one CLI run (`forge chat --profile X`).
_override_profile: str | None = None


def set_profile_override(name: str | None) -> None:
    global _override_profile
    _override_profile = name.strip() if name else None


def get_profile_override() -> str | None:
    return _override_profile


def _now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass
class LLMProfile:
    name: str
    provider: str
    base_url: str | None = None
    api_key: str | None = None  # in-memory only; persisted in secrets.json
    model: str | None = None
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)

    def to_public_dict(self) -> dict[str, Any]:
        """Disk-safe profile metadata — no secrets."""
        data = asdict(self)
        data.pop("api_key", None)
        return data

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LLMProfile:
        return cls(
            name=str(data["name"]).strip(),
            provider=str(data.get("provider") or "ollama").strip().lower(),
            base_url=(data.get("base_url") or None),
            api_key=(data.get("api_key") or None),
            model=(data.get("model") or None),
            created_at=str(data.get("created_at") or _now()),
            updated_at=str(data.get("updated_at") or _now()),
        )


@dataclass
class ResolvedLLMConfig:
    """Effective LLM settings after profile + env merge."""

    provider: str
    model: str
    api_key: str | None = None
    base_url: str | None = None
    profile_name: str | None = None
    ollama_think: bool = True


def mask_secret(value: str | None) -> str | None:
    if not value:
        return None
    if len(value) <= 8:
        return "****"
    return f"{value[:4]}…{value[-4:]}"


def profile_public(profile: LLMProfile) -> dict[str, Any]:
    data = profile.to_public_dict()
    data["api_key"] = mask_secret(profile.api_key)
    data["has_api_key"] = bool(profile.api_key)
    return data


def _restrict_file(path) -> None:
    """Best-effort owner-only perms (no-op / soft-fail on Windows ACLs)."""
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


class ProfileStore:
    def _load_secrets(self) -> dict[str, str]:
        raw = paths.read_json(paths.llm_secrets_path(), {"keys": {}})
        keys = raw.get("keys") or {}
        if not isinstance(keys, dict):
            return {}
        return {
            str(name): str(value)
            for name, value in keys.items()
            if value is not None and str(value).strip()
        }

    def _save_secrets(self, secrets: dict[str, str]) -> None:
        path = paths.llm_secrets_path()
        paths.write_json(path, {"keys": secrets})
        _restrict_file(path)

    def _payloads_have_inline_keys(self, items: Any) -> bool:
        if isinstance(items, dict):
            payloads = items.values()
        elif isinstance(items, list):
            payloads = items
        else:
            return False
        return any(isinstance(p, dict) and p.get("api_key") for p in payloads)

    def _load_all(self) -> dict[str, LLMProfile]:
        raw = paths.read_json(paths.llm_profiles_path(), {"profiles": {}})
        items = raw.get("profiles") or {}
        result: dict[str, LLMProfile] = {}
        if isinstance(items, dict):
            for name, payload in items.items():
                if isinstance(payload, dict):
                    result[name] = LLMProfile.from_dict({**payload, "name": name})
        elif isinstance(items, list):
            for payload in items:
                if isinstance(payload, dict) and payload.get("name"):
                    result[payload["name"]] = LLMProfile.from_dict(payload)

        secrets = self._load_secrets()
        migrated = False
        for name, profile in result.items():
            inline = (profile.api_key or "").strip() or None
            if inline and name not in secrets:
                secrets[name] = inline
                migrated = True
            # Prefer secrets file; fall back to inline only until migrated.
            profile.api_key = secrets.get(name) or inline

        if migrated or self._payloads_have_inline_keys(items):
            # Strip keys from profiles.json (Hermes: secrets live elsewhere).
            self._save_secrets(secrets)
            self._save_all(result)

        return result

    def _save_all(self, profiles: dict[str, LLMProfile]) -> None:
        paths.write_json(
            paths.llm_profiles_path(),
            {"profiles": {name: profile.to_public_dict() for name, profile in profiles.items()}},
        )
        secrets = {
            name: profile.api_key
            for name, profile in profiles.items()
            if profile.api_key and str(profile.api_key).strip()
        }
        self._save_secrets(secrets)

    def list_profiles(self) -> list[LLMProfile]:
        return sorted(self._load_all().values(), key=lambda item: item.name.lower())

    def get_profile(self, name: str) -> LLMProfile | None:
        return self._load_all().get(name)

    def upsert_profile(self, profile: LLMProfile, *, activate: bool = False) -> LLMProfile:
        provider = profile.provider.lower().strip()
        if provider not in PROVIDERS:
            raise ValueError(
                f"Unsupported provider '{provider}'. Choose from: {', '.join(PROVIDERS)}"
            )
        name = profile.name.strip()
        if not name:
            raise ValueError("Profile name is required")
        profiles = self._load_all()
        existing = profiles.get(name)
        now = _now()
        profile.name = name
        profile.provider = provider
        profile.updated_at = now
        profile.created_at = existing.created_at if existing else now
        if profile.base_url:
            profile.base_url = profile.base_url.rstrip("/")
        # Preserve existing secret when caller omits api_key (UI "leave blank").
        if (profile.api_key is None or profile.api_key == "") and existing and existing.api_key:
            profile.api_key = existing.api_key
        profiles[name] = profile
        self._save_all(profiles)
        if activate:
            self.set_active(name)
        return profile

    def delete_profile(self, name: str) -> bool:
        profiles = self._load_all()
        if name not in profiles:
            return False
        del profiles[name]
        self._save_all(profiles)
        if self.get_active_name() == name:
            fallback = next(iter(profiles), None)
            self.set_active(fallback)
        return True

    def get_active_name(self) -> str | None:
        data = paths.read_json(paths.llm_active_path(), {})
        name = data.get("profile")
        return str(name) if name else None

    def set_active(self, name: str | None) -> None:
        if name is None:
            paths.write_json(paths.llm_active_path(), {"profile": None})
            return
        if not self.get_profile(name):
            raise KeyError(f"Profile '{name}' not found")
        paths.write_json(paths.llm_active_path(), {"profile": name})

    def resolve_profile(self, name: str | None = None) -> LLMProfile | None:
        chosen = name or get_profile_override() or self.get_active_name()
        if not chosen:
            return None
        return self.get_profile(chosen)


profile_store = ProfileStore()


def default_base_url(provider: str) -> str | None:
    provider = provider.lower()
    if provider == "ollama":
        return settings.OLLAMA_BASE_URL.rstrip("/")
    if provider == "openai":
        return "https://api.openai.com/v1"
    if provider == "vllm":
        return settings.VLLM_BASE_URL.rstrip("/")
    if provider == "anthropic":
        return "https://api.anthropic.com"
    if provider in {"openai_compatible", "litellm"}:
        return "http://127.0.0.1:4000/v1"
    return None


def _openai_models_url(base_url: str) -> str:
    base = base_url.rstrip("/")
    if base.endswith("/v1"):
        return f"{base}/models"
    return f"{base}/v1/models"


async def fetch_models(
    *,
    provider: str,
    base_url: str | None,
    api_key: str | None = None,
) -> list[str]:
    models, _error = await fetch_models_detailed(
        provider=provider,
        base_url=base_url,
        api_key=api_key,
    )
    return models


async def fetch_models_detailed(
    *,
    provider: str,
    base_url: str | None,
    api_key: str | None = None,
) -> tuple[list[str], str | None]:
    """
    Autofetch model ids. Returns (models, error). error is None on success.
    Works with OpenAI, vLLM, LiteLLM proxy, and other OpenAI-compatible gateways.
    """
    provider = provider.lower().strip()
    base = (base_url or default_base_url(provider) or "").rstrip("/")
    if not base:
        return [], "Base URL is required to fetch models."

    timeout = httpx.Timeout(20.0)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            if provider == "ollama":
                response = await client.get(f"{base}/api/tags")
                response.raise_for_status()
                data = response.json()
                models = [
                    item.get("name") or item.get("model")
                    for item in (data.get("models") or [])
                    if isinstance(item, dict)
                ]
                names = sorted({name for name in models if name}, key=str.lower)
                return names, None

            if provider == "anthropic":
                return (
                    [],
                    "Anthropic does not expose a public model list endpoint here — type the model id.",
                )

            headers = {}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
            response = await client.get(_openai_models_url(base), headers=headers)
            response.raise_for_status()
            data = response.json()
            models = [
                item.get("id")
                for item in (data.get("data") or [])
                if isinstance(item, dict) and item.get("id")
            ]
            names = sorted({name for name in models if name}, key=str.lower)
            if not names:
                return [], "Endpoint returned an empty model list."
            return names, None
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text[:240] if exc.response is not None else str(exc)
        return [], f"HTTP {exc.response.status_code if exc.response else '?'}: {detail}"
    except Exception as exc:  # noqa: BLE001
        return [], str(exc)


def resolve_llm_config(profile_name: str | None = None) -> ResolvedLLMConfig:
    """
    Precedence: explicit/override profile → active profile → env/settings defaults.
    """
    profile = profile_store.resolve_profile(profile_name)
    if profile:
        provider = profile.provider
        base_url = profile.base_url or default_base_url(provider)
        api_key = profile.api_key
        if provider == "openai" and not api_key:
            api_key = settings.get_openai_api_key()
        if provider == "anthropic" and not api_key:
            api_key = settings.get_anthropic_api_key()
        if provider in {"vllm", "openai_compatible", "litellm"} and not api_key:
            api_key = settings.get_openai_api_key() or "EMPTY"
        model = profile.model or settings.MODEL_NAME
        return ResolvedLLMConfig(
            provider=provider,
            model=model,
            api_key=api_key,
            base_url=base_url,
            profile_name=profile.name,
            ollama_think=bool(settings.OLLAMA_THINK),
        )

    provider = settings.LLM_PROVIDER.lower().strip()
    base_url = default_base_url(provider)
    api_key = None
    if provider == "openai":
        api_key = settings.get_openai_api_key()
    elif provider == "anthropic":
        api_key = settings.get_anthropic_api_key()
    elif provider == "vllm":
        api_key = settings.get_openai_api_key() or "EMPTY"
    return ResolvedLLMConfig(
        provider=provider,
        model=settings.MODEL_NAME,
        api_key=api_key,
        base_url=base_url,
        profile_name=None,
        ollama_think=bool(settings.OLLAMA_THINK),
    )


def prompt_secret(label: str = "API key") -> str | None:
    try:
        value = getpass.getpass(f"{label} (leave blank to skip): ").strip()
    except Exception:  # noqa: BLE001
        value = input(f"{label} (leave blank to skip): ").strip()
    return value or None
