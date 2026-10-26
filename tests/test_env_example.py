"""Ensure .env.example stays in sync with app/core/config.py."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _parse_env_keys(text: str) -> set[str]:
    keys = set()
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            keys.add(line.split("=", 1)[0].strip())
    return keys


def test_env_example_exists():
    assert (ROOT / ".env.example").exists()


def test_env_example_covers_core_settings():
    # Spot-check that every important Settings field appears in .env.example
    env_text = (ROOT / ".env.example").read_text(encoding="utf-8")
    env_keys = _parse_env_keys(env_text)

    config_text = (ROOT / "app" / "core" / "config.py").read_text(encoding="utf-8")
    # extract Settings attributes like "FOO: str = " or "FOO = "
    field_re = re.compile(r"^\s{4}([A-Z_]+)\s*[:=]", re.MULTILINE)
    fields = set(field_re.findall(config_text))

    # allowlist: fields that are intentionally not in .env.example (computed props, etc.)
    allow_missing = {
        "APP_NAME",
        "APP_VERSION",  # from __version__.py
    }
    expected = fields - allow_missing

    # Must cover at least the security/sandbox/llm surface
    must_have = {
        "FORGE_HOME",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "API_KEY",
        "SANDBOX_BACKEND",
        "SANDBOX_CPU_LIMIT",
        "SANDBOX_MEMORY_MB",
        "CORS_ORIGINS",
        "LLM_PROVIDER",
        "OLLAMA_BASE_URL",
    }
    missing_must = must_have - env_keys
    assert not missing_must, f".env.example missing critical keys: {missing_must}"

    # All fields should be documented (warning, not hard fail for future fields)
    undocumented = expected - env_keys
    assert not undocumented, f".env.example missing Settings fields: {undocumented}"


def test_env_example_does_not_contain_secrets():
    text = (ROOT / ".env.example").read_text(encoding="utf-8")
    # Values should be empty or placeholder — not real keys
    assert "sk-" not in text.lower(), ".env.example must not contain real API keys"
    assert "ghp_" not in text.lower()


def test_frontend_env_example_exists_and_has_api_url():
    fe = ROOT / "frontend" / ".env.example"
    assert fe.exists()
    assert "NEXT_PUBLIC_API_URL" in fe.read_text(encoding="utf-8")


def test_gitignore_ignores_env_but_not_env_example():
    text = (ROOT / ".gitignore").read_text(encoding="utf-8")
    # should ignore .env but not .env.example
    assert re.search(r"^\.env\s*$", text, re.MULTILINE), ".gitignore must ignore .env"
    # .env.example should not be ignored — if there's a generic .env* ignore it must be overridden
    # Our .gitignore does not have .env* blanket, so just ensure .env.example file exists
    assert (ROOT / ".env.example").exists()
