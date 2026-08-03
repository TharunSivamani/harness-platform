from pydantic import BaseModel, Field


class ToolManifest(BaseModel):
    """
    Metadata describing a tool.
    """

    name: str
    description: str
    keywords: list[str]
    priority: int = 100
    permissions: list[str] = Field(default_factory=list)
