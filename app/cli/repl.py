from __future__ import annotations

import asyncio
import logging
import shutil
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from app.cli.banner import ensure_utf8_stdio, print_welcome_panel, thin_rule
from app.cli.select import Choice, select_option
from app.core.config import settings
from app.llm.profiles import (
    fetch_models,
    profile_store,
    resolve_llm_config,
    set_profile_override,
)
from app.storage.db import storage
from app.storage.paths import paths

# Soft context-window estimate for the status bar (Claude-style used/limit).
DEFAULT_CONTEXT_LIMIT = 128_000
CTRL_C_EXIT_WINDOW = 2.0

SLASH_COMMANDS: list[tuple[str, str]] = [
    ("/help", "Show all commands"),
    ("/status", "Profile, model, timer, tokens"),
    ("/profile", "Switch LLM profile (picker)"),
    ("/provider", "Alias for /profile"),
    ("/switch", "Alias for /profile"),
    ("/model", "Switch model (picker + filter)"),
    ("/project", "Show or set project root"),
    ("/clear", "Fresh chat session (keep profile)"),
    ("/home", "Show ~/.forgeai config path"),
    ("/exit", "Quit the CLI"),
    ("/quit", "Alias for /exit"),
]


@dataclass
class ReplState:
    user_id: str
    session_id: str
    project_root: str
    profile: str | None = None
    started_at: float = field(default_factory=time.monotonic)
    session_started_at: float = field(default_factory=time.monotonic)
    session_tokens: int = 0
    last_turn_tokens: int = 0
    last_turn_seconds: float = 0.0
    turns: int = 0
    context_limit: int = DEFAULT_CONTEXT_LIMIT
    ctrl_c_armed_at: float | None = None
    generating: bool = False


def quiet_logging() -> None:
    logging.getLogger("forge-ai").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)


def _c(text: str, code: str) -> str:
    return f"\033[{code}m{text}\033[0m"


def dim(text: str) -> str:
    return _c(text, "2")


def bold(text: str) -> str:
    return _c(text, "1")


def accent(text: str) -> str:
    return _c(text, "38;5;208")


def cyan(text: str) -> str:
    return _c(text, "36")


def green(text: str) -> str:
    return _c(text, "32")


def term_width(fallback: int = 72) -> int:
    try:
        return max(48, min(shutil.get_terminal_size((fallback, 20)).columns, 100))
    except OSError:
        return fallback


def rule() -> None:
    thin_rule()


def format_duration(seconds: float) -> str:
    total = max(0, int(seconds))
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h{m:02d}m"
    if m:
        return f"{m}m{s:02d}s"
    return f"{s}s"


def format_tokens(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.2f}M"
    if n >= 1000:
        val = n / 1000
        text = f"{val:.2f}".rstrip("0").rstrip(".")
        return f"{text}k"
    return str(n)


def token_bar(used: int, limit: int, width: int = 12) -> str:
    if limit <= 0:
        return f"[{'.' * width}] 0%"
    pct = min(1.0, max(0.0, used / limit))
    filled = int(round(width * pct))
    body = "#" * filled + "." * (width - filled)
    return f"[{body}] {int(pct * 100)}%"


def refresh_token_stats(state: ReplState) -> None:
    stats = storage.session_stats(state.session_id)
    state.session_tokens = int(stats.get("total_tokens") or 0)


def print_status_bar(state: ReplState) -> None:
    """Compact Claude-like strip (no heavy dashed sandwich)."""
    resolved = resolve_llm_config(state.profile)
    model = resolved.model or "-"
    used = state.session_tokens
    limit = state.context_limit
    live = format_duration(time.monotonic() - state.started_at)
    chat = format_duration(time.monotonic() - state.session_started_at)
    last = format_duration(state.last_turn_seconds) if state.last_turn_seconds else "-"
    bar = token_bar(used, limit)
    print(
        f"  {cyan('$' + ' ' + model)}  {dim('|')}  "
        f"{dim(format_tokens(used) + '/' + format_tokens(limit))}  {dim('|')}  "
        f"{green(bar)}  {dim('|')}  "
        f"{dim(live)}  {dim('|')}  "
        f"{dim('chat ' + chat)}  {dim('|')}  "
        f"{dim('last ' + last)}"
    )
    if state.last_turn_tokens:
        print(
            f"  {dim('turn +' + format_tokens(state.last_turn_tokens))}  "
            f"{dim('|')}  {dim('turns ' + str(state.turns))}  "
            f"{dim('|')}  {dim(resolved.profile_name or 'env')}"
        )


