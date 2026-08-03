import ast
import operator
import time
from typing import Any

from app.schemas.tool_manifest import ToolManifest
from app.schemas.tool_result import ToolResult
from app.tools.base import BaseTool

manifest = ToolManifest(
    name="python",
    description="Evaluate restricted Python expressions safely.",
    keywords=[
        "python",
        "code",
        "script",
        "eval",
        "execute python",
        "run python",
    ],
)

_BINARY_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

_UNARY_OPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
    ast.Not: operator.not_,
}

_COMPARE_OPS = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
}

_ALLOWED_BUILTINS = {
    "abs": abs,
    "min": min,
    "max": max,
    "sum": sum,
    "len": len,
    "round": round,
    "sorted": sorted,
    "True": True,
    "False": False,
    "None": None,
}


class RestrictedPythonEvaluator(ast.NodeVisitor):
    def evaluate(self, expression: str) -> Any:
        tree = ast.parse(expression, mode="eval")
        return self.visit(tree.body)

    def visit_Expression(self, node: ast.Expression) -> Any:
        return self.visit(node.body)

    def visit_Constant(self, node: ast.Constant) -> Any:
        return node.value

    def visit_List(self, node: ast.List) -> list:
        return [self.visit(elt) for elt in node.elts]

    def visit_Tuple(self, node: ast.Tuple) -> tuple:
        return tuple(self.visit(elt) for elt in node.elts)

    def visit_Set(self, node: ast.Set) -> set:
        return {self.visit(elt) for elt in node.elts}

    def visit_Dict(self, node: ast.Dict) -> dict:
        return {
            self.visit(key): self.visit(value)
            for key, value in zip(node.keys, node.values)
        }

    def visit_UnaryOp(self, node: ast.UnaryOp) -> Any:
        op_type = type(node.op)
        if op_type not in _UNARY_OPS:
            raise ValueError(f"Unary operator not allowed: {op_type.__name__}")
        return _UNARY_OPS[op_type](self.visit(node.operand))

    def visit_BinOp(self, node: ast.BinOp) -> Any:
        op_type = type(node.op)
        if op_type not in _BINARY_OPS:
            raise ValueError(f"Binary operator not allowed: {op_type.__name__}")
        return _BINARY_OPS[op_type](self.visit(node.left), self.visit(node.right))

    def visit_Compare(self, node: ast.Compare) -> Any:
        left = self.visit(node.left)
        for op, comparator in zip(node.ops, node.comparators):
            op_type = type(op)
            if op_type not in _COMPARE_OPS:
                raise ValueError(f"Compare operator not allowed: {op_type.__name__}")
            right = self.visit(comparator)
            if not _COMPARE_OPS[op_type](left, right):
                return False
            left = right
        return True

    def visit_Call(self, node: ast.Call) -> Any:
        if not isinstance(node.func, ast.Name):
            raise ValueError("Only simple function calls are allowed.")

        name = node.func.id
        if name not in _ALLOWED_BUILTINS or not callable(_ALLOWED_BUILTINS[name]):
            raise ValueError(f"Function '{name}' is not allowed.")

        if node.keywords:
            raise ValueError("Keyword arguments are not allowed.")

        args = [self.visit(arg) for arg in node.args]
        return _ALLOWED_BUILTINS[name](*args)

    def visit_Name(self, node: ast.Name) -> Any:
        if node.id in _ALLOWED_BUILTINS:
            return _ALLOWED_BUILTINS[node.id]
        raise ValueError(f"Name '{node.id}' is not allowed.")

    def generic_visit(self, node: ast.AST) -> Any:
        raise ValueError(f"Unsupported expression node: {type(node).__name__}")


class PythonTool(BaseTool):
    manifest = manifest

    async def execute(self, code: str) -> ToolResult:
        start = time.perf_counter()

        try:
            code = code.strip()
            if not code:
                raise ValueError("Code must not be empty.")

            result = RestrictedPythonEvaluator().evaluate(code)

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
