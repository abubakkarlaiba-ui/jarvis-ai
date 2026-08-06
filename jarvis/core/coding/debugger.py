"""
Code Debugger — detect errors and suggest fixes.
=================================================
Uses AST for Python, regex pattern matching for other languages.
"""

from __future__ import annotations

import ast
import re
import traceback
import textwrap
from typing import Any

from jarvis.core.coding.base import (
    CodeIssue,
    CodeLanguage,
    CodingResult,
    Severity,
    TaskType,
)


# ---------------------------------------------------------------------------
# Python AST-based analysis
# ---------------------------------------------------------------------------

def _py_find_syntax_errors(code: str) -> list[CodeIssue]:
    """Detect Python syntax errors via ast.parse."""
    issues: list[CodeIssue] = []
    try:
        ast.parse(textwrap.dedent(code))
    except SyntaxError as exc:
        issues.append(CodeIssue(
            file="<input>",
            line=exc.lineno or 1,
            column=exc.offset or 0,
            severity=Severity.CRITICAL,
            code="E999",
            message=str(exc.msg),
            suggestion="Fix the syntax error.",
            fix_available=False,
        ))
    return issues


def _py_find_logic_errors(code: str) -> list[CodeIssue]:
    """Detect logic issues in Python code using AST."""
    issues: list[CodeIssue] = []
    try:
        tree = ast.parse(textwrap.dedent(code))
    except SyntaxError:
        return issues

    for node in ast.walk(tree):
        # Infinite loops: while True with no break
        if isinstance(node, ast.While):
            if isinstance(node.test, ast.Constant) and node.test.value is True:
                has_break = False
                for child in ast.walk(node):
                    if isinstance(child, ast.Break):
                        has_break = True
                        break
                if not has_break:
                    issues.append(CodeIssue(
                        file="<input>",
                        line=getattr(node, "lineno", 1),
                        severity=Severity.HIGH,
                        code="W291",
                        message="Infinite loop: `while True` without `break`.",
                        suggestion="Add a break condition or use a finite loop.",
                    ))

        # Unreachable code after return/raise/continue/break
        if isinstance(node, (ast.FunctionDef, ast.AsyncDef)):
            body = node.body
            for i, stmt in enumerate(body):
                if isinstance(stmt, (ast.Return, ast.Raise, ast.Continue, ast.Break)):
                    if i < len(body) - 1:
                        issues.append(CodeIssue(
                            file="<input>",
                            line=getattr(body[i + 1], "lineno", stmt.lineno),
                            severity=Severity.MEDIUM,
                            code="W0101",
                            message="Unreachable code after return/raise/break/continue.",
                            suggestion="Remove unreachable statements.",
                        ))
                    break

        # Bare except
        if isinstance(node, ast.ExceptHandler) and node.type is None:
            issues.append(CodeIssue(
                file="<input>",
                line=getattr(node, "lineno", 1),
                severity=Severity.MEDIUM,
                        code="W0702",
                message="Bare `except:` catches all exceptions including SystemExit and KeyboardInterrupt.",
                suggestion="Use `except Exception:` or catch specific exceptions.",
            ))

        # Comparison to None/True/False using == instead of is
        if isinstance(node, ast.Compare):
            for op, comparator in zip(node.ops, node.comparators):
                if isinstance(comparator, ast.Constant) and comparator.value in (None, True, False):
                    if not isinstance(op, (ast.Is, ast.IsNot)):
                        issues.append(CodeIssue(
                            file="<input>",
                            line=getattr(node, "lineno", 1),
                            severity=Severity.LOW,
                            code="E711",
                            message=f"Comparison to {comparator.value!r} using `==` instead of `is`.",
                            suggestion=f"Use `is {comparator.value}` instead.",
                            fix_available=True,
                            fix_code="is None" if comparator.value is None else f"is {comparator.value}",
                        ))

        # Mutable default argument
        if isinstance(node, (ast.FunctionDef, ast.AsyncDef)):
            for default in node.args.defaults + node.args.kw_defaults:
                if default is None:
                    continue
                if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                    issues.append(CodeIssue(
                        file="<input>",
                        line=getattr(node, "lineno", 1),
                        severity=Severity.MEDIUM,
                        code="W0102",
                        message=f"Mutable default argument {type(default).__name__} in function `{node.name}`.",
                        suggestion="Use `None` as default and initialize inside the function.",
                    ))

        # star args in dict/list literals (Python <3.5 style, but AST still valid)
        # Duplicate keys in dict
        if isinstance(node, ast.Dict):
            keys_seen: dict[str, int] = {}
            for k in node.keys:
                if k is None:
                    continue
                key_repr = ast.dump(k)
                if key_repr in keys_seen:
                    issues.append(CodeIssue(
                        file="<input>",
                        line=getattr(node, "lineno", 1),
                        severity=Severity.MEDIUM,
                        code="W0109",
                        message="Duplicate key in dictionary literal.",
                        suggestion="Remove the duplicate key.",
                    ))
                keys_seen[key_repr] = keys_seen.get(key_repr, 0) + 1

    return issues


