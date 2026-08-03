from app.tools.registry import ToolRegistry
from app.tools.calculator import CalculatorTool

registry = ToolRegistry()

registry.register(CalculatorTool())