def print_banner(state: ReplState) -> None:
    resolved = resolve_llm_config(state.profile)
    print_welcome_panel(
        profile=resolved.profile_name or "(env)",
        provider=resolved.provider,
        model=resolved.model or "-",
        project=state.project_root,
        version=settings.APP_VERSION,
    )
    print_status_bar(state)
    print()


def print_status(state: ReplState) -> None:
    refresh_token_stats(state)
    print()
    print_status_bar(state)
    resolved = resolve_llm_config(state.profile)
    print(f"  {dim('project')}  {state.project_root}")
    print(f"  {dim('session')}  {state.session_id}")
    print(f"  {dim('config')}   {paths.config_home()}")
    print(f"  {dim('provider')} {resolved.provider}")
    print()


def cmd_help() -> None:
    print()
    print(f"  {bold(accent('commands'))}")
    for cmd, desc in SLASH_COMMANDS:
        print(f"  {cyan(cmd):<22} {dim(desc)}")
    print()
    print(f"  {dim('type / for a live filter panel — arrows + enter to pick')}")
    print()


def cmd_home() -> None:
    print(f"{dim('config')}  {paths.config_home()}")
    print(f"{dim('llm')}     {paths.llm_dir()}")
    print(f"{dim('secrets')} {paths.llm_secrets_path()}")


async def cmd_profile_use(state: ReplState, name: str) -> None:
    name = name.strip()
    if not profile_store.get_profile(name):
        print(f"Profile not found: {name}")
        await cmd_profile_pick(state)
        return
    profile_store.set_active(name)
    set_profile_override(name)
    state.profile = name
    resolved = resolve_llm_config(name)
    print(
        f"{accent('ok')} profile {bold(name)}  "
        f"{dim(f'{resolved.provider}/{resolved.model}')}"
    )


async def cmd_profile_pick(state: ReplState) -> None:
    items = profile_store.list_profiles()
    if not items:
        print(dim("No profiles. Run: forgeai setup"))
        return
    active = profile_store.get_active_name() or state.profile
    choices = [
        Choice(
            value=p.name,
            label=p.name,
            description=f"{p.provider}/{p.model or '-'}  {p.base_url or ''}".strip(),
        )
        for p in items
    ]
    picked = await select_option("Select profile", choices, current=active)
    if picked is None:
        print(dim("cancelled"))
        return
    await cmd_profile_use(state, picked)


async def cmd_model_use(state: ReplState, model: str) -> None:
    model = model.strip()
    profile = profile_store.resolve_profile(state.profile)
    if not profile:
        print("No active profile. Use /profile first.")
        return
    profile.model = model
    profile_store.upsert_profile(profile, activate=True)
    set_profile_override(profile.name)
    state.profile = profile.name
    print(f"{accent('ok')} model {bold(model)}  {dim(f'on {profile.name}')}")


async def cmd_model_pick(state: ReplState) -> None:
    resolved = resolve_llm_config(state.profile)
    profile = profile_store.resolve_profile(state.profile)
    if not profile:
        print(dim("No active profile - run /profile or forgeai setup"))
        return
    print(dim(f"fetching models for {profile.name}..."))
    models = await fetch_models(
        provider=profile.provider,
        base_url=profile.base_url,
        api_key=profile.api_key,
    )
    if not models:
        print(dim("No models returned from provider (check base URL / API key)."))
        return
    choices = [Choice(value=m, label=m) for m in models]
    picked = await select_option(
        f"Select model  ({profile.name})",
        choices,
        current=resolved.model,
    )
    if picked is None:
        print(dim("cancelled"))
        return
    await cmd_model_use(state, picked)


def cmd_project_show(state: ReplState) -> None:
    print(f"{dim('project')} {state.project_root}")


def cmd_project_set(state: ReplState, path: str) -> None:
    root = str(Path(path).expanduser().resolve())
    if not Path(root).is_dir():
        print(f"Not a directory: {root}")
        return
    storage.set_project_root(state.session_id, state.user_id, root)
    state.project_root = root
    print(f"{accent('ok')} project {root}")


def cmd_clear(state: ReplState, *, quiet: bool = False) -> None:
    title = Path(state.project_root).name or "CLI chat"
    session = storage.create_session(
        state.user_id,
        title=title,
        project_root=state.project_root,
    )
    state.session_id = session["session_id"]
    state.session_started_at = time.monotonic()
    state.session_tokens = 0
    state.last_turn_tokens = 0
    state.last_turn_seconds = 0.0
    state.turns = 0
    if not quiet:
        print()
        print(f"  {accent('ok')} new chat  {dim(state.session_id[:8] + '...')}")
        print()


