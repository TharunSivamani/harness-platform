"""ForgeAI CLI banner — nanochat energy, distro-logo spirit."""

from __future__ import annotations

import sys

# Block "FORGE" mark (UTF-8). Accent-color applied by caller.
FORGE_MARK_UTF8 = """
   ######  #####  #####   #####  ######
   ##     ##   ## ##  ## ##      ##
   ####   ##   ## #####  ## ###  ####
   ##     ##   ## ##  ## ##  ##  ##
   ##      #####  ##  ##  ####   ######
""".strip(
    "\n"
)

# Prefer full block glyphs when stdout can encode them (Windows Terminal / UTF-8).
FORGE_MARK_BLOCKS = """
   \u2588\u2588\u2588\u2588\u2588\u2588\u2588  \u2588\u2588\u2588\u2588\u2588\u2588  \u2588\u2588\u2588\u2588\u2588\u2588   \u2588\u2588\u2588\u2588\u2588\u2588  \u2588\u2588\u2588\u2588\u2588\u2588\u2588
   \u2588\u2588      \u2588\u2588    \u2588\u2588 \u2588\u2588   \u2588\u2588 \u2588\u2588       \u2588\u2588
   \u2588\u2588\u2588\u2588\u2588   \u2588\u2588    \u2588\u2588 \u2588\u2588\u2588\u2588\u2588\u2588  \u2588\u2588   \u2588\u2588\u2588 \u2588\u2588\u2588\u2588\u2588
   \u2588\u2588      \u2588\u2588    \u2588\u2588 \u2588\u2588   \u2588\u2588 \u2588\u2588    \u2588\u2588 \u2588\u2588
   \u2588\u2588       \u2588\u2588\u2588\u2588\u2588\u2588  \u2588\u2588   \u2588\u2588  \u2588\u2588\u2588\u2588\u2588\u2588  \u2588\u2588\u2588\u2588\u2588\u2588\u2588
""".strip(
    "\n"
)

ANVIL = r"""
      .----.
     /######\
    |## /\ ##|
    |## \/ ##|
     \##--##/
      '===='
        ||
     ===||===
""".strip(
    "\n"
)


def _stdout_supports(text: str) -> bool:
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    try:
        text.encode(encoding)
        return True
    except UnicodeEncodeError:
        return False


def ensure_utf8_stdio() -> None:
    """Best-effort UTF-8 so block logos render in Windows Terminal."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001
            pass


def forge_mark_lines() -> list[str]:
    if _stdout_supports(FORGE_MARK_BLOCKS):
        return FORGE_MARK_BLOCKS.splitlines()
    return FORGE_MARK_UTF8.splitlines()


def anvil_lines() -> list[str]:
    return ANVIL.splitlines()
