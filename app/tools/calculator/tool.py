import time

from app.schemas.tool_manifest import ToolManifest
from app.schemas.tool_result import ToolResult
from app.tools.base import BaseTool

manifest = ToolManifest(
    name="calculator",
    description="Performs mathematical calculations.",
    keywords=[
        "calculate",
        "math",
        "multiply",
        "divide",
        "add",
        "subtract",
        "equation",
        "expression",
    ],
)


class CalculatorTool(BaseTool):
    manifest = manifest

    async def execute(self, expression: str) -> ToolResult:
        start = time.perf_counter()

        try:
            result = eval(expression)

            return ToolResult(
                success=True,
                output=result,
                execution_time=time.perf_counter() - start,
            )

        except Exception as e:
            return ToolResult(
                success=False,
                error=str(e),
                execution_time=time.perf_counter() - start,
            )
