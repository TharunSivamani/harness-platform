from __future__ import annotations

import asyncio
import logging
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from app.cli.select import Choice, select_option
from app.llm.profiles import (
    fetch_models,
    profile_store,
    resolve_llm_config,
    set_profile_override,
)
from app.storage.db import storage
from app.storage.paths import paths


# ── slash catalogue (completer + help share this) ──────────────────────────

SLASH_COMMANDS: list[tuple[str, str]] = [
    ("/help", "Show all commands"),
    ("/status", "Profile, model, timer, tokens"),
    ("/profile", "Switch LLM profile (picker)"),
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
    turns: int = 0


def quiet_logging() -> None:
    """Silence plugin registration noise during interactive chat."""
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


def ember(text: str) -> str:
    return _c(text, "38;5;216")


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
        return f"{n / 1_000_000:.1f}M"
    if n >= 10_000:
        return f"{n / 1_000:.1f}k"
    if n >= 1_000:
        return f"{n / 1_000:.2f}k".rstrip("0").rstrip(".")
    return str(n)


def refresh_token_stats(state: ReplState) -> None:
    stats = storage.session_stats(state.session_id)
    state.session_tokens = int(stats.get("total_tokens") or 0)


def status_line(state: ReplState, *, turn_tokens: int | None = None) -> str:
    resolved = resolve_llm_config(state.profile)
    elapsed = format_duration(time.monotonic() - state.started_at)
    sess = format_duration(time.monotonic() - state.session_started_at)
    turn = state.last_turn_tokens if turn_tokens is None else turn_tokens
    bits = [
        f"{accent('live')} {elapsed}",
        f"chat {sess}",
        f"turn +{format_tokens(turn)}" if turn else "turn -",
        f"session {format_tokens(state.session_tokens)} tok",
        f"{resolved.profile_name or 'env'}/{resolved.model or '-'}",
    ]
    return dim("  " + "  |  ".join(bits))


def print_banner(state: ReplState) -> None:
    resolved = resolve_llm_config(state.profile)
    profile = resolved.profile_name or "(env)"
    model = resolved.model or "-"
    provider = resolved.provider
    project = state.project_root
    width = 54
    top = "+" + ("-" * width) + "+"
    print()
    print(f"  {accent(top)}")
    print(f"  {accent('|')}  ForgeAI  agent cli" + " " * (width - 20) + accent("|"))
    print(f"  {accent('|')}  {dim('profile')}  {profile[:44]:<44}{accent('|')}")
    print(
        f"  {accent('|')}  {dim('model')}    "
        f"{(provider + '/' + model)[:44]:<44}{accent('|')}"
    )
    short_proj = project if len(project) <= 44 else "..." + project[-41:]
    print(f"  {accent('|')}  {dim('project')}  {short_proj:<44}{accent('|')}")
    print(
        f"  {accent('|')}  {dim('session')}  "
        f"{(state.session_id[:8] + '...'):<44}{accent('|')}"
    )
    cfg = str(paths.config_home())
    short_cfg = cfg if len(cfg) <= 44 else "..." + cfg[-41:]
    print(f"  {accent('|')}  {dim('config')}   {short_cfg:<44}{accent('|')}")
    print(f"  {accent('+' + ('-' * width) + '+')}")
    print(
        f"  {dim('type')} {accent('/')} "
        f"{dim('for commands | tab complete | /ex expands to /exit')}"
    )
    print()
    print(status_line(state))
    print()


def print_status(state: ReplState) -> None:
    refresh_token_stats(state)
    resolved = resolve_llm_config(state.profile)
    print()
    print(f"  {bold('status')}")
    print(f"  {dim('profile')}   {resolved.profile_name or '-'} ({resolved.provider})")
    print(f"  {dim('model')}     {resolved.model}")
    print(f"  {dim('project')}   {state.project_root}")
    print(f"  {dim('session')}   {state.session_id}")
    print(f"  {dim('config')}    {paths.config_home()}")
    print(f"  {dim('live')}      {format_duration(time.monotonic() - state.started_at)}")
    print(
        f"  {dim('chat')}      "
        f"{format_duration(time.monotonic() - state.session_started_at)}  "
        f"({state.turns} turns)"
    )
    print(
        f"  {dim('tokens')}    "
        f"session {format_tokens(state.session_tokens)}  "
        f"last turn +{format_tokens(state.last_turn_tokens)}"
    )
    print()


def cmd_help() -> None:
    print()
    print(f"  {bold(ember('commands'))}")
    for cmd, desc in SLASH_COMMANDS:
        print(f"  {accent(cmd):<22} {dim(desc)}")
    print()
    print(f"  {dim('tip')} start typing {accent('/')} then Tab — or keep typing to filter ({accent('/ex')} → {accent('/exit')})")
    print()


def cmd_home() -> None:
    print(f"{dim('config')} {paths.config_home()}")
    print(f"{dim('llm')}    {paths.llm_dir()}")
    print(f"{dim('secrets')} {paths.llm_secrets_path()}")


def cmd_profile_use(state: ReplState, name: str) -> None:
    name = name.strip()
    if not profile_store.get_profile(name):
        print(f"Profile not found: {name}")
        cmd_profile_pick(state)
        return
    profile_store.set_active(name)
    set_profile_override(name)
    state.profile = name
    resolved = resolve_llm_config(name)
    print(
        f"{accent('ok')} profile {bold(name)}  "
        f"{dim(f'{resolved.provider}/{resolved.model}')}"
    )


def cmd_profile_pick(state: ReplState) -> None:
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
    picked = select_option("Select profile", choices, current=active)
    if picked is None:
        print(dim("cancelled"))
        return
    cmd_profile_use(state, picked)


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
    picked = select_option(
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


def cmd_clear(state: ReplState) -> None:
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
    state.turns = 0
    print(f"{accent('ok')} new session {state.session_id[:8]}...")
    print(status_line(state))


async def handle_slash(state: ReplState, line: str) -> bool:
    """Handle a slash command. Returns True if the REPL should exit."""
    parts = line.strip().split(maxsplit=1)
    cmd = parts[0].lower()
    arg = parts[1].strip() if len(parts) > 1 else ""

    # Prefix resolve: /ex → /exit when unambiguous
    if cmd.startswith("/") and cmd not in {c for c, _ in SLASH_COMMANDS}:
        matches = [c for c, _ in SLASH_COMMANDS if c.startswith(cmd)]
        if len(matches) == 1:
            cmd = matches[0]
        elif len(matches) > 1:
            print(dim(f"ambiguous: {', '.join(matches)}"))
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
    if cmd == "/profile":
        if arg:
            cmd_profile_use(state, arg)
        else:
            cmd_profile_pick(state)
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
            if " " in text.strip():
                return
            token = text.split()[0] if text.split() else text
            for cmd, desc in SLASH_COMMANDS:
                if cmd.startswith(token):
                    yield Completion(
                        cmd,
                        start_position=-len(token),
                        display=cmd,
                        display_meta=desc,
                    )

    return SlashCompleter()


async def _prompt_line(session) -> str:  # noqa: ANN001
    try:
        return await session.prompt_async()
    except EOFError:
        return "/exit"
    except KeyboardInterrupt:
        return ""


async def _run_with_pulse(state: ReplState, coro):
    """Show a live elapsed pulse while the agent works."""
    frames = ["|", "/", "-", "\\"]
    stop = asyncio.Event()
    start = time.monotonic()

    async def pulse() -> None:
        i = 0
        while not stop.is_set():
            elapsed = format_duration(time.monotonic() - start)
            live = format_duration(time.monotonic() - state.started_at)
            sys.stdout.write(
                f"\r  {accent(frames[i % len(frames)])} "
                f"{dim('forging')} {elapsed}  {dim('|')}  "
                f"{dim('session')} {live}  {dim('|')}  "
                f"{format_tokens(state.session_tokens)} tok   "
            )
            sys.stdout.flush()
            i += 1
            try:
                await asyncio.wait_for(stop.wait(), timeout=0.08)
            except asyncio.TimeoutError:
                pass

    task = asyncio.create_task(pulse())
    try:
        return await coro
    finally:
        stop.set()
        await task
        sys.stdout.write("\r" + " " * 72 + "\r")
        sys.stdout.flush()


async def run_repl(state: ReplState) -> None:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.formatted_text import HTML
    from prompt_toolkit.history import FileHistory
    from prompt_toolkit.styles import Style

    from app.agents.chat_loop import chat_loop

    quiet_logging()
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
            "bottom-toolbar": "#808080",
        }
    )

    def bottom_toolbar():
        resolved = resolve_llm_config(state.profile)
        live = format_duration(time.monotonic() - state.started_at)
        return HTML(
            f"<b>{live}</b> | "
            f"session {format_tokens(state.session_tokens)} tok | "
            f"{resolved.profile_name or 'env'}/{resolved.model or '-'} | "
            f"/help"
        )

    session = PromptSession(
        HTML("<prompt>forge</prompt><prompt> > </prompt>"),
        history=history,
        completer=_make_completer(),
        complete_while_typing=True,
        bottom_toolbar=bottom_toolbar,
        style=pt_style,
        enable_history_search=True,
    )

    while True:
        try:
            text = (await _prompt_line(session)).strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not text:
            continue
        if text.startswith("/"):
            if await handle_slash(state, text):
                elapsed = format_duration(time.monotonic() - state.started_at)
                print(dim(f"  until next forge | lived {elapsed} | {format_tokens(state.session_tokens)} tok"))
                break
            continue

        before = state.session_tokens
        try:
            result = await _run_with_pulse(
                state,
                chat_loop.run(
                    user_id=state.user_id,
                    session_id=state.session_id,
                    content=text,
                ),
            )
        except Exception as exc:  # noqa: BLE001
            print(f"{_c('error', '31')} {exc}")
            continue

        content = (result.get("content") or "").strip() or dim("(empty response)")
        stats = result.get("stats") or {}
        after = int(stats.get("total_tokens") or 0)
        state.last_turn_tokens = max(0, after - before)
        state.session_tokens = after
        state.turns += 1

        print()
        print(content)
        print()
        print(status_line(state))
        print()
