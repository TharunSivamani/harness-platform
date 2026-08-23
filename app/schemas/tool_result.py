from typing import Any

from pydantic import BaseModel, Field


class ToolResult(BaseModel):
    """
    Standard response returned by every tool.
    """

    success: bool

    output: Any = None

    error: str | None = None

    execution_time: float = Field(default=0.0, description="Execution time in seconds")

    metadata: dict[str, Any] = Field(default_factory=dict)