async def handle_slash(state: ReplState, line: str) -> bool:
    """Handle a slash command. Returns True if the REPL should exit."""
    parts = line.strip().split(maxsplit=1)
    cmd = parts[0].lower()
    arg = parts[1].strip() if len(parts) > 1 else ""

    known = {c for c, _ in SLASH_COMMANDS}
    if cmd.startswith("/") and cmd not in known:
        matches = [c for c, _ in SLASH_COMMANDS if c.startswith(cmd)]
        if len(matches) == 1:
            cmd = matches[0]
        elif len(matches) > 1:
            print(dim(f"ambiguous: {', '.join(matches)}  (use the live / panel)"))
            return False

    if cmd in {"/exit", "/quit", "/q"}:
        return True
    if cmd in {"/help", "/?"}:
        cmd_help()
        return False
    if cmd == "/status":
        print_status(state)
        return False
    if cmd == "/home":
        cmd_home()
        return False
    if cmd in {"/profile", "/provider", "/switch"}:
        if arg:
            await cmd_profile_use(state, arg)
        else:
            await cmd_profile_pick(state)
        return False
    if cmd == "/model":
        if arg:
            await cmd_model_use(state, arg)
        else:
            await cmd_model_pick(state)
        return False
    if cmd == "/project":
        if arg:
            cmd_project_set(state, arg)
        else:
            cmd_project_show(state)
        return False
    if cmd == "/clear":
        cmd_clear(state)
        return False

    print(f"Unknown command: {cmd}  {dim('(try /help)')}")
    return False


def _make_completer():
    from prompt_toolkit.completion import Completer, Completion

    class SlashCompleter(Completer):
        def get_completions(self, document, complete_event):  # noqa: ANN001, ARG002
            text = document.text_before_cursor
            if not text.startswith("/"):
                return
            if " " in text:
                return
            token = text
            needle = token[1:].lower() if len(token) > 1 else ""
            for cmd, desc in SLASH_COMMANDS:
                name = cmd[1:].lower()
                if cmd.startswith(token) or (needle and name.startswith(needle)):
                    yield Completion(
                        cmd,
                        start_position=-len(token),
                        display=cmd,
                        display_meta=desc,
                    )

    return SlashCompleter()


def _make_key_bindings():
    from prompt_toolkit.filters import has_completions
    from prompt_toolkit.key_binding import KeyBindings

    kb = KeyBindings()

    @kb.add("enter", filter=has_completions)
    def _accept_completion(event) -> None:  # noqa: ANN001
        buff = event.current_buffer
        state = buff.complete_state
        if state and state.current_completion:
            buff.apply_completion(state.current_completion)
        buff.validate_and_handle()

    @kb.add("escape", eager=True)
    def _escape(event) -> None:  # noqa: ANN001
        buff = event.current_buffer
        if buff.complete_state:
            buff.cancel_completion()
            return
        if buff.text:
            buff.reset()
            return
        # Idle ESC: ignore (generation ESC handled separately).
        pass

    return kb


def _poll_cancel_key() -> str | None:
    """Non-blocking key read for ESC / Ctrl+C during generation (Windows + POSIX)."""
    try:
        if sys.platform == "win32":
            import msvcrt

            if not msvcrt.kbhit():
                return None
            ch = msvcrt.getwch()
            if ch in ("\x00", "\xe0"):
                msvcrt.getwch()
                return None
            return ch
        import select

        if select.select([sys.stdin], [], [], 0)[0]:
            return sys.stdin.read(1)
    except Exception:  # noqa: BLE001
        return None
    return None


async def _run_with_pulse(state: ReplState, session_id: str, coro):
    """Live pulse + ESC/Ctrl+C cancel while the agent works."""
    from app.agents.chat_loop import chat_loop

    frames = ["|", "/", "-", "\\"]
    stop = asyncio.Event()
    start = time.monotonic()
    state.generating = True

    async def pulse() -> None:
        i = 0
        while not stop.is_set():
            elapsed = format_duration(time.monotonic() - start)
            live = format_duration(time.monotonic() - state.started_at)
            sys.stdout.write(
                f"\r  {accent(frames[i % len(frames)])} "
                f"{dim('forging')} {elapsed}  {dim('|')}  "
                f"{dim('live')} {live}  {dim('|')}  "
                f"{format_tokens(state.session_tokens)} tok  {dim('|')}  "
                f"{dim('esc/ctrl+c stop')}   "
            )
            sys.stdout.flush()
            i += 1
            try:
                await asyncio.wait_for(stop.wait(), timeout=0.08)
            except asyncio.TimeoutError:
                pass

    async def watch_keys() -> None:
        while not stop.is_set():
            key = await asyncio.to_thread(_poll_cancel_key)
            if key in {"\x1b"}:  # ESC
                chat_loop.request_cancel(session_id)
                sys.stdout.write(f"\n  {dim('stopping...')}\n")
                sys.stdout.flush()
                return
            if key in {"\x03"}:  # Ctrl+C
                chat_loop.request_cancel(session_id)
                sys.stdout.write(f"\n  {dim('stopping...')}\n")
                sys.stdout.flush()
                return
            await asyncio.sleep(0.05)

    pulse_task = asyncio.create_task(pulse())
    watch_task = asyncio.create_task(watch_keys())
    try:
        return await coro
    finally:
        stop.set()
        state.generating = False
        for task in (pulse_task, watch_task):
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        sys.stdout.write("\r" + " " * 80 + "\r")
        sys.stdout.flush()
        state.last_turn_seconds = time.monotonic() - start


