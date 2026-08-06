"""
Skill: Calculator
=================
Evaluate mathematical expressions safely.
"""

from __future__ import annotations

import ast
import math
import operator
from datetime import datetime

from jarvis.core.skills import BaseSkill, SkillContext, SkillMetadata, SkillResult

SAFE_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

SAFE_FUNCS = {
    "abs": abs,
    "round": round,
    "min": min,
    "max": max,
    "sum": sum,
    "sqrt": math.sqrt,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "log": math.log,
    "log10": math.log10,
    "log2": math.log2,
    "exp": math.exp,
    "pi": math.pi,
    "e": math.e,
    "ceil": math.ceil,
    "floor": math.floor,
    "factorial": math.factorial,
}


def _safe_eval(node: ast.AST) -> float:
    if isinstance(node, ast.Expression):
        return _safe_eval(node.body)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError(f"Unsupported constant: {node.value!r}")
    if isinstance(node, ast.BinOp):
        op = SAFE_OPS.get(type(node.op))
        if op is None:
            raise ValueError(f"Unsupported operator: {type(node.op).__name__}")
        return op(_safe_eval(node.left), _safe_eval(node.right))
    if isinstance(node, ast.UnaryOp):
        op = SAFE_OPS.get(type(node.op))
        if op is None:
            raise ValueError(f"Unsupported unary: {type(node.op).__name__}")
        return op(_safe_eval(node.operand))
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        func = SAFE_FUNCS.get(node.func.id)
        if func is None:
            raise ValueError(f"Unknown function: {node.func.id}")
        args = [_safe_eval(a) for a in node.args]
        return func(*args)
    if isinstance(node, ast.Name):
        val = SAFE_FUNCS.get(node.id)
        if val is None:
            raise ValueError(f"Unknown variable: {node.id}")
        if not isinstance(val, (int, float)):
            raise ValueError(f"'{node.id}' is not a number")
        return val
    raise ValueError(f"Unsupported expression: {type(node).__name__}")


class CalculatorSkill(BaseSkill):
    metadata = SkillMetadata(
        name="calculator",
        version="1.0.0",
        description="Evaluate mathematical expressions safely",
        author="JARVIS Team",
        tags=["math", "calculator", "computation"],
    )

    async def execute(self, context: SkillContext) -> SkillResult:
        expr = context.user_input.strip()
        if not expr:
            expr = context.parameters.get("expression", "")

        if not expr:
            return SkillResult(success=False, error="No expression provided")

        try:
            tree = ast.parse(expr, mode="eval")
            result = _safe_eval(tree)
            if isinstance(result, float) and result == int(result) and abs(result) < 1e15:
                result = int(result)
            return SkillResult(
                success=True,
                output=str(result),
                metadata={"expression": expr, "result": result},
            )
        except ZeroDivisionError:
            return SkillResult(success=False, error="Division by zero")
        except (ValueError, SyntaxError, TypeError) as e:
            return SkillResult(success=False, error=f"Invalid expression: {e}")
