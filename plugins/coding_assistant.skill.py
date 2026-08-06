"""
Skill: Coding Assistant
=======================
Code review, explanation, and refactoring suggestions using pattern-based
analysis. No external API calls.
"""

from __future__ import annotations

import ast
import re
from typing import Any

from jarvis.core.skills import BaseSkill, SkillContext, SkillMetadata, SkillResult

EXTENSION_TO_LANG: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".jsx": "jsx",
    ".tsx": "tsx",
    ".java": "java",
    ".c": "c",
    ".cpp": "cpp",
    ".cs": "csharp",
    ".go": "go",
    ".rs": "rust",
    ".rb": "ruby",
    ".php": "php",
    ".swift": "swift",
    ".kt": "kotlin",
    ".sh": "bash",
    ".ps1": "powershell",
    ".bat": "batch",
    ".sql": "sql",
    ".html": "html",
    ".css": "css",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".xml": "xml",
    ".toml": "toml",
    ".md": "markdown",
}

PYTHON_BUILTINS = set(dir(__builtins__)) if isinstance(__builtins__, dict) else set(dir(__builtins__))
PYTHON_COMMON_IMPORTS = {
    "os", "sys", "re", "json", "math", "datetime", "time", "pathlib",
    "collections", "itertools", "functools", "typing", "abc", "io",
    "logging", "hashlib", "subprocess", "threading", "asyncio",
}

SINGLE_LETTER_VARS = set("abcdefghijklmnopqrstuvwxyz")


def _detect_language(filename: str | None) -> str:
    if not filename:
        return "unknown"
    for ext, lang in EXTENSION_TO_LANG.items():
        if filename.endswith(ext):
            return lang
    return "unknown"


def _count_lines(code: str) -> dict[str, int]:
    lines = code.split("\n")
    blank = sum(1 for l in lines if l.strip() == "")
    comment = sum(
        1 for l in lines
        if l.strip().startswith("#") or l.strip().startswith("//") or l.strip().startswith("*")
    )
    return {"total": len(lines), "code": len(lines) - blank - comment, "blank": blank, "comment": comment}


def _check_python_ast(code: str) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        issues.append({"line": e.lineno or 1, "category": "syntax", "message": f"Syntax error: {e.msg}"})
        return issues

    func_names: list[str] = []
    class_names: list[str] = []
    assigned_names: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            func_names.append(node.name)
            if len(node.name) > 45:
                issues.append({"line": node.lineno, "category": "naming", "message": f"Function name too long: '{node.name}'"})
            if node.name.startswith("_") and not node.name.startswith("__"):
                issues.append({"line": node.lineno, "category": "naming", "message": f"Private function '{node.name}' — ensure it's used internally"})

        if isinstance(node, ast.ClassDef):
            class_names.append(node.name)

        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    assigned_names.add(target.id)
                    if len(target.id) == 1 and target.id in SINGLE_LETTER_VARS:
                        issues.append({"line": node.lineno, "category": "naming", "message": f"Single-letter variable '{target.id}' — consider a descriptive name"})

        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            if node.id.startswith("_") and not node.id.startswith("__"):
                pass

        if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
            if len(node.args.args) > 6:
                issues.append({
                    "line": node.lineno,
                    "category": "complexity",
                    "message": f"Function '{node.name}' has {len(node.args.args)} parameters — consider grouping into a dataclass or dict",
                })

            body_str = ast.dump(ast.Module(body=node.body, type_ignores=[]))
            if body_str.count("If(") + body_str.count("For(") + body_str.count("While(") > 5:
                issues.append({
                    "line": node.lineno,
                    "category": "complexity",
                    "message": f"Function '{node.name}' has high nesting — consider extracting helper functions",
                })

    imports_used: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.asname if alias.asname else alias.name
                imports_used.add(name)
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                name = alias.asname if alias.asname else alias.name
                imports_used.add(name)

    return issues


