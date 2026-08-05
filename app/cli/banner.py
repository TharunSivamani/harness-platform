"""Claude Code–style welcome panel for ForgeAI CLI."""

from __future__ import annotations

import shutil
import sys
from getpass import getuser

from app.core.config import settings

# Small “forge sprite” — distro-logo / Claude-invader energy.
SPRITE_UTF8 = [
    "  ▄██▄  ",
    " █████ ",
    "█ ███ █",
    " █████ ",
    "█ ▀ ▀ █",
    " ▀▀▀▀▀ ",
]

SPRITE_ASCII = [
    "  .--.  ",
    " /####\\ ",
    "| #  # |",
    " \\####/ ",
    " | || | ",
    " '----' ",
]


def ensure_utf8_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001
            pass


def _supports(text: str) -> bool:
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    try:
        text.encode(encoding)
        return True
    except UnicodeEncodeError:
        return False


def _box_chars() -> dict[str, str]:
    fancy = {
        "tl": "╭",
        "tr": "╮",
        "bl": "╰",
        "br": "╯",
        "h": "─",
        "v": "│",
        "vr": "├",
        "vl": "┤",
        "hd": "┬",
        "hu": "┴",
        "x": "┼",
        "dot": "·",
    }
    plain = {
        "tl": "+",
        "tr": "+",
        "bl": "+",
        "br": "+",
        "h": "-",
        "v": "|",
        "vr": "+",
        "vl": "+",
        "hd": "+",
        "hu": "+",
        "x": "+",
        "dot": "*",
    }
    sample = "".join(fancy.values())
    return fancy if _supports(sample) else plain


def _c(text: str, code: str) -> str:
    return f"\033[{code}m{text}\033[0m"


def accent(text: str) -> str:
    return _c(text, "38;5;208")


def dim(text: str) -> str:
    return _c(text, "2")


def bold(text: str) -> str:
    return _c(text, "1")


def visible_len(text: str) -> int:
    """Length ignoring ANSI CSI sequences."""
    out = 0
    i = 0
    while i < len(text):
        if text[i] == "\033":
            j = text.find("m", i)
            i = j + 1 if j != -1 else i + 1
            continue
        out += 1
        i += 1
    return out


def _pad(text: str, width: int) -> str:
    pad = max(0, width - visible_len(text))
    return text + (" " * pad)


def _center(text: str, width: int) -> str:
    pad = max(0, width - visible_len(text))
    left = pad // 2
    return (" " * left) + text + (" " * (pad - left))


def _truncate(text: str, width: int) -> str:
    if len(text) <= width:
        return text
    if width <= 3:
        return text[:width]
    return "..." + text[-(width - 3) :]


def term_width(fallback: int = 88) -> int:
    try:
        return max(64, min(shutil.get_terminal_size((fallback, 20)).columns, 100))
    except OSError:
        return fallback


def sprite_lines() -> list[str]:
    sample = "\n".join(SPRITE_UTF8)
    return SPRITE_UTF8 if _supports(sample) else SPRITE_ASCII


def print_welcome_panel(
    *,
    profile: str,
    provider: str,
    model: str,
    project: str,
    version: str | None = None,
) -> None:
    """
    Claude Code–like welcome card:

      ╭─ ForgeAI v0.2 ──────────────────────────────╮
      │           Welcome back name!                │
      │              ▄██▄                           │
      │   model · profile          Tips ...         │
      │   path                     Recent ...       │
      ╰─────────────────────────────────────────────╯
    """
    b = _box_chars()
    ver = version or settings.APP_VERSION
    try:
        who = getuser()
    except Exception:  # noqa: BLE001
        who = "there"

    width = term_width()
    # outer border consumes 2; leave 2 for side padding in caller
    inner = width - 2
    # split: left identity | right tips
    right_w = max(28, inner // 3)
    left_w = inner - right_w - 1  # 1 for vertical divider

    title = f" ForgeAI v{ver} "
    top_fill = max(0, inner - len(title))
    top = f"{b['tl']}{b['h']}{title}{b['h'] * top_fill}{b['tr']}"
    print()
    print(accent(top))

    def row(left: str, right: str = "") -> None:
        # Truncate overflow (ANSI-safe enough for our short tip strings).
        if visible_len(left) > left_w:
            # drop ANSI for hard truncate fallback
            plain = left
            while visible_len(plain) > left_w and plain:
                plain = plain[:-1]
            left = plain
        if visible_len(right) > right_w:
            plain = right
            while visible_len(plain) > right_w and plain:
                plain = plain[:-1]
            right = plain
        print(
            accent(b["v"])
            + _pad(left, left_w)
            + accent(b["v"])
            + _pad(right, right_w)
            + accent(b["v"])
        )

    def full(text: str = "") -> None:
        print(accent(b["v"]) + _pad(text, inner) + accent(b["v"]))

    full("")
    full(_center(bold(f"Welcome back {who}!"), inner))
    full("")

    sprite = [accent(line) for line in sprite_lines()]
    tips_header = dim("Tips for getting started")
    tips = [
        f"{accent('/profile')} switch profile",
        f"{accent('/model')}   pick model",
        f"{accent('/')}        commands",
        f"{accent('/status')}  tokens",
    ]
    recent_header = dim("Shortcuts")
    recent = [
        f"{dim('esc')}  stop reply",
        f"{dim('^C')}   new chat",
        f"{dim('^C')}   x2 exit",
    ]

    # Build right column lines
    right_lines: list[str] = ["", tips_header, *tips, "", recent_header, *recent]
    # Left column: blank, sprite centered, blank, meta, path
    meta = f"{model} {b['dot']} {provider} {b['dot']} {profile}"
    path_line = _truncate(project, left_w - 2)
    left_lines: list[str] = [""]
    # center sprite in left column
    for line in sprite:
        left_lines.append(_center(line, left_w))
    left_lines.append("")
    left_lines.append(_center(dim(meta), left_w))
    left_lines.append(_center(dim(path_line), left_w))
    left_lines.append("")

    height = max(len(left_lines), len(right_lines))
    while len(left_lines) < height:
        left_lines.append("")
    while len(right_lines) < height:
        right_lines.append("")

    for left, right in zip(left_lines, right_lines):
        row(left, " " + right if right else "")

    bottom = f"{b['bl']}{b['h'] * inner}{b['br']}"
    print(accent(bottom))
    print()


def thin_rule() -> None:
    b = _box_chars()
    print(dim(b["h"] * term_width()))
