"""
Coding Agent — static bug detection.
====================================
Scans code for bugs, secrets, vulnerabilities, anti-patterns, dead code,
and excessive complexity using AST (Python) or regex (other languages).
"""

from __future__ import annotations

import ast
import os
import re
from collections import Counter
from typing import Sequence

from jarvis.core.coding.base import CodeIssue, CodeLanguage, Severity


class BugDetector:
    """Static analysis engine that detects common bugs and anti-patterns."""

    # ── secret patterns ──────────────────────────────────────────────
    _SECRET_PATTERNS: list[tuple[str, str, Severity]] = [
        (r"(?:api[_-]?key|apikey)\s*[:=]\s*['\"]([A-Za-z0-9_\-]{16,})['\"]",
         "Hardcoded API key detected", Severity.CRITICAL),
        (r"(?:secret|password|passwd|pwd)\s*[:=]\s*['\"]([^'\"]{8,})['\"]",
         "Hardcoded password/secret detected", Severity.CRITICAL),
        (r"(?:token)\s*[:=]\s*['\"]([A-Za-z0-9_\-\.]{20,})['\"]",
         "Hardcoded token detected", Severity.CRITICAL),
        (r"-----BEGIN\s+(RSA\s+)?PRIVATE\s+KEY-----",
         "Embedded private key detected", Severity.CRITICAL),
        (r"(?:aws_access_key_id|aws_secret_access_key)\s*=\s*['\"]([^'\"]+)['\"]",
         "AWS credential detected", Severity.CRITICAL),
        (r"['\"]([A-Za-z0-9]{32})['\"]", "Possible API key (32-char hex)", Severity.HIGH),
        (r"(?:jdbc:|mysql://|postgres://|mongodb://)\S+:\S+@",
         "Database connection string with credentials", Severity.CRITICAL),
    ]

    # ── vulnerability patterns ───────────────────────────────────────
    _VULN_PATTERNS: list[tuple[str, str, Severity]] = [
        (r"eval\s*\(", "Use of eval() — potential code injection", Severity.HIGH),
        (r"exec\s*\(", "Use of exec() — potential code injection", Severity.HIGH),
        (r"__import__\s*\(", "Dynamic import — potential code injection", Severity.MEDIUM),
        (r"subprocess\.(?:call|run|Popen)\s*\(.*shell\s*=\s*True",
         "Shell injection via subprocess with shell=True", Severity.HIGH),
        (r"os\.system\s*\(", "Shell injection via os.system()", Severity.HIGH),
        (r"pickle\.loads?\s*\(", "Insecure deserialization with pickle", Severity.HIGH),
        (r"yaml\.load\s*\((?!.*Loader\s*=\s*yaml\.SafeLoader)",
         "Unsafe YAML load — use SafeLoader", Severity.HIGH),
        (r"tempfile\.mktemp\s*\(", "Insecure temp file — use mkstemp()", Severity.MEDIUM),
        (r"assert\s+(?!.*#\s*nosec)", "Assert used for validation (stripped in -O)", Severity.LOW),
        (r"(?:innerHTML|document\.write)\s*\(", "Potential XSS via innerHTML/document.write", Severity.HIGH),
        (r"(?:\.execute|\.raw)\s*\(\s*['\"].*%s", "Potential SQL injection (string formatting)", Severity.HIGH),
        (r"(?:\.execute|\.raw)\s*\(\s*f['\"]", "Potential SQL injection (f-string)", Severity.HIGH),
        (r"(?:\.execute|\.raw)\s*\(\s*['\"].*\+", "Potential SQL injection (concatenation)", Severity.HIGH),
        (r"\.\./", "Path traversal pattern detected", Severity.MEDIUM),
        (r"chmod\s+777", "World-writable permissions (777)", Severity.MEDIUM),
        (r"marshal\.loads?\s*\(", "Insecure deserialization with marshal", Severity.HIGH),
    ]

    # ── anti-pattern regex (non-Python) ──────────────────────────────
    _ANTI_PATTERN_JS: list[tuple[str, str, Severity]] = [
        (r"var\s+", "Use of var — prefer const/let", Severity.LOW),
        (r"==\s*(?!={2})", "Loose equality (==) — prefer ===", Severity.LOW),
        (r"console\.(?:log|debug|info)\s*\(", "console.log left in code", Severity.LOW),
        (r"alert\s*\(", "alert() left in code", Severity.LOW),
    ]

    _ANTI_PATTERN_GENERIC: list[tuple[str, str, Severity]] = [
        (r"(?:TODO|FIXME|HACK|XXX)\b", "Unresolved TODO/FIXME comment", Severity.INFO),
        (r"except\s*:\s*$", "Bare except clause — catch specific exceptions", Severity.MEDIUM),
        (r"\bpass\s*$", "Empty pass statement", Severity.LOW),
    ]

    _COMPLEXITY_THRESHOLD: int = 10

    # ─────────────────────────────────────────────────────────────────
    # public API
    # ─────────────────────────────────────────────────────────────────

    def scan_file(self, file_path: str) -> list[CodeIssue]:
        """Scan a single file and return all detected issues."""
        ext = os.path.splitext(file_path)[1]
        lang = CodeLanguage.from_ext(ext)

        with open(file_path, encoding="utf-8", errors="ignore") as fh:
            code = fh.read()

        issues: list[CodeIssue] = []
        issues.extend(self.detect_secrets(code, lang))
        issues.extend(self.detect_vulnerabilities(code, lang))
        issues.extend(self.detect_anti_patterns(code, lang))
        issues.extend(self.detect_dead_code(code, lang))
        issues.extend(self.detect_complexity(code, lang))

        for issue in issues:
            issue.file = file_path
        return issues

    def scan_project(
        self,
        project_path: str,
        extensions: Sequence[str] | None = None,
    ) -> list[CodeIssue]:
        """Recursively scan a project directory."""
        if extensions is None:
            extensions = {
                ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go",
                ".rs", ".cpp", ".c", ".cs", ".rb", ".php", ".swift",
                ".kt", ".sql", ".sh",
            }
        else:
            extensions = {e if e.startswith(".") else f".{e}" for e in extensions}

        all_issues: list[CodeIssue] = []
        for root, _dirs, files in os.walk(project_path):
            for fname in files:
                if os.path.splitext(fname)[1] in extensions:
                    fpath = os.path.join(root, fname)
                    all_issues.extend(self.scan_file(fpath))
        return all_issues

    def detect_secrets(self, code: str, language: CodeLanguage) -> list[CodeIssue]:
        """Find hardcoded secrets, API keys, and passwords."""
        issues: list[CodeIssue] = []
        lines = code.splitlines()
        for idx, line in enumerate(lines, 1):
            for pattern, msg, severity in self._SECRET_PATTERNS:
                if re.search(pattern, line, re.IGNORECASE):
                    issues.append(CodeIssue(
                        file="", line=idx, severity=severity,
                        code="SEC001", message=msg,
                        suggestion="Move secrets to environment variables or a vault.",
                        fix_available=True,
                    ))
                    break  # one issue per line
        return issues

    def detect_vulnerabilities(self, code: str, language: CodeLanguage) -> list[CodeIssue]:
        """Detect SQL injection, XSS, path traversal, and other vulnerabilities."""
        issues: list[CodeIssue] = []
        lines = code.splitlines()

        if language == CodeLanguage.PYTHON:
            issues.extend(self._detect_py_vulnerabilities(lines))
        elif language in (CodeLanguage.JAVASCRIPT, CodeLanguage.TYPESCRIPT):
            issues.extend(self._detect_js_vulnerabilities(lines))
        else:
            for idx, line in enumerate(lines, 1):
                for pattern, msg, sev in self._VULN_PATTERNS:
                    if re.search(pattern, line):
                        issues.append(CodeIssue(
                            file="", line=idx, severity=sev,
                            code="VUL001", message=msg,
                            suggestion="Review and sanitize input/output.",
                        ))
        return issues

    def detect_anti_patterns(self, code: str, language: CodeLanguage) -> list[CodeIssue]:
        """Detect god objects, deep nesting, long methods, and other anti-patterns."""
        issues: list[CodeIssue] = []

        if language == CodeLanguage.PYTHON:
            issues.extend(self._detect_py_anti_patterns(code))
        else:
            issues.extend(self._detect_generic_anti_patterns(code, language))

        return issues

    def detect_dead_code(self, code: str, language: CodeLanguage) -> list[CodeIssue]:
        """Find unused functions, variables, and imports."""
        if language == CodeLanguage.PYTHON:
            return self._detect_py_dead_code(code)
        return self._detect_generic_dead_code(code)

    def detect_complexity(self, code: str, language: CodeLanguage) -> list[CodeIssue]:
        """Flag functions that exceed the complexity threshold."""
        if language == CodeLanguage.PYTHON:
            return self._detect_py_complexity(code)
        return self._detect_generic_complexity(code)

    def severity_summary(self, issues: list[CodeIssue]) -> dict:
        """Count issues grouped by severity."""
        counts: Counter[str] = Counter()
        for issue in issues:
            counts[issue.severity.name] += 1
        return dict(counts)

    # ─────────────────────────────────────────────────────────────────
    # Python-specific helpers
    # ─────────────────────────────────────────────────────────────────

    def _detect_py_vulnerabilities(self, lines: list[str]) -> list[CodeIssue]:
        issues: list[CodeIssue] = []
        for idx, line in enumerate(lines, 1):
            for pattern, msg, sev in self._VULN_PATTERNS:
                if re.search(pattern, line):
                    issues.append(CodeIssue(
                        file="", line=idx, severity=sev,
                        code="VUL001", message=msg,
                        suggestion="Review and sanitize input/output.",
                    ))
        return issues

    def _detect_py_anti_patterns(self, code: str) -> list[CodeIssue]:
        issues: list[CodeIssue] = []
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return issues

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                methods = [n for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
                if len(methods) > 15:
                    issues.append(CodeIssue(
                        file="", line=node.lineno, severity=Severity.MEDIUM,
                        code="AP001",
                        message=f"God object '{node.name}' has {len(methods)} methods",
                        suggestion="Split into smaller, focused classes.",
                    ))
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                depth = self._max_nesting_depth(node)
                if depth > 4:
                    issues.append(CodeIssue(
                        file="", line=node.lineno, severity=Severity.MEDIUM,
                        code="AP002",
                        message=f"Deep nesting (depth {depth}) in '{node.name}'",
                        suggestion="Extract nested logic into helper functions.",
                    ))
                if len(node.body) > 50:
                    issues.append(CodeIssue(
                        file="", line=node.lineno, severity=Severity.MEDIUM,
                        code="AP003",
                        message=f"Long method '{node.name}' ({len(node.body)} statements)",
                        suggestion="Break into smaller functions.",
                    ))
        return issues

    def _max_nesting_depth(self, node: ast.AST, depth: int = 0) -> int:
        max_d = depth
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.If, ast.For, ast.While, ast.With, ast.Try, ast.ExceptHandler)):
                max_d = max(max_d, self._max_nesting_depth(child, depth + 1))
            else:
                max_d = max(max_d, self._max_nesting_depth(child, depth))
        return max_d

    def _detect_py_dead_code(self, code: str) -> list[CodeIssue]:
        issues: list[CodeIssue] = []
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return issues

        defined_funcs: dict[str, int] = {}
        defined_vars: dict[str, int] = {}
        imported_names: dict[str, int] = {}

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                defined_funcs[node.name] = node.lineno
            elif isinstance(node, ast.Name):
                if isinstance(node.ctx, ast.Store):
                    defined_vars[node.id] = node.lineno
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.asname or alias.name
                    imported_names[name] = node.lineno
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    name = alias.asname or alias.name
                    imported_names[name] = node.lineno

        all_names = code
        for name, lineno in imported_names.items():
            # count occurrences excluding the import line itself
            occurrences = len(re.findall(r'\b' + re.escape(name) + r'\b', all_names))
            if occurrences <= 1:
                issues.append(CodeIssue(
                    file="", line=lineno, severity=Severity.LOW,
                    code="DC001", message=f"Unused import '{name}'",
                    suggestion="Remove unused import.",
                    fix_available=True,
                ))

        for name, lineno in defined_funcs.items():
            if name.startswith("_") and name != "__init__":
                continue
            occurrences = len(re.findall(r'\b' + re.escape(name) + r'\b', all_names))
            if occurrences <= 1:
                issues.append(CodeIssue(
                    file="", line=lineno, severity=Severity.LOW,
                    code="DC002", message=f"Unused function '{name}'",
                    suggestion="Remove or reference the unused function.",
                ))

        return issues

    def _detect_py_complexity(self, code: str) -> list[CodeIssue]:
        issues: list[CodeIssue] = []
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return issues

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                complexity = self._calc_cyclomatic(node)
                if complexity > self._COMPLEXITY_THRESHOLD:
                    issues.append(CodeIssue(
                        file="", line=node.lineno, severity=Severity.MEDIUM,
                        code="CX001",
                        message=f"High complexity ({complexity}) in '{node.name}'",
                        suggestion="Refactor to reduce branching.",
                    ))
        return issues

    def _calc_cyclomatic(self, node: ast.AST) -> int:
        complexity = 1
        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.While, ast.For, ast.ExceptHandler)):
                complexity += 1
            elif isinstance(child, ast.BoolOp):
                complexity += len(child.values) - 1
        return complexity

    # ─────────────────────────────────────────────────────────────────
    # Generic / multi-language helpers
    # ─────────────────────────────────────────────────────────────────

    def _detect_js_vulnerabilities(self, lines: list[str]) -> list[CodeIssue]:
        issues: list[CodeIssue] = []
        for idx, line in enumerate(lines, 1):
            for pattern, msg, sev in self._VULN_PATTERNS:
                if re.search(pattern, line):
                    issues.append(CodeIssue(
                        file="", line=idx, severity=sev,
                        code="VUL001", message=msg,
                        suggestion="Review and sanitize input/output.",
                    ))
        return issues

    def _detect_generic_anti_patterns(self, code: str, language: CodeLanguage) -> list[CodeIssue]:
        issues: list[CodeIssue] = []
        lines = code.splitlines()

        patterns = list(self._ANTI_PATTERN_GENERIC)
        if language in (CodeLanguage.JAVASCRIPT, CodeLanguage.TYPESCRIPT):
            patterns.extend(self._ANTI_PATTERN_JS)

        for idx, line in enumerate(lines, 1):
            for pattern, msg, sev in patterns:
                if re.search(pattern, line):
                    issues.append(CodeIssue(
                        file="", line=idx, severity=sev,
                        code="AP010", message=msg,
                        suggestion="Follow language best practices.",
                    ))

        # deep nesting check (regex fallback)
        for idx, line in enumerate(lines, 1):
            stripped = line.lstrip()
            if stripped:
                indent = len(line) - len(stripped)
                if indent >= 20:
                    issues.append(CodeIssue(
                        file="", line=idx, severity=Severity.MEDIUM,
                        code="AP002",
                        message=f"Deep nesting detected (indent level {indent // 4})",
                        suggestion="Reduce nesting by extracting logic.",
                    ))
        return issues

    def _detect_generic_dead_code(self, code: str) -> list[CodeIssue]:
        issues: list[CodeIssue] = []
        lines = code.splitlines()

        # detect comments-only lines that might indicate dead code blocks
        comment_chars = {
            CodeLanguage.PYTHON: "#",
            CodeLanguage.JAVASCRIPT: "//",
            CodeLanguage.TYPESCRIPT: "//",
            CodeLanguage.JAVA: "//",
            CodeLanguage.GO: "//",
            CodeLanguage.RUST: "//",
            CodeLanguage.CPP: "//",
            CodeLanguage.C: "//",
            CodeLanguage.CSHARP: "//",
            CodeLanguage.RUBY: "#",
            CodeLanguage.PHP: "//",
            CodeLanguage.SWIFT: "//",
            CodeLanguage.KOTLIN: "//",
            CodeLanguage.BASH: "#",
            CodeLanguage.POWERSHELL: "#",
        }

        # simple unused variable heuristic: "type var;" or "var var;" followed by no use
        unused_pattern = re.compile(r'(?:const|let|var|def|val|final)\s+(\w+)')
        for idx, line in enumerate(lines, 1):
            m = unused_pattern.search(line)
            if m:
                name = m.group(1)
                rest = "\n".join(lines[idx:]) if idx < len(lines) else ""
                if name not in rest:
                    issues.append(CodeIssue(
                        file="", line=idx, severity=Severity.LOW,
                        code="DC003",
                        message=f"Possible unused variable '{name}'",
                        suggestion="Remove or use the variable.",
                    ))
        return issues

    def _detect_generic_complexity(self, code: str) -> list[CodeIssue]:
        issues: list[CodeIssue] = []
        lines = code.splitlines()

        func_start = re.compile(
            r'(?:function\s+(\w+)|def\s+(\w+)|fun\s+(\w+)|fn\s+(\w+)|'
            r'(?:public|private|protected|static|\s)+\s+\w+\s+(\w+)\s*\()'
        )
        brace_depth = 0
        current_func: str | None = None
        func_line = 0
        func_complexity = 1

        for idx, line in enumerate(lines, 1):
            m = func_start.search(line)
            if m:
                current_func = next(g for g in m.groups() if g)
                func_line = idx
                func_complexity = 1

            # rough branching count
            for kw in ("if ", "else if", "elif ", "for ", "while ", "switch ", "case ", "catch "):
                if kw in line:
                    func_complexity += 1

            brace_depth += line.count("{") - line.count("}")
            if brace_depth <= 0 and current_func:
                if func_complexity > self._COMPLEXITY_THRESHOLD:
                    issues.append(CodeIssue(
                        file="", line=func_line, severity=Severity.MEDIUM,
                        code="CX001",
                        message=f"High complexity ({func_complexity}) in '{current_func}'",
                        suggestion="Refactor to reduce branching.",
                    ))
                current_func = None
        return issues