def _check_python_patterns(code: str) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    lines = code.split("\n")

    import_lines = [i + 1 for i, l in enumerate(lines) if re.match(r"^\s*import\s+", l) or re.match(r"^\s*from\s+", l)]

    bare_excepts = [i + 1 for i, l in enumerate(lines) if re.match(r"^\s*except\s*:", l)]
    for ln in bare_excepts:
        issues.append({"line": ln, "category": "error-handling", "message": "Bare except clause — catch specific exceptions instead"})

    todo_fixme = [i + 1 for i, l in enumerate(lines) if re.search(r"#\s*(TODO|FIXME|HACK|XXX|TEMP)", l, re.IGNORECASE)]
    for ln in todo_fixme:
        issues.append({"line": ln, "category": "maintainability", "message": "TODO/FIXME marker found — resolve before production"})

    long_lines = [i + 1 for i, l in enumerate(lines) if len(l) > 120 and not l.strip().startswith("#")]
    for ln in long_lines:
        issues.append({"line": ln, "category": "style", "message": f"Line exceeds 120 characters"})

    global_usage = [i + 1 for i, l in enumerate(lines) if re.match(r"^\s*global\s+", l)]
    for ln in global_usage:
        issues.append({"line": ln, "category": "design", "message": "Global variable usage — prefer passing state via parameters or context"})

    print_usage = [i + 1 for i, l in enumerate(lines) if re.search(r"\bprint\s*\(", l)]
    for ln in print_usage:
        issues.append({"line": ln, "category": "style", "message": "print() call found — consider using logging instead"})

    return issues


def _check_generic_patterns(code: str) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    lines = code.split("\n")

    todo_fixme = [i + 1 for i, l in enumerate(lines) if re.search(r"//\s*(TODO|FIXME|HACK|XXX|TEMP)", l, re.IGNORECASE)]
    for ln in todo_fixme:
        issues.append({"line": ln, "category": "maintainability", "message": "TODO/FIXME marker found"})

    console_log = [i + 1 for i, l in enumerate(lines) if re.search(r"\bconsole\.(log|warn|error)\s*\(", l)]
    for ln in console_log:
        issues.append({"line": ln, "category": "style", "message": "console.log found — remove or use a proper logger"})

    long_lines = [i + 1 for i, l in enumerate(lines) if len(l) > 120 and not l.strip().startswith("//")]
    for ln in long_lines:
        issues.append({"line": ln, "category": "style", "message": "Line exceeds 120 characters"})

    return issues


def _summarize_code(code: str, lang: str) -> str:
    counts = _count_lines(code)
    parts = [f"Language: {lang}", f"Lines: {counts['total']} total, {counts['code']} code, {counts['blank']} blank, {counts['comment']} comments"]
    return "; ".join(parts)