def _py_find_type_errors(code: str) -> list[CodeIssue]:
    """Detect common type-related issues in Python code."""
    issues: list[CodeIssue] = []
    try:
        tree = ast.parse(textwrap.dedent(code))
    except SyntaxError:
        return issues

    for node in ast.walk(tree):
        # isinstance with single arg (missing second argument)
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id == "isinstance":
                if len(node.args) < 2:
                    issues.append(CodeIssue(
                        file="<input>",
                        line=getattr(node, "lineno", 1),
                        severity=Severity.HIGH,
                        code="E1120",
                        message="`isinstance()` called with fewer than 2 arguments.",
                        suggestion="Provide both the object and the type/class to check against.",
                    ))

        # Raising non-exception types
        if isinstance(node, ast.Raise) and node.exc:
            exc = node.exc
            if isinstance(exc, ast.Name) and exc.id[0].islower():
                issues.append(CodeIssue(
                    file="<input>",
                    line=getattr(node, "lineno", 1),
                    severity=Severity.MEDIUM,
                    code="E0602",
                    message=f"Possible non-exception type `{exc.id}` being raised.",
                    suggestion="Ensure the raised value is an exception class or instance.",
                ))

        # Undefined names used as function calls (heuristic)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            name = node.func.id
            builtins = {"print", "len", "range", "int", "str", "float", "list", "dict",
                        "set", "tuple", "type", "isinstance", "hasattr", "getattr",
                        "setattr", "open", "input", "super", "enumerate", "zip",
                        "map", "filter", "sorted", "reversed", "any", "all", "min",
                        "max", "sum", "abs", "round", "id", "hash", "repr", "hex",
                        "oct", "bin", "chr", "ord", "bool", "bytes", "bytearray",
                        "memoryview", "complex", "frozenset", "property", "staticmethod",
                        "classmethod", "object", "Exception", "ValueError", "TypeError",
                        "KeyError", "IndexError", "AttributeError", "RuntimeError",
                        "StopIteration", "ImportError", "OSError", "FileNotFoundError",
                        "ZeroDivisionError", "OverflowError", "FloatingPointError"}
            # Not really possible to detect undefined without full scope analysis
            # but we can catch the most egregious case of calling None
            pass

        # Assigning to None (e.g., x = None; then using x as if it were a value)
        if isinstance(node, ast.Compare):
            for comp in node.comparators:
                if isinstance(comp, ast.Constant) and comp.value is None:
                    # This is fine (checking for None), skip
                    pass

    return issues


# ---------------------------------------------------------------------------
# Regex-based analysis for non-Python languages
# ---------------------------------------------------------------------------

