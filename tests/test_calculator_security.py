"""
Security tests for the calculator tool.

These tests verify that the calculator uses safe AST-based evaluation
and does NOT allow arbitrary code execution via eval().
"""

import pytest

from app.tools.calculator.tool import CalculatorTool, RestrictedMathEvaluator


class TestRestrictedMathEvaluator:
    """Test the AST-based math evaluator."""

    def setup_method(self):
        self.evaluator = RestrictedMathEvaluator()

    def test_basic_arithmetic(self):
        """Test basic math operations work."""
        assert self.evaluator.evaluate("2 + 2") == 4
        assert self.evaluator.evaluate("10 - 3") == 7
        assert self.evaluator.evaluate("6 * 7") == 42
        assert self.evaluator.evaluate("15 / 3") == 5.0
        assert self.evaluator.evaluate("2 ** 10") == 1024
        assert self.evaluator.evaluate("17 % 5") == 2
        assert self.evaluator.evaluate("17 // 5") == 3

    def test_math_functions(self):
        """Test allowed math functions."""
        assert self.evaluator.evaluate("abs(-5)") == 5
        assert self.evaluator.evaluate("min(1, 2, 3)") == 1
        assert self.evaluator.evaluate("max(1, 2, 3)") == 3
        assert self.evaluator.evaluate("round(3.7)") == 4
        assert self.evaluator.evaluate("sqrt(16)") == 4.0

    def test_math_constants(self):
        """Test math constants are available."""
        import math

        assert self.evaluator.evaluate("pi") == math.pi
        assert self.evaluator.evaluate("e") == math.e

    def test_comparisons(self):
        """Test comparison operators."""
        assert self.evaluator.evaluate("5 > 3") is True
        assert self.evaluator.evaluate("2 < 1") is False
        assert self.evaluator.evaluate("3 == 3") is True
        assert self.evaluator.evaluate("4 != 5") is True

    def test_unary_operators(self):
        """Test unary operators."""
        assert self.evaluator.evaluate("-5") == -5
        assert self.evaluator.evaluate("+10") == 10

    def test_complex_expression(self):
        """Test complex nested expressions."""
        result = self.evaluator.evaluate("sqrt(abs(-16)) + max(1, 2, 3) * 2")
        assert result == 10.0  # sqrt(16) + 3*2 = 4 + 6

    # Security tests - these should all FAIL/raise

    def test_blocks_import(self):
        """SECURITY: Block __import__ calls."""
        with pytest.raises(ValueError, match="not allowed"):
            self.evaluator.evaluate("__import__('os')")

    def test_blocks_dunder_access(self):
        """SECURITY: Block dunder attribute access."""
        with pytest.raises(ValueError, match="not allowed"):
            self.evaluator.evaluate("().__class__.__bases__")

    def test_blocks_exec(self):
        """SECURITY: Block exec calls."""
        with pytest.raises(ValueError, match="not allowed"):
            self.evaluator.evaluate("exec('print(1)')")

    def test_blocks_eval(self):
        """SECURITY: Block eval calls."""
        with pytest.raises(ValueError, match="not allowed"):
            self.evaluator.evaluate("eval('1+1')")

    def test_blocks_open(self):
        """SECURITY: Block file operations."""
        with pytest.raises(ValueError, match="not allowed"):
            self.evaluator.evaluate("open('/etc/passwd')")

    def test_blocks_system_command(self):
        """SECURITY: Block system command execution patterns."""
        with pytest.raises(ValueError):
            self.evaluator.evaluate("__import__('os').system('id')")

    def test_blocks_getattr(self):
        """SECURITY: Block getattr for attribute access bypass."""
        with pytest.raises(ValueError, match="not allowed"):
            self.evaluator.evaluate("getattr(object, '__subclasses__')")

    def test_blocks_arbitrary_names(self):
        """SECURITY: Block undefined variable names."""
        with pytest.raises(ValueError, match="not allowed"):
            self.evaluator.evaluate("arbitrary_variable")

    def test_blocks_lambda(self):
        """SECURITY: Block lambda expressions."""
        with pytest.raises(ValueError, match="allowed"):
            self.evaluator.evaluate("(lambda: 1)()")

    def test_blocks_comprehensions(self):
        """SECURITY: Block list comprehensions (can hide code execution)."""
        with pytest.raises(ValueError, match="not allowed"):
            self.evaluator.evaluate("[x for x in range(10)]")


@pytest.mark.asyncio
class TestCalculatorTool:
    """Test the full calculator tool."""

    async def test_basic_calculation(self):
        """Test basic calculation via tool."""
        tool = CalculatorTool()
        result = await tool.execute("2 + 2")
        assert result.success is True
        assert result.output == 4

    async def test_malicious_input_blocked(self):
        """SECURITY: Malicious inputs should fail safely."""
        tool = CalculatorTool()

        # This would execute arbitrary code with eval()
        result = await tool.execute("__import__('os').system('id')")
        assert result.success is False
        assert "allowed" in result.error.lower()

    async def test_empty_expression(self):
        """Test empty expression handling."""
        tool = CalculatorTool()
        result = await tool.execute("")
        assert result.success is False
        assert "empty" in result.error.lower()
