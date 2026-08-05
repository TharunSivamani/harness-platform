from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from app.core.config import settings
from app.llm.profiles import (
    PROVIDERS,
    LLMProfile,
    default_base_url,
    fetch_models,
    profile_public,
    profile_store,
    prompt_secret,
    resolve_llm_config,
    set_profile_override,
)
from app.storage.db import storage
from app.tools.loader import load_plugins, registry


def _resolve_project(explicit: str | None) -> str:
    if explicit:
        return str(Path(explicit).expanduser().resolve())
    if settings.DEFAULT_PROJECT_ROOT:
        return str(Path(settings.DEFAULT_PROJECT_ROOT).expanduser().resolve())
    return str(Path.cwd().resolve())


def _prompt(label: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{label}{suffix}: ").strip()
    if value:
        return value
    return default or ""


def cmd_tools(_: argparse.Namespace) -> None:
    load_plugins()
    for tool in registry.discover():
        print(f"{tool.name:16} {tool.description}")


def cmd_sessions(args: argparse.Namespace) -> None:
    user_id = args.user or settings.DEFAULT_USER_ID
    storage.ensure_default_user()
    for session in storage.list_sessions(user_id):
        root = session.get("project_root") or "-"
        print(f"{session['session_id']}  {session['title']}  project={root}")


async def _chat(args: argparse.Namespace) -> None:
    from app.cli.repl import ReplState, quiet_logging, run_repl

    quiet_logging()
    storage.ensure_default_user()
    user_id = args.user or settings.DEFAULT_USER_ID
    project_root = _resolve_project(args.project)
    if getattr(args, "profile", None):
        set_profile_override(args.profile)
    resolved = resolve_llm_config(args.profile)

    if args.session:
        session_id = args.session
        session = storage.get_session(session_id)
        if not session or session["user_id"] != user_id:
            raise SystemExit(f"Session not found: {session_id}")
        if project_root and session.get("project_root") != project_root:
            storage.set_project_root(session_id, user_id, project_root)
    else:
        title = (args.message or Path(project_root).name or "CLI chat")[:48]
        session = storage.create_session(
            user_id,
            title=title,
            project_root=project_root,
        )
        session_id = session["session_id"]

    state = ReplState(
        user_id=user_id,
        session_id=session_id,
        project_root=project_root,
        profile=getattr(args, "profile", None) or resolved.profile_name,
    )

    if args.message:
        from app.agents.chat_loop import chat_loop

        if state.profile:
            set_profile_override(state.profile)
        result = await chat_loop.run(
            user_id=user_id,
            session_id=session_id,
            content=args.message,
        )
        print(result["content"])
        return

    await run_repl(state)


def cmd_chat(args: argparse.Namespace) -> None:
    asyncio.run(_chat(args))


def cmd_whoami(args: argparse.Namespace) -> None:
    from app.runtime.sandbox import sandbox_manager

    user_id = args.user or settings.DEFAULT_USER_ID
    user = storage.get_user(user_id) or storage.ensure_default_user()
    stats = storage.user_stats(user["user_id"])
    resolved = resolve_llm_config()
    print(
        json.dumps(
            {
                **user,
                "stats": stats,
                "forge_home": str(settings.forge_home),
                "forgeai_config": str(settings.forgeai_config_home),
                "cwd": str(Path.cwd().resolve()),
                "llm": {
                    "profile": resolved.profile_name,
                    "provider": resolved.provider,
                    "model": resolved.model,
                    "base_url": resolved.base_url,
                },
                "sandbox": {
                    "configured": settings.SANDBOX_BACKEND,
                    "effective": sandbox_manager.resolve_backend(),
                    "docker_available": sandbox_manager.docker_available(),
                },
            },
            indent=2,
        )
    )


def cmd_project(args: argparse.Namespace) -> None:
    user_id = args.user or settings.DEFAULT_USER_ID
    storage.ensure_default_user()
    root = _resolve_project(args.path)
    updated = storage.set_project_root(args.session, user_id, root)
    print(json.dumps(updated, indent=2))


async def _setup_async(args: argparse.Namespace) -> None:
    if args.non_interactive:
        if not args.name or not args.provider:
            raise SystemExit("--name and --provider are required in non-interactive mode")
        provider = args.provider.lower().strip()
        if provider not in PROVIDERS:
            raise SystemExit(f"provider must be one of: {', '.join(PROVIDERS)}")
        base_url = args.base_url or default_base_url(provider)
        model = args.model
        if not model and base_url:
            models = await fetch_models(
                provider=provider,
                base_url=base_url,
                api_key=args.api_key,
            )
            model = models[0] if models else settings.MODEL_NAME
        profile = LLMProfile(
            name=args.name,
            provider=provider,
            base_url=base_url,
            api_key=args.api_key,
            model=model or settings.MODEL_NAME,
        )
        saved = profile_store.upsert_profile(profile, activate=True)
        print(json.dumps(profile_public(saved), indent=2))
        print(f"Active profile set to '{saved.name}'")
        return

    print("ForgeAI LLM profile setup")
    print(f"Profiles are stored under {paths_llm_hint()}")
    name = _prompt("Profile name", "default")
    provider = _prompt(
        f"Provider ({', '.join(PROVIDERS)})",
        "ollama",
    ).lower()
    if provider not in PROVIDERS:
        raise SystemExit(f"Unknown provider. Choose: {', '.join(PROVIDERS)}")

    base_default = default_base_url(provider)
    base_url = _prompt("Base URL", base_default or "")
    api_key = None
    if provider in {"openai", "anthropic", "vllm", "openai_compatible"}:
        api_key = prompt_secret("API key")
    elif provider == "ollama":
        # Optional for remote Ollama proxies
        maybe = _prompt("API key (optional)", "")
        api_key = maybe or None

    print("Fetching models…")
    models = await fetch_models(provider=provider, base_url=base_url or None, api_key=api_key)
    model = args.model
    if models:
        print("Available models:")
        for index, item in enumerate(models[:40], start=1):
            print(f"  {index}. {item}")
        if len(models) > 40:
            print(f"  … {len(models) - 40} more")
        choice = _prompt("Model name or number", "1" if models else settings.MODEL_NAME)
        if choice.isdigit() and 1 <= int(choice) <= len(models):
            model = models[int(choice) - 1]
        else:
            model = choice or models[0]
    else:
        print("Could not autofetch models; enter a model id manually.")
        model = _prompt("Model", settings.MODEL_NAME)

    profile = LLMProfile(
        name=name,
        provider=provider,
        base_url=base_url or None,
        api_key=api_key,
        model=model,
    )
    saved = profile_store.upsert_profile(profile, activate=True)
    print(json.dumps(profile_public(saved), indent=2))
    print(f"Active profile set to '{saved.name}'")


def paths_llm_hint() -> str:
    from app.storage.paths import paths

    return str(paths.llm_dir())


def cmd_setup(args: argparse.Namespace) -> None:
    asyncio.run(_setup_async(args))


def cmd_profile(args: argparse.Namespace) -> None:
    action = args.profile_command
    if action == "list":
        active = profile_store.get_active_name()
        items = profile_store.list_profiles()
        if not items:
            print("No profiles. Run: forge setup")
            return
        for profile in items:
            mark = "*" if profile.name == active else " "
            print(
                f"{mark} {profile.name:20} {profile.provider:18} {profile.model or '-'}  {profile.base_url or '-'}"
            )
        return

    if action == "use":
        profile_store.set_active(args.name)
        print(f"Active profile: {args.name}")
        return

    if action == "show":
        name = args.name or profile_store.get_active_name()
        if not name:
            raise SystemExit("No active profile")
        profile = profile_store.get_profile(name)
        if not profile:
            raise SystemExit(f"Profile '{name}' not found")
        print(json.dumps(profile_public(profile), indent=2))
        return

    if action == "delete":
        if not profile_store.delete_profile(args.name):
            raise SystemExit(f"Profile '{args.name}' not found")
        print(f"Deleted profile '{args.name}'")
        return

    if action == "models":
        name = args.name or profile_store.get_active_name()
        if not name:
            raise SystemExit("No profile specified")
        profile = profile_store.get_profile(name)
        if not profile:
            raise SystemExit(f"Profile '{name}' not found")

        async def _run():
            return await fetch_models(
                provider=profile.provider,
                base_url=profile.base_url,
                api_key=profile.api_key,
            )

        models = asyncio.run(_run())
        if not models:
            print("No models returned (endpoint unreachable or unsupported).")
            return
        for item in models:
            print(item)
        return

    raise SystemExit("Unknown profile command")


def main(argv: list[str] | None = None) -> None:
    # Support aliases: forge --setup, forge --webui, forgeai ui
    import sys

    raw = list(argv) if argv is not None else sys.argv[1:]
    if raw and raw[0] == "--setup":
        raw = ["setup", *raw[1:]]
    if raw and raw[0] in {"--webui", "--ui"}:
        raw = ["ui", *raw[1:]]

    prog = Path(sys.argv[0]).stem if argv is None else "forge"
    if prog.lower() in {"forgeai", "forge-ai"}:
        prog = "forgeai"
    else:
        prog = "forge"

    parser = argparse.ArgumentParser(prog=prog, description="ForgeAI CLI")
    parser.add_argument("--user", default=None, help="Soft local user id")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("tools", help="List autodiscovered tools")
    sub.add_parser("sessions", help="List sessions")
    sub.add_parser("whoami", help="Show current user + LLM profile + sandbox")

    setup = sub.add_parser("setup", help="Create/update an LLM profile under ~/.forgeai")
    setup.add_argument("--non-interactive", action="store_true")
    setup.add_argument("--name")
    setup.add_argument("--provider", choices=list(PROVIDERS))
    setup.add_argument("--base-url")
    setup.add_argument("--api-key")
    setup.add_argument("--model")

    profile = sub.add_parser("profile", help="Manage LLM profiles")
    profile_sub = profile.add_subparsers(dest="profile_command")
    profile_sub.add_parser("list", help="List profiles")
    use = profile_sub.add_parser("use", help="Activate a profile")
    use.add_argument("name")
    show = profile_sub.add_parser("show", help="Show a profile (masked key)")
    show.add_argument("name", nargs="?")
    delete = profile_sub.add_parser("delete", help="Delete a profile")
    delete.add_argument("name")
    models = profile_sub.add_parser("models", help="Fetch models for a profile")
    models.add_argument("name", nargs="?")

    ui = sub.add_parser("ui", help="Launch API + Web UI (alias: --webui)")
    ui.add_argument("--api-host", default="127.0.0.1")
    ui.add_argument("--api-port", type=int, default=8000)
    ui.add_argument("--ui-host", default="127.0.0.1")
    ui.add_argument("--ui-port", type=int, default=3000)
    ui.add_argument("--no-browser", action="store_true", help="Do not open a browser tab")
    ui.add_argument(
        "--no-install",
        action="store_true",
        help="Skip npm install even when node_modules is missing",
    )

    chat = sub.add_parser("chat", help="Interactive or one-shot chat loop")
    chat.add_argument("message", nargs="?", help="Optional one-shot message")
    chat.add_argument("--session", help="Existing session id")
    chat.add_argument(
        "--project",
        default=None,
        help="Project root on disk (default: current working directory)",
    )
    chat.add_argument("--profile", default=None, help="LLM profile for this run")

    project = sub.add_parser("project", help="Bind a session to a project folder")
    project.add_argument("--session", required=True, help="Session id")
    project.add_argument(
        "path",
        nargs="?",
        default=None,
        help="Folder path (default: cwd)",
    )

    args = parser.parse_args(raw)
    command = args.command or "chat"
    if command == "tools":
        cmd_tools(args)
    elif command == "sessions":
        cmd_sessions(args)
    elif command == "whoami":
        cmd_whoami(args)
    elif command == "setup":
        cmd_setup(args)
    elif command == "profile":
        if not getattr(args, "profile_command", None):
            profile.print_help()
            raise SystemExit(2)
        cmd_profile(args)
    elif command == "project":
        cmd_project(args)
    elif command in {"ui", "webui"}:
        from app.cli.webui import cmd_ui

        cmd_ui(args)
    elif command == "chat":
        if not hasattr(args, "message"):
            args.message = None
        if not hasattr(args, "session"):
            args.session = None
        if not hasattr(args, "project"):
            args.project = None
        if not hasattr(args, "profile"):
            args.profile = None
        cmd_chat(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
