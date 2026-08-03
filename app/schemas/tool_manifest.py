from pydantic import BaseModel


class ToolManifest(BaseModel):
    """
    Metadata describing a tool.
    """

    name: str

    description: str

    keywords: list[str]

    priority: int = 100