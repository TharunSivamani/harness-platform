"""Interactive arrow-key selector (Claude Code / Hermes-style).

↑↓ navigate · type to filter · enter confirm · esc cancel
Falls back to a numbered prompt when stdin is not a TTY.

Works inside an already-running asyncio loop (forgeai chat REPL).
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class Choice:
    value: str
    label: str
    description: str = ""


def _visible(choices: Sequence[Choice], query: str) -> list[Choice]:
    q = query.strip().lower()
    if not q:
        return list(choices)
    return [
        c
        for c in choices
        if q in c.value.lower()
        or q in c.label.lower()
        or q in (c.description or "").lower()
    ]


def _fallback_select(
    title: str,
    choices: Sequence[Choice],
    *,
    current: str | None = None,
) -> str | None:
    print(title)
    for i, choice in enumerate(choices, start=1):
        mark = "*" if choice.value == current else " "
        desc = f"  {choice.description}" if choice.description else ""
        print(f" {mark} {i}. {choice.label}{desc}")
    print("  enter number (empty cancel)")
    try:
        raw = input("> ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return None
    if not raw:
        return None
    if raw.isdigit():
        idx = int(raw)
        if 1 <= idx <= len(choices):
            return choices[idx - 1].value
    for choice in choices:
        if choice.value == raw or choice.label == raw:
            return choice.value
    print("Invalid selection.")
    return None


def _build_app(
    title: str,
    choices: Sequence[Choice],
    *,
    current: str | None = None,
):
    from prompt_toolkit.application import Application
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.layout import Layout
    from prompt_toolkit.layout.containers import HSplit, Window
    from prompt_toolkit.layout.controls import FormattedTextControl
    from prompt_toolkit.styles import Style

    state = {
        "index": 0,
        "query": "",
        "result": None,
        "cancelled": False,
    }
    items = list(choices)
    if current:
        for i, choice in enumerate(items):
            if choice.value == current:
                state["index"] = i
                break

    def filtered() -> list[Choice]:
        return _visible(items, state["query"])

    def clamp() -> None:
        rows = filtered()
        if not rows:
            state["index"] = 0
            return
        state["index"] = max(0, min(state["index"], len(rows) - 1))

    def render() -> list[tuple[str, str]]:
        rows = filtered()
        clamp()
        out: list[tuple[str, str]] = []
        out.append(("class:title", f"{title}\n"))
        if state["query"]:
            out.append(("class:hint", f"  filter: {state['query']}\n"))
        if not rows:
            out.append(("class:dim", "  (no matches)\n"))
        else:
            window = 12
            start = max(0, state["index"] - window // 2)
            end = min(len(rows), start + window)
            start = max(0, end - window)
            if start > 0:
                out.append(("class:dim", f"  ... {start} more above\n"))
            for i in range(start, end):
                choice = rows[i]
                active = i == state["index"]
                pointer = ">" if active else " "
                star = "*" if choice.value == current else " "
                style = "class:selected" if active else "class:item"
                line = f" {pointer}{star} {choice.label}"
                if choice.description:
                    line += f"  {choice.description}"
                out.append((style, line + "\n"))
            below = len(rows) - end
            if below > 0:
                out.append(("class:dim", f"  ... {below} more below\n"))
        out.append(
            (
                "class:hint",
                "  up/down  enter  esc  type to filter  backspace\n",
            )
        )
        return out

    kb = KeyBindings()

    @kb.add("up")
    @kb.add("c-p")
    def _up(event) -> None:  # noqa: ANN001
        rows = filtered()
        if rows:
            state["index"] = (state["index"] - 1) % len(rows)
            event.app.invalidate()

    @kb.add("down")
    @kb.add("c-n")
    def _down(event) -> None:  # noqa: ANN001
        rows = filtered()
        if rows:
            state["index"] = (state["index"] + 1) % len(rows)
            event.app.invalidate()

    @kb.add("enter")
    def _enter(event) -> None:  # noqa: ANN001
        rows = filtered()
        if rows:
            state["result"] = rows[state["index"]].value
        event.app.exit()

    @kb.add("escape")
    @kb.add("c-c")
    @kb.add("c-g")
    def _cancel(event) -> None:  # noqa: ANN001
        state["cancelled"] = True
        event.app.exit()

    @kb.add("backspace")
    def _backspace(event) -> None:  # noqa: ANN001
        if state["query"]:
            state["query"] = state["query"][:-1]
            state["index"] = 0
            event.app.invalidate()

    @kb.add("<any>")
    def _type(event) -> None:  # noqa: ANN001
        data = event.data
        if data and data.isprintable() and data not in "\r\n\t":
            state["query"] += data
            state["index"] = 0
            event.app.invalidate()

    style = Style.from_dict(
        {
            "title": "bold #ffaf5f",
            "selected": "bold #ffffff bg:#4a3728",
            "item": "",
            "dim": "#808080",
            "hint": "#808080",
        }
    )

    control = FormattedTextControl(render, focusable=True, show_cursor=False)
    layout = Layout(HSplit([Window(content=control, always_hide_cursor=True)]))
    app: Application[None] = Application(
        layout=layout,
        key_bindings=kb,
        style=style,
        full_screen=False,
        mouse_support=False,
    )
    return app, state


async def select_option(
    title: str,
    choices: Sequence[Choice],
    *,
    current: str | None = None,
) -> str | None:
    """
    Inline interactive select. Safe to await inside forgeai chat's asyncio loop.
    """
    if not choices:
        return None
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        return _fallback_select(title, choices, current=current)

    try:
        app, state = _build_app(title, choices, current=current)
    except ImportError:
        return _fallback_select(title, choices, current=current)

    await app.run_async()
    if state["cancelled"]:
        return None
    return state["result"]
