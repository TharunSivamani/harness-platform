from app.tools.base import BaseTool


class CalculatorTool(BaseTool):

    name = "calculator"

    description = "Evaluate mathematical expressions."

    async def execute(self, expression: str):

        try:
            return eval(expression)

        except Exception as e:
            return str(e)