_REGEX_PATTERNS: dict[str, dict[str, Any]] = {
    "javascript": {
        "infinite_loop": [
            (re.compile(r"while\s*\(\s*true\s*\)"), "Infinite loop: `while(true)` without break."),
        ],
        "unreachable": [
            (re.compile(r"return\s+[^;]+;\s*\n\s*[^\s\}]", re.MULTILINE), "Unreachable code after return statement."),
        ],
        "type_issues": [
            (re.compile(r"==\s*null"), "Use `=== null` for strict comparison."),
            (re.compile(r"!=\s*null"), "Use `!== null` for strict comparison."),
        ],
        "lint": [
            (re.compile(r"console\.log\b"), "`console.log` left in code — remove before production."),
            (re.compile(r"var\s+"), "Use `const` or `let` instead of `var`."),
            (re.compile(r"==\s*"), "Use `===` for strict equality."),
            (re.compile(r"!=\s*"), "Use `!==` for strict inequality."),
            (re.compile(r"eval\s*\("), "Avoid `eval()` — security risk."),
        ],
    },
    "typescript": {
        "lint": [
            (re.compile(r"console\.log\b"), "`console.log` left in code."),
            (re.compile(r":\s*any\b"), "Avoid `any` type — use specific types."),
            (re.compile(r"as\s+any\b"), "Avoid `as any` type assertion."),
        ],
    },
    "java": {
        "lint": [
            (re.compile(r"System\.out\.print"), "`System.out.print` left in code — use a logger."),
            (re.compile(r"==\s*"), "Use `.equals()` for object comparison."),
        ],
    },
    "go": {
        "lint": [
            (re.compile(r"fmt\.Print"), "`fmt.Print` left in code — use a logger."),
            (re.compile(r"panic\("), "Avoid `panic` in production code — return errors."),
        ],
    },
    "rust": {
        "lint": [
            (re.compile(r"println!\b"), "`println!` left in code — use `log` or `tracing`."),
            (re.compile(r"unwrap\(\)"), "`unwrap()` may panic — use `?` or `expect()`."),
            (re.compile(r"panic!\b"), "`panic!` in production code."),
        ],
    },
    "cpp": {
        "lint": [
            (re.compile(r"using namespace std"), "Avoid `using namespace std` — pollutes namespace."),
            (re.compile(r"#include\s*<iostream>"), "Consider removing `<iostream>` if not needed."),
        ],
    },
    "csharp": {
        "lint": [
            (re.compile(r"Console\.Write"), "`Console.Write` left in code — use a logger."),
        ],
    },
}


def _regex_find_errors(code: str, lang: CodeLanguage) -> list[CodeIssue]:
    """Apply regex-based detection for non-Python languages."""
    issues: list[CodeIssue] = []
    lang_key = lang.value.lower()
    patterns = _REGEX_PATTERNS.get(lang_key, {})

    for category, pat_list in patterns.items():
        severity_map = {
            "infinite_loop": Severity.HIGH,
            "unreachable": Severity.MEDIUM,
            "type_issues": Severity.MEDIUM,
            "lint": Severity.LOW,
        }
        severity = severity_map.get(category, Severity.LOW)
        code_map = {
            "infinite_loop": "W291",
            "unreachable": "W0101",
            "type_issues": "E711",
            "lint": "W0108",
        }
        code_id = code_map.get(category, "W0100")

        for pat, msg in pat_list:
            for m in pat.finditer(code):
                line_num = code[:m.start()].count("\n") + 1
                issues.append(CodeIssue(
                    file="<input>",
                    line=line_num,
                    severity=severity,
                    code=code_id,
                    message=msg,
                    suggestion="Review and fix.",
                ))

    return issues


# ---------------------------------------------------------------------------
# Stack trace parser
# ---------------------------------------------------------------------------

_STACKTRACE_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # Python traceback
    (re.compile(r'File "([^"]+)", line (\d+)'), "python"),
    # Node.js / Java style
    (re.compile(r"at\s+(?:\S+\s+\()?([^:]+):(\d+):\d+\)?"), "node"),
    # Go style
    (re.compile(r"([^\s]+\.go):(\d+)"), "go"),
    # C/C++ segfault
    (re.compile(r"Segmentation fault.*(?:at|in)\s+(.+?):(\d+)"), "c_cpp"),
]


def _parse_stacktrace(trace: str) -> dict[str, Any]:
    """Parse a stack trace and return structured information."""
    result: dict[str, Any] = {
        "raw": trace,
        "frames": [],
        "exception_type": "",
        "exception_message": "",
        "language": "unknown",
    }

    lines = trace.strip().splitlines()
    if not lines:
        return result

    # Detect exception type (first line usually has it)
    first_line = lines[0].strip()
    # Python: "Traceback (most recent call last):" or "SomeError: message"
    python_exc = re.match(r"^(\w+(?:\.\w+)*(?:Error|Exception|Warning))\s*:\s*(.*)", first_line)
    if python_exc:
        result["exception_type"] = python_exc.group(1)
        result["exception_message"] = python_exc.group(2).strip()
        result["language"] = "python"
    else:
        # Generic: try to extract exception from lines
        for line in lines:
            exc_match = re.match(r"^(\w+(?:Error|Exception|Fault|Panic))\s*[:]\s*(.*)", line.strip())
            if exc_match:
                result["exception_type"] = exc_match.group(1)
                result["exception_message"] = exc_match.group(2).strip()
                break

    # Parse frames
    for pat, lang in _STACKTRACE_PATTERNS:
        for m in pat.finditer(trace):
            file_path = m.group(1)
            line_num = int(m.group(2))
            result["frames"].append({
                "file": file_path,
                "line": line_num,
                "language": lang,
            })
            if result["language"] == "unknown":
                result["language"] = lang

    # Deduplicate frames
    seen: set[str] = set()
    unique_frames: list[dict[str, Any]] = []
    for frame in result["frames"]:
        key = f"{frame['file']}:{frame['line']}"
        if key not in seen:
            seen.add(key)
            unique_frames.append(frame)
    result["frames"] = unique_frames

    return result