async def run_repl(state: ReplState) -> None:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.formatted_text import HTML
    from prompt_toolkit.history import FileHistory
    from prompt_toolkit.shortcuts import CompleteStyle
    from prompt_toolkit.styles import Style

    from app.agents.chat_loop import chat_loop

    quiet_logging()
    ensure_utf8_stdio()
    if state.profile:
        set_profile_override(state.profile)
    else:
        active = profile_store.get_active_name()
        if active:
            set_profile_override(active)
            state.profile = active

    refresh_token_stats(state)
    print_banner(state)

    history = FileHistory(str(paths.cli_history_path()))
    pt_style = Style.from_dict(
        {
            "prompt": "#ffaf5f bold",
            "bottom-toolbar": "noreverse #a8b2c0",
            "completion-menu": "bg:#1a1f27 #d6dde8",
            "completion-menu.completion": "bg:#1a1f27 #d6dde8",
            "completion-menu.completion.current": "bg:#4a3728 #ffffff",
            "completion-menu.meta.completion": "bg:#1a1f27 #808080",
            "completion-menu.meta.completion.current": "bg:#4a3728 #ffd7a0",
        }
    )

    def bottom_toolbar():
        resolved = resolve_llm_config(state.profile)
        live = format_duration(time.monotonic() - state.started_at)
        chat = format_duration(time.monotonic() - state.session_started_at)
        used = format_tokens(state.session_tokens)
        limit = format_tokens(state.context_limit)
        model = resolved.model or "-"
        return HTML(
            f"<b>$ {model}</b> | {used}/{limit} | "
            f"live {live} | chat {chat} | "
            f"/ for commands | esc stop | ctrl+c new chat"
        )

    session = PromptSession(
        HTML("<prompt>></prompt> "),
        history=history,
        completer=_make_completer(),
        complete_while_typing=True,
        complete_style=CompleteStyle.COLUMN,
        bottom_toolbar=bottom_toolbar,
        style=pt_style,
        enable_history_search=True,
        key_bindings=_make_key_bindings(),
        refresh_interval=0.5,
    )

    while True:
        try:
            text = (await session.prompt_async()).strip()
            state.ctrl_c_armed_at = None
        except EOFError:
            print()
            break
        except KeyboardInterrupt:
            now = time.monotonic()
            armed = state.ctrl_c_armed_at
            if armed is not None and (now - armed) <= CTRL_C_EXIT_WINDOW:
                print()
                print(dim("  exit"))
                break
            state.ctrl_c_armed_at = now
            cmd_clear(state)
            print(dim("  Ctrl+C again within 2s to exit"))
            print()
            continue

        if not text:
            continue

        if text.startswith("/"):
            if await handle_slash(state, text):
                elapsed = format_duration(time.monotonic() - state.started_at)
                print(dim(f"  until next forge | lived {elapsed} | {format_tokens(state.session_tokens)} tok"))
                break
            continue

        # Claude-like: don't re-box the prompt; just a thin turn divider.
        print()
        rule()
        print()

        before = state.session_tokens
        try:
            result = await _run_with_pulse(
                state,
                state.session_id,
                chat_loop.run(
                    user_id=state.user_id,
                    session_id=state.session_id,
                    content=text,
                ),
            )
        except KeyboardInterrupt:
            chat_loop.request_cancel(state.session_id)
            print(f"\n  {dim('stopped')}")
            print()
            print_status_bar(state)
            print()
            continue
        except Exception as exc:  # noqa: BLE001
            print(f"{_c('error', '31')} {exc}")
            print()
            print_status_bar(state)
            print()
            continue

        content = (result.get("content") or "").strip() or dim("(empty response)")
        cancelled = bool(result.get("cancelled"))
        stats = result.get("stats") or {}
        after = int(stats.get("total_tokens") or 0)
        state.last_turn_tokens = max(0, after - before)
        state.session_tokens = after
        state.turns += 1

        print()
        if cancelled:
            print(f"  {dim('(stopped)')}")
        print(content)
        print()
        rule()
        print_status_bar(state)
        print()
