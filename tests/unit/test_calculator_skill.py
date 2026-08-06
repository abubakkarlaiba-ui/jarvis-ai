"""Unit tests for the Calculator skill plugin."""

from __future__ import annotations

import math

import pytest

from tests.conftest import run_async

from plugins.calculator.skill import CalculatorSkill
from jarvis.core.skills.module import SkillContext, SkillResult


@pytest.fixture
def calculator():
    return CalculatorSkill()


@pytest.fixture
def make_context():
    def _make(expr: str) -> SkillContext:
        return SkillContext(user_input=expr)
    return _make


@pytest.mark.unit
class TestCalculatorSkill:
    """Test cases for CalculatorSkill.execute."""

    def test_add(self, calculator, make_context):
        ctx = make_context("2+3")
        result = run_async(calculator.execute(ctx))
        assert result.success is True
        assert result.output == "5"

    def test_subtract(self, calculator, make_context):
        ctx = make_context("10-4")
        result = run_async(calculator.execute(ctx))
        assert result.success is True
        assert result.output == "6"

    def test_multiply(self, calculator, make_context):
        ctx = make_context("6*7")
        result = run_async(calculator.execute(ctx))
        assert result.success is True
        assert result.output == "42"

    def test_divide(self, calculator, make_context):
        ctx = make_context("10/2")
        result = run_async(calculator.execute(ctx))
        assert result.success is True
        assert result.output == "5.0"

    def test_divide_by_zero(self, calculator, make_context):
        ctx = make_context("1/0")
        result = run_async(calculator.execute(ctx))
        assert result.success is False
        assert "Division by zero" in result.error

    def test_complex(self, calculator, make_context):
        ctx = make_context("2**10")
        result = run_async(calculator.execute(ctx))
        assert result.success is True
        assert result.output == "1024"

    def test_nested(self, calculator, make_context):
        ctx = make_context("(2+3)*4")
        result = run_async(calculator.execute(ctx))
        assert result.success is True
        assert result.output == "20"

    def test_imports(self, calculator, make_context):
        ctx = make_context("sqrt(16)")
        result = run_async(calculator.execute(ctx))
        assert result.success is True
        assert result.output == "4.0"

    def test_pi(self, calculator, make_context):
        ctx = make_context("pi")
        result = run_async(calculator.execute(ctx))
        assert result.success is True
        assert float(result.output) == pytest.approx(math.pi, rel=1e-9)

    def test_invalid(self, calculator, make_context):
        ctx = make_context("invalid!!!")
        result = run_async(calculator.execute(ctx))
        assert result.success is False
        assert result.error != ""
