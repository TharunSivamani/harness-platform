from typing import Any

from pydantic import BaseModel, Field


class ToolManifest(BaseModel):
    """
    Metadata describing a tool, including OpenAI-compatible JSON Schema parameters.
    """

    name: str
    description: str
    keywords: list[str]
    priority: int = 100
    permissions: list[str] = Field(default_factory=list)
    parameters: dict[str, Any] = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        }
    )

    def openai_tool(self) -> dict[str, Any]:
        """Function-calling payload for OpenAI / Ollama / vLLM."""
        schema = dict(self.parameters or {})
        schema.setdefault("type", "object")
        schema.setdefault("properties", {})
        if "additionalProperties" not in schema:
            schema["additionalProperties"] = False
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": schema,
            },
        }