# ---------------------------------------------------------------------------
# Linter
# ---------------------------------------------------------------------------

def _py_lint(code: str) -> list[CodeIssue]:
    """Basic Python linting via AST."""
    issues: list[CodeIssue] = []
    try:
        tree = ast.parse(textwrap.dedent(code))
    except SyntaxError:
        return _py_find_syntax_errors(code)

    lines = code.splitlines()

    for node in ast.walk(tree):
        # Unused imports (heuristic: imported name not used elsewhere)
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                name = alias.asname or alias.name
                # Check if name is used in code (rough heuristic)
                used_count = len(re.findall(r'\b' + re.escape(name) + r'\b', code))
                if used_count <= 1 and not name.startswith("_"):
                    issues.append(CodeIssue(
                        file="<input>",
                        line=getattr(node, "lineno", 1),
                        severity=Severity.LOW,
                        code="F401",
                        message=f"`{name}` imported but unused.",
                        suggestion=f"Remove `{name}` from imports.",
                        fix_available=True,
                    ))

        # Missing docstrings for public functions/classes
        if isinstance(node, (ast.FunctionDef, ast.AsyncDef, ast.ClassDef)):
            if not node.name.startswith("_"):
                ds = ast.get_docstring(node)
                if not ds:
                    kind = "class" if isinstance(node, ast.ClassDef) else "function"
                    issues.append(CodeIssue(
                        file="<input>",
                        line=getattr(node, "lineno", 1),
                        severity=Severity.INFO,
                        code="D100",
                        message=f"Missing docstring for public {kind} `{node.name}`.",
                        suggestion=f"Add a docstring to `{node.name}`.",
                    ))

        # Line length (PEP 8)
    for i, line in enumerate(lines, 1):
        if len(line) > 120:
            issues.append(CodeIssue(
                file="<input>",
                line=i,
                severity=Severity.INFO,
                code="E501",
                message=f"Line too long ({len(line)} > 120 characters).",
                suggestion="Break line or use intermediate variables.",
            ))

    return issues


def _regex_lint(code: str, lang: CodeLanguage) -> list[CodeIssue]:
    """Regex-based linting for non-Python languages."""
    return _regex_find_errors(code, lang)


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

