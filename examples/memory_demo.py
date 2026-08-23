from app.memory.session import session_manager
from app.memory.system import memory_system


def main():
    session = session_manager.create()
    session_manager.add_message(session.session_id, "user", "My favorite language is Python")
    session_manager.add_message(session.session_id, "assistant", "Noted.")

    memory_system.remember("User prefers Python", tags=["preference", "python"])
    hits = memory_system.recall("python preference")
    summary = memory_system.summarize_session(session.session_id)

    print("session:", session.session_id)
    print("recall:", [item.content for item in hits])
    print("summary:", summary)


if __name__ == "__main__":
    main()