class CodingAssistantSkill(BaseSkill):
    metadata = SkillMetadata(
        name="coding_assistant",
        version="1.0.0",
        description="Code review, explanation, and refactoring suggestions via pattern analysis",
        author="JARVIS Team",
        tags=["code", "programming", "development"],
    )

    async def execute(self, context: SkillContext) -> SkillResult:
        action = context.parameters.get("action", "review").lower()
        code = context.parameters.get("code", context.user_input.strip())
        filename = context.parameters.get("filename", None)

        if not code:
            return SkillResult(success=False, error="No code provided. Pass code in parameters or user input.")

        lang = _detect_language(filename)

        handlers = {
            "review": self._review,
            "explain": self._explain,
            "refactor": self._refactor,
        }

        handler = handlers.get(action)
        if not handler:
            return SkillResult(
                success=False,
                error=f"Unknown action '{action}'. Available: {', '.join(handlers)}",
            )
        return await handler(code, lang, context)

    async def _review(self, code: str, lang: str, context: SkillContext) -> SkillResult:
        issues: list[dict[str, Any]] = []

        if lang == "python":
            issues.extend(_check_python_ast(code))
            issues.extend(_check_python_patterns(code))
        else:
            issues.extend(_check_generic_patterns(code))

        summary = _summarize_code(code, lang)

        if not issues:
            output = f"{summary}\n\nNo issues found. Code looks clean."
        else:
            lines = [f"{summary}\n"]
            by_cat: dict[str, list] = {}
            for issue in issues:
                by_cat.setdefault(issue["category"], []).append(issue)
            for cat, items in sorted(by_cat.items()):
                lines.append(f"[{cat}]")
                for item in items:
                    lines.append(f"  Line {item['line']}: {item['message']}")
            lines.append(f"\nTotal: {len(issues)} issue(s) found.")
            output = "\n".join(lines)

        return SkillResult(
            success=True,
            output=output,
            metadata={"lang": lang, "issue_count": len(issues), "issues": issues},
        )

    async def _explain(self, code: str, lang: str, context: SkillContext) -> SkillResult:
        lines = _count_lines(code)
        explanation_parts: list[str] = [f"Language: {lang}", f"Length: {lines['code']} lines of code"]

        if lang == "python":
            try:
                tree = ast.parse(code)
            except SyntaxError:
                tree = None

            if tree is not None:
                funcs = [n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
                classes = [n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
                imports = []
                for n in ast.walk(tree):
                    if isinstance(n, ast.Import):
                        imports.extend(a.name for a in n.names)
                    elif isinstance(n, ast.ImportFrom) and n.module:
                        imports.append(n.module)

                if classes:
                    explanation_parts.append(f"Classes: {', '.join(classes)}")
                if funcs:
                    explanation_parts.append(f"Functions: {', '.join(funcs)}")
                if imports:
                    explanation_parts.append(f"Imports: {', '.join(imports)}")
                explanation_parts.append(f"Estimated complexity: {'high' if len(funcs) > 8 or lines['code'] > 200 else 'low'}")
        else:
            function_count = len(re.findall(r"(?:function\s+\w+|const\s+\w+\s*=\s*(?:async\s*)?\()|(?:def\s+\w+)", code))
            class_count = len(re.findall(r"(?:class\s+\w+)", code))
            if function_count:
                explanation_parts.append(f"~{function_count} function(s) defined")
            if class_count:
                explanation_parts.append(f"~{class_count} class(es) defined")

        output = "\n".join(explanation_parts)
        return SkillResult(
            success=True,
            output=output,
            metadata={"lang": lang, "lines": lines},
        )

    async def _refactor(self, code: str, lang: str, context: SkillContext) -> SkillResult:
        suggestions: list[str] = []

        if lang == "python":
            try:
                tree = ast.parse(code)
            except SyntaxError:
                tree = None

            if tree is not None:
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if len(node.args.args) > 4:
                            suggestions.append(f"Function '{node.name}' at line {node.lineno}: use a dataclass or namedtuple for {len(node.args.args)} parameters")
                        body_nodes = node.body
                        nesting = sum(1 for n in ast.walk(node) if isinstance(n, (ast.If, ast.For, ast.While, ast.With)))
                        if nesting > 3:
                            suggestions.append(f"Function '{node.name}' at line {node.lineno}: deep nesting detected — extract inner logic into helper functions")

                    if isinstance(node, ast.ClassDef):
                        method_count = sum(1 for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)))
                        if method_count > 10:
                            suggestions.append(f"Class '{node.name}' at line {node.lineno}: {method_count} methods — consider splitting responsibilities (SRP)")

                    if isinstance(node, ast.Assign):
                        for target in node.targets:
                            if isinstance(target, ast.Name) and target.id.startswith("_") and not target.id.startswith("__"):
                                suggestions.append(f"Variable '{target.id}' at line {node.lineno}: leading underscore suggests private — use a class or module for encapsulation")

        lines = code.split("\n")
        long_funcs: list[tuple[str, int]] = []
        current_func = None
        func_start = 0
        for i, l in enumerate(lines):
            if re.match(r"(?:async\s+)?def\s+(\w+)", l):
                if current_func and i - func_start > 50:
                    long_funcs.append((current_func, i - func_start))
                match = re.match(r"(?:async\s+)?def\s+(\w+)", l)
                current_func = match.group(1) if match else "unknown"
                func_start = i
        if current_func and len(lines) - func_start > 50:
            long_funcs.append((current_func, len(lines) - func_start))

        for fname, length in long_funcs:
            suggestions.append(f"Function '{fname}' is {length} lines long — break into smaller functions")

        dup_imports = re.findall(r"^(import\s+\w+|from\s+\w+\s+import\s+\w+)", code, re.MULTILINE)
        seen: set[str] = set()
        for imp in dup_imports:
            if imp in seen:
                suggestions.append(f"Duplicate import: {imp.strip()}")
            seen.add(imp)

        if not suggestions:
            output = "No refactoring suggestions. Code structure looks reasonable."
        else:
            output = "Refactoring suggestions:\n" + "\n".join(f"  - {s}" for s in suggestions)

        return SkillResult(
            success=True,
            output=output,
            metadata={"lang": lang, "suggestion_count": len(suggestions)},
        )
