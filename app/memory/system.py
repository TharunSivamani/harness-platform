from app.memory.long_term import LongTermMemory, long_term_memory
from app.memory.session import SessionManager, session_manager


class MemorySystem:
    """
    Facade over short-term session memory and long-term memory.
    """

    def __init__(
        self,
        sessions: SessionManager | None = None,
        long_term: LongTermMemory | None = None,
    ):
        self.sessions = sessions or session_manager
        self.long_term = long_term or long_term_memory

    def remember(self, content: str, tags: list[str] | None = None):
        return self.long_term.store(content=content, tags=tags)

    def recall(self, query: str, limit: int = 5):
        return self.long_term.retrieve(query=query, limit=limit)

    def summarize_session(self, session_id: str, max_messages: int = 20) -> str:
        messages = self.sessions.history(session_id, limit=max_messages)
        if not messages:
            summary = "No conversation history."
        else:
            lines = [f"{message.role}: {message.content}" for message in messages]
            summary = " | ".join(lines)
            if len(summary) > 1000:
                summary = summary[:997] + "..."

        session = self.sessions.get(session_id)
        session.summary = summary
        self.long_term.store(
            content=summary,
            tags=["summary", session_id],
            metadata={"session_id": session_id},
        )
        return summary


memory_system = MemorySystem()
