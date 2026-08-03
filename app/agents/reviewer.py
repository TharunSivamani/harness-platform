from app.agents.base import BaseAgent
from app.schemas.tool_result import ToolResult


class ReviewerAgent(BaseAgent):
    """
    Reviews an upstream agent result and annotates quality.
    """

    async def run(self, user_input: str) -> ToolResult:
        # Placeholder reviewer: score based on non-empty content.
        content = user_input.strip()
        success = bool(content) and "error" not in content.lower()
        notes = []
        if not content:
            notes.append("Empty result.")
        if len(content) < 20:
            notes.append("Result looks too short.")
        if success and not notes:
            notes.append("Looks reasonable.")

        return ToolResult(
            success=success,
            output={
                "approved": success and len(notes) <= 1,
                "notes": notes,
                "reviewed": content[:500],
            },
        )
