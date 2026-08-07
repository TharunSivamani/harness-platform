"""
Calculator tool with safe AST-based expression evaluation.

SECURITY: Uses RestrictedMathEvaluator (AST whitelist) instead of eval()
to prevent arbitrary code execution via malicious expressions like
`__import__('os').system('rm -rf /')`.
"""

import ast
import math
import operator
import time
from typing import Any

from app.schemas.tool_manifest import ToolManifest
from app.schemas.tool_result import ToolResult
from app.tools.base import BaseTool

manifest = ToolManifest(
    name="calculator",
    description="Evaluate a math expression and return the numeric result (e.g. 2+2, 3*7, (10-3)/2, sqrt(16), sin(pi/2)).",
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
    permissions=["calculator.execute"],
    parameters={
        "type": "object",
        "properties": {
            "expression": {
                "type": "string",
                "description": "Arithmetic expression to evaluate (supports +, -, *, /, **, %, //, sqrt, sin, cos, tan, log, abs, round, min, max, pi, e)",
            },
        },
        "required": ["expression"],
        "additionalProperties": False,
    },
)

# Supported binary operators
_BINARY_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

# Supported unary operators
_UNARY_OPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}

# Supported comparison operators
_COMPARE_OPS = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
}

# Safe math functions and constants
_ALLOWED_NAMES: dict[str, Any] = {
    # Constants
    "pi": math.pi,
    "e": math.e,
    "tau": math.tau,
    "inf": math.inf,
    # Boolean/None
    "True": True,
    "False": False,
    "None": None,
}

_ALLOWED_FUNCS: dict[str, Any] = {
    # Basic math
    "abs": abs,
    "round": round,
    "min": min,
    "max": max,
    "sum": sum,
    "pow": pow,
    # Roots and logarithms
    "sqrt": math.sqrt,
    "log": math.log,
    "log10": math.log10,
    "log2": math.log2,
    "exp": math.exp,
    # Trigonometry
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "asin": math.asin,
    "acos": math.acos,
    "atan": math.atan,
    "atan2": math.atan2,
    # Hyperbolic
    "sinh": math.sinh,
    "cosh": math.cosh,
    "tanh": math.tanh,
    # Rounding
    "ceil": math.ceil,
    "floor": math.floor,
    "trunc": math.trunc,
    # Other
    "factorial": math.factorial,
    "gcd": math.gcd,
    "degrees": math.degrees,
    "radians": math.radians,
}


class RestrictedMathEvaluator(ast.NodeVisitor):
    """
    Safe math expression evaluator using AST whitelisting.
    
    Only allows:
    - Numeric literals (int, float, complex)
    - Basic arithmetic operators (+, -, *, /, //, %, **)
    - Comparison operators (==, !=, <, <=, >, >=)
    - Whitelisted math functions (sqrt, sin, cos, etc.)
    - Whitelisted constants (pi, e, tau)
    - Lists, tuples for function args like min([1,2,3])
    """
    
    def evaluate(self, expression: str) -> Any:
        """Parse and evaluate a math expression safely."""
        try:
            tree = ast.parse(expression, mode="eval")
        except SyntaxError as e:
            raise ValueError(f"Invalid expression syntax: {e}") from e
        return self.visit(tree.body)
    
    def visit_Expression(self, node: ast.Expression) -> Any:
        return self.visit(node.body)
    
    def visit_Constant(self, node: ast.Constant) -> Any:
        """Allow numeric literals and strings (for error messages)."""
        if isinstance(node.value, (int, float, complex, bool, type(None))):
            return node.value
        raise ValueError(f"Constant type not allowed: {type(node.value).__name__}")
    
    def visit_Num(self, node: ast.Num) -> Any:
        """Python 3.7 compatibility for numeric literals."""
        return node.n
    
    def visit_List(self, node: ast.List) -> list:
        return [self.visit(elt) for elt in node.elts]
    
    def visit_Tuple(self, node: ast.Tuple) -> tuple:
        return tuple(self.visit(elt) for elt in node.elts)
    
    def visit_UnaryOp(self, node: ast.UnaryOp) -> Any:
        op_type = type(node.op)
        if op_type not in _UNARY_OPS:
            raise ValueError(f"Unary operator not allowed: {op_type.__name__}")
        return _UNARY_OPS[op_type](self.visit(node.operand))
    
    def visit_BinOp(self, node: ast.BinOp) -> Any:
        op_type = type(node.op)
        if op_type not in _BINARY_OPS:
            raise ValueError(f"Binary operator not allowed: {op_type.__name__}")
        left = self.visit(node.left)
        right = self.visit(node.right)
        return _BINARY_OPS[op_type](left, right)
    
    def visit_Compare(self, node: ast.Compare) -> Any:
        left = self.visit(node.left)
        for op, comparator in zip(node.ops, node.comparators):
            op_type = type(op)
            if op_type not in _COMPARE_OPS:
                raise ValueError(f"Comparison operator not allowed: {op_type.__name__}")
            right = self.visit(comparator)
            if not _COMPARE_OPS[op_type](left, right):
                return False
            left = right
        return True
    
    def visit_Call(self, node: ast.Call) -> Any:
        if not isinstance(node.func, ast.Name):
            raise ValueError("Only simple function calls are allowed (no method calls).")
        
        func_name = node.func.id
        if func_name not in _ALLOWED_FUNCS:
            raise ValueError(
                f"Function '{func_name}' is not allowed. "
                f"Allowed: {', '.join(sorted(_ALLOWED_FUNCS.keys()))}"
            )
        
        if node.keywords:
            raise ValueError("Keyword arguments are not allowed in calculator expressions.")
        
        args = [self.visit(arg) for arg in node.args]
        return _ALLOWED_FUNCS[func_name](*args)
    
    def visit_Name(self, node: ast.Name) -> Any:
        name = node.id
        if name in _ALLOWED_NAMES:
            return _ALLOWED_NAMES[name]
        if name in _ALLOWED_FUNCS:
            # Allow referencing function names (for cases like passing to higher-order funcs)
            return _ALLOWED_FUNCS[name]
        raise ValueError(
            f"Name '{name}' is not allowed. "
            f"Allowed constants: {', '.join(sorted(_ALLOWED_NAMES.keys()))}"
        )
    
    def visit_IfExp(self, node: ast.IfExp) -> Any:
        """Allow ternary expressions: x if condition else y"""
        condition = self.visit(node.test)
        if condition:
            return self.visit(node.body)
        return self.visit(node.orelse)
    
    def generic_visit(self, node: ast.AST) -> Any:
        raise ValueError(
            f"Expression node type not allowed: {type(node).__name__}. "
            "Only arithmetic expressions with whitelisted functions are permitted."
        )


# Singleton evaluator instance
_evaluator = RestrictedMathEvaluator()


class CalculatorTool(BaseTool):
    manifest = manifest

    async def execute(self, expression: str) -> ToolResult:
        start = time.perf_counter()

        try:
            expression = (expression or "").strip()
            if not expression:
                raise ValueError("Expression must not be empty.")
            
            # Use safe AST-based evaluation instead of eval()
            result = _evaluator.evaluate(expression)

            return ToolResult(
                success=True,
                output=result,
                execution_time=time.perf_counter() - start,
                metadata={"expression": expression, "evaluator": "restricted-ast"},
            )

        except Exception as e:
            return ToolResult(
                success=False,
                error=str(e),
                execution_time=time.perf_counter() - start,
                metadata={"expression": expression},
            )
