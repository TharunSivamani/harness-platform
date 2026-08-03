from __future__ import annotations

import argparse
import asyncio
import json

from app.agents.chat_loop import chat_loop
from app.core.config import settings
from app.storage.db import storage
from app.tools.loader import load_plugins, registry


def cmd_tools(_: argparse.Namespace) -> None:
    load_plugins()
    for tool in registry.discover():
        print(f"{tool.name:16} {tool.description}")


def cmd_sessions(args: argparse.Namespace) -> None:
    user_id = args.user or settings.DEFAULT_USER_ID
    storage.ensure_default_user()
    for session in storage.list_sessions(user_id):
        print(f"{session['session_id']}  {session['title']}")


async def _chat(args: argparse.Namespace) -> None:
    storage.ensure_default_user()
    user_id = args.user or settings.DEFAULT_USER_ID
    if args.session:
        session_id = args.session
    else:
        session = storage.create_session(user_id, title=(args.message or "CLI chat")[:48])
        session_id = session["session_id"]
        print(f"session {session_id}")

    if args.message:
        result = await chat_loop.run(
            user_id=user_id,
            session_id=session_id,
            content=args.message,
        )
        print(result["content"])
        print(json.dumps(result["stats"], indent=2))
        return

    print(f"ForgeAI CLI · home={settings.forge_home} · session={session_id}")
    print("Type /exit to quit.")
    while True:
        try:
            text = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not text:
            continue
        if text in {"/exit", "/quit"}:
            break
        result = await chat_loop.run(
            user_id=user_id,
            session_id=session_id,
            content=text,
        )
        print(f"forge> {result['content']}")


def cmd_chat(args: argparse.Namespace) -> None:
    asyncio.run(_chat(args))


def cmd_whoami(args: argparse.Namespace) -> None:
    user_id = args.user or settings.DEFAULT_USER_ID
    user = storage.get_user(user_id) or storage.ensure_default_user()
    stats = storage.user_stats(user["user_id"])
    print(json.dumps({**user, "stats": stats, "forge_home": str(settings.forge_home)}, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(prog="forge", description="ForgeAI CLI")
    parser.add_argument("--user", default=None, help="Soft local user id")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("tools", help="List autodiscovered tools")
    sub.add_parser("sessions", help="List sessions")
    sub.add_parser("whoami", help="Show current user + token stats")

    chat = sub.add_parser("chat", help="Interactive or one-shot chat loop")
    chat.add_argument("message", nargs="?", help="Optional one-shot message")
    chat.add_argument("--session", help="Existing session id")

    args = parser.parse_args()
    command = args.command or "chat"
    if command == "tools":
        cmd_tools(args)
    elif command == "sessions":
        cmd_sessions(args)
    elif command == "whoami":
        cmd_whoami(args)
    elif command == "chat":
        if not hasattr(args, "message"):
            args.message = None
        if not hasattr(args, "session"):
            args.session = None
        cmd_chat(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
