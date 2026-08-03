import time

from app.schemas.tool_result import ToolResult
from app.tools.base import BaseTool


class CalculatorTool(BaseTool):

    name = "calculator"

    description = "Evaluate mathematical expressions."

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