class Debugger:
    """Debug code by detecting errors and suggesting fixes."""

    def _resolve_lang(self, language: str | CodeLanguage) -> CodeLanguage:
        if isinstance(language, CodeLanguage):
            return language
        return CodeLanguage.from_ext(language)

    # ------------------------------------------------------------------
    # debug
    # ------------------------------------------------------------------

    def debug(
        self,
        code: str,
        language: str | CodeLanguage = CodeLanguage.PYTHON,
        error_message: str = "",
    ) -> CodingResult:
        """Full debug analysis: syntax, logic, type errors, and linting."""
        lang = self._resolve_lang(language)
        all_issues: list[CodeIssue] = []

        all_issues.extend(self.find_syntax_errors(code, lang))
        all_issues.extend(self.find_logic_errors(code, lang))
        all_issues.extend(self.find_type_errors(code, lang))
        all_issues.extend(self.lint(code, lang))

        if error_message:
            trace_info = self.analyze_stacktrace(error_message)
            if trace_info.get("frames"):
                all_issues.append(CodeIssue(
                    file=trace_info["frames"][0].get("file", "<input>"),
                    line=trace_info["frames"][0].get("line", 0),
                    severity=Severity.HIGH,
                    code="ERR",
                    message=f"{trace_info.get('exception_type', 'Error')}: {trace_info.get('exception_message', '')}",
                    suggestion="See stack trace analysis for details.",
                ))

        all_issues = self.suggest_fixes(all_issues, code)

        summary_parts: list[str] = []
        by_sev: dict[str, int] = {}
        for iss in all_issues:
            sev = iss.severity.name
            by_sev[sev] = by_sev.get(sev, 0) + 1
        for sev, count in sorted(by_sev.items()):
            summary_parts.append(f"{count} {sev}")
        summary = f"Found {len(all_issues)} issue(s): {', '.join(summary_parts)}" if all_issues else "No issues found."

        return CodingResult(
            success=True,
            task_type=TaskType.DEBUG,
            code=code,
            explanation=summary,
            issues=all_issues,
            metadata={"language": lang.value, "error_message": error_message},
        )

    # ------------------------------------------------------------------
    # find_syntax_errors
    # ------------------------------------------------------------------

    def find_syntax_errors(
        self,
        code: str,
        language: str | CodeLanguage = CodeLanguage.PYTHON,
    ) -> list[CodeIssue]:
        """Detect syntax errors."""
        lang = self._resolve_lang(language)
        if lang == CodeLanguage.PYTHON:
            return _py_find_syntax_errors(code)
        # For non-Python, try regex-based detection
        return _regex_find_errors(code, lang)

    # ------------------------------------------------------------------
    # find_logic_errors
    # ------------------------------------------------------------------

    def find_logic_errors(
        self,
        code: str,
        language: str | CodeLanguage = CodeLanguage.PYTHON,
    ) -> list[CodeIssue]:
        """Detect logic issues (infinite loops, unreachable code, etc)."""
        lang = self._resolve_lang(language)
        if lang == CodeLanguage.PYTHON:
            return _py_find_logic_errors(code)
        return _regex_find_errors(code, lang)

    # ------------------------------------------------------------------
    # find_type_errors
    # ------------------------------------------------------------------

    def find_type_errors(
        self,
        code: str,
        language: str | CodeLanguage = CodeLanguage.PYTHON,
    ) -> list[CodeIssue]:
        """Detect type mismatches and type-related issues."""
        lang = self._resolve_lang(language)
        if lang == CodeLanguage.PYTHON:
            return _py_find_type_errors(code)
        return _regex_find_errors(code, lang)

    # ------------------------------------------------------------------
    # suggest_fixes
    # ------------------------------------------------------------------

    def suggest_fixes(
        self,
        issues: list[CodeIssue],
        code: str,
    ) -> list[CodeIssue]:
        """Suggest fixes for detected issues."""
        for issue in issues:
            if issue.fix_code:
                issue.fix_available = True
                continue
            # Auto-generate suggestions based on code pattern
            msg_lower = issue.message.lower()
            if "unused" in msg_lower and "import" in msg_lower:
                # Extract the name from message
                name_match = re.search(r"`(\w+)`", issue.message)
                if name_match:
                    issue.fix_available = True
                    issue.fix_code = f"# remove: {name_match.group(1)}"
            elif "mutable default" in msg_lower:
                issue.fix_available = True
                issue.fix_code = "Use `None` as default and initialize inside the function body."
            elif "bare except" in msg_lower or "bare `except`" in msg_lower:
                issue.fix_available = True
                issue.fix_code = "except Exception:"
            elif "console.log" in msg_lower:
                issue.fix_available = True
                issue.fix_code = "// remove console.log"
            elif "var " in msg_lower:
                issue.fix_available = True
                issue.fix_code = "Replace `var` with `const` or `let`."
        return issues

    # ------------------------------------------------------------------
    # analyze_stacktrace
    # ------------------------------------------------------------------

    def analyze_stacktrace(self, trace: str) -> dict[str, Any]:
        """Parse and explain a stack trace."""
        return _parse_stacktrace(trace)

    # ------------------------------------------------------------------
    # lint
    # ------------------------------------------------------------------

    def lint(
        self,
        code: str,
        language: str | CodeLanguage = CodeLanguage.PYTHON,
    ) -> list[CodeIssue]:
        """Basic linting: unused imports, style issues, etc."""
        lang = self._resolve_lang(language)
        if lang == CodeLanguage.PYTHON:
            return _py_lint(code)
        return _regex_lint(code, lang)
