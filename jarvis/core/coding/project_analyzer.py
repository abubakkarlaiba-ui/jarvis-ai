"""
Project Analyzer — analyze project structure, quality, and dependencies.
=======================================================================
Walks directory trees, parses config files, uses AST for Python analysis.
"""

from __future__ import annotations

import ast
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

from jarvis.core.coding.base import (
    CodeIssue,
    CodeLanguage,
    CodingResult,
    Severity,
    TaskType,
)


# ---------------------------------------------------------------------------
# Language detection by extension
# ---------------------------------------------------------------------------

_EXT_LANG_MAP: dict[str, CodeLanguage] = {
    ".py": CodeLanguage.PYTHON,
    ".js": CodeLanguage.JAVASCRIPT,
    ".ts": CodeLanguage.TYPESCRIPT,
    ".jsx": CodeLanguage.JAVASCRIPT,
    ".tsx": CodeLanguage.TYPESCRIPT,
    ".java": CodeLanguage.JAVA,
    ".go": CodeLanguage.GO,
    ".rs": CodeLanguage.RUST,
    ".cpp": CodeLanguage.CPP,
    ".cc": CodeLanguage.CPP,
    ".cxx": CodeLanguage.CPP,
    ".c": CodeLanguage.C,
    ".h": CodeLanguage.C,
    ".hpp": CodeLanguage.CPP,
    ".cs": CodeLanguage.CSHARP,
    ".rb": CodeLanguage.RUBY,
    ".php": CodeLanguage.PHP,
    ".swift": CodeLanguage.SWIFT,
    ".kt": CodeLanguage.KOTLIN,
    ".sql": CodeLanguage.SQL,
    ".html": CodeLanguage.HTML,
    ".css": CodeLanguage.CSS,
    ".sh": CodeLanguage.BASH,
    ".bash": CodeLanguage.BASH,
    ".ps1": CodeLanguage.POWERSHELL,
    ".yml": CodeLanguage.YAML,
    ".yaml": CodeLanguage.YAML,
    ".json": CodeLanguage.JSON,
    ".md": CodeLanguage.MARKDOWN,
}

_IGNORE_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv", "env",
    ".tox", ".mypy_cache", ".pytest_cache", "dist", "build",
    ".next", ".nuxt", "vendor", "target", "coverage",
}


# ---------------------------------------------------------------------------
# Dependency parsers
# ---------------------------------------------------------------------------

def _parse_requirements_txt(path: Path) -> list[dict[str, Any]]:
    deps: list[dict[str, Any]] = []
    if not path.exists():
        return deps
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        m = re.match(r"^([a-zA-Z0-9_\-.]+)\s*([><=!~]+.*)?$", line)
        if m:
            deps.append({"name": m.group(1), "version": (m.group(2) or "").strip(), "source": "requirements.txt"})
    return deps


def _parse_package_json(path: Path) -> list[dict[str, Any]]:
    deps: list[dict[str, Any]] = []
    if not path.exists():
        return deps
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return deps
    for section in ("dependencies", "devDependencies", "peerDependencies"):
        for name, ver in data.get(section, {}).items():
            deps.append({"name": name, "version": ver, "source": f"package.json:{section}"})
    return deps


def _parse_go_mod(path: Path) -> list[dict[str, Any]]:
    deps: list[dict[str, Any]] = []
    if not path.exists():
        return deps
    in_require = False
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("require ("):
            in_require = True
            continue
        if line == ")":
            in_require = False
            continue
        if in_require or line.startswith("require "):
            parts = line.replace("require ", "").strip().split()
            if len(parts) >= 2:
                deps.append({"name": parts[0], "version": parts[1], "source": "go.mod"})
    return deps


def _parse_cargo_toml(path: Path) -> list[dict[str, Any]]:
    deps: list[dict[str, Any]] = []
    if not path.exists():
        return deps
    content = path.read_text(encoding="utf-8")
    current_section = ""
    for line in content.splitlines():
        line = line.strip()
        if line.startswith("["):
            current_section = line
            continue
        if "=" in line and current_section in ("[dependencies]", "[dev-dependencies]", "[build-dependencies]"):
            m = re.match(r'^(\w[\w-]*)\s*=\s*"?([^"]+)"?', line)
            if m:
                deps.append({"name": m.group(1), "version": m.group(2).strip(), "source": "Cargo.toml"})
    return deps


def _parse_gemfile(path: Path) -> list[dict[str, Any]]:
    deps: list[dict[str, Any]] = []
    if not path.exists():
        return deps
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        m = re.match(r"""^gem\s+['"](\w[\w-]*)['"]\s*(?:,\s*['"]([^'"]+)['"])?""", line)
        if m:
            deps.append({"name": m.group(1), "version": m.group(2) or "", "source": "Gemfile"})
    return deps


def _parse_composer_json(path: Path) -> list[dict[str, Any]]:
    deps: list[dict[str, Any]] = []
    if not path.exists():
        return deps
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return deps
    for section in ("require", "require-dev"):
        for name, ver in data.get(section, {}).items():
            deps.append({"name": name, "version": ver, "source": f"composer.json:{section}"})
    return deps


# ---------------------------------------------------------------------------
# Python AST analysis
# ---------------------------------------------------------------------------

def _py_analyze_file(path: Path) -> dict[str, Any]:
    """Analyze a Python file using AST."""
    result: dict[str, Any] = {
        "functions": 0,
        "classes": 0,
        "imports": 0,
        "comments": 0,
        "blank_lines": 0,
        "complexity": 0.0,
    }
    try:
        source = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return result

    lines = source.splitlines()
    result["blank_lines"] = sum(1 for l in lines if not l.strip())
    result["comments"] = sum(1 for l in lines if l.strip().startswith("#"))

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return result

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncDef)):
            result["functions"] += 1
            # Simple cyclomatic complexity
            result["complexity"] += 1
            for child in ast.walk(node):
                if isinstance(child, (ast.If, ast.While, ast.For, ast.ExceptHandler, ast.With, ast.Assert)):
                    result["complexity"] += 1
                if isinstance(child, ast.BoolOp):
                    result["complexity"] += len(child.values) - 1
        elif isinstance(node, ast.ClassDef):
            result["classes"] += 1
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            result["imports"] += len(node.names)

    return result


# ---------------------------------------------------------------------------
# Known vulnerability patterns (simplified)
# ---------------------------------------------------------------------------

_VULNERABILITY_PATTERNS: list[dict[str, Any]] = [
    {"pattern": r"eval\s*\(", "severity": Severity.CRITICAL, "message": "Use of eval() — potential code injection", "language": "python"},
    {"pattern": r"exec\s*\(", "severity": Severity.CRITICAL, "message": "Use of exec() — potential code injection", "language": "python"},
    {"pattern": r"os\.system\s*\(", "severity": Severity.HIGH, "message": "Use of os.system() — use subprocess instead", "language": "python"},
    {"pattern": r"subprocess\.call.*shell\s*=\s*True", "severity": Severity.HIGH, "message": "subprocess with shell=True — command injection risk", "language": "python"},
    {"pattern": r"SELECT.*FROM.*\{", "severity": Severity.CRITICAL, "message": "Possible SQL injection — use parameterized queries", "language": "python"},
    {"pattern": r"innerHTML\s*=", "severity": Severity.HIGH, "message": "innerHTML assignment — potential XSS", "language": "javascript"},
    {"pattern": r"document\.write\s*\(", "severity": Severity.MEDIUM, "message": "document.write() — potential XSS", "language": "javascript"},
    {"pattern": r"dangerouslySetInnerHTML", "severity": Severity.HIGH, "message": "dangerouslySetInnerHTML — potential XSS", "language": "javascript"},
    {"pattern": r"eval\s*\(", "severity": Severity.CRITICAL, "message": "Use of eval() — potential code injection", "language": "javascript"},
    {"pattern": r"Function\s*\(", "severity": Severity.HIGH, "message": "Function constructor — potential code injection", "language": "javascript"},
    {"pattern": r"exec\s*\(", "severity": Severity.CRITICAL, "message": "Use of exec() — potential code injection", "language": "ruby"},
    {"pattern": r"system\s*\(", "severity": Severity.HIGH, "message": "system() call — potential command injection", "language": "ruby"},
]


# ---------------------------------------------------------------------------
# ProjectAnalyzer
# ---------------------------------------------------------------------------

class ProjectAnalyzer:
    """Analyze a project's structure, quality, and dependencies."""

    # ------------------------------------------------------------------
    # analyze_project
    # ------------------------------------------------------------------

    def analyze_project(self, project_path: str) -> CodingResult:
        """Full project analysis."""
        p = Path(project_path)
        if not p.exists():
            return CodingResult(
                success=False,
                task_type=TaskType.ANALYZE,
                error=f"Project path does not exist: {project_path}",
            )

        lang_dist = self.detect_language(project_path)
        loc = self.count_lines(project_path)
        deps = self.find_dependencies(project_path)
        structure = self.analyze_structure(project_path)
        health = self.health_score(project_path)
        entry_points = self.find_entry_points(project_path)
        issues = self.security_audit(project_path)

        primary_lang = max(lang_dist.items(), key=lambda x: x[1])[0] if lang_dist else "unknown"

        explanation_lines = [
            f"Project: {p.name}",
            f"Primary language: {primary_lang}",
            f"Files: {structure.get('total_files', 0)}",
            f"Total lines: {sum(loc.values())}",
            f"Dependencies: {len(deps)}",
            f"Health score: {health.get('score', 0)}/100",
            f"Security issues: {len(issues)}",
            f"Entry points: {len(entry_points)}",
        ]

        return CodingResult(
            success=True,
            task_type=TaskType.ANALYZE,
            output={
                "language_distribution": lang_dist,
                "lines_of_code": loc,
                "dependencies": deps,
                "structure": structure,
                "health": health,
                "entry_points": entry_points,
            },
            issues=issues,
            explanation="\n".join(explanation_lines),
            metadata={"project_path": project_path},
        )

    # ------------------------------------------------------------------
    # count_lines
    # ------------------------------------------------------------------

    def count_lines(self, project_path: str) -> dict[str, int]:
        """Count lines of code by language."""
        counts: dict[str, int] = {}
        p = Path(project_path)

        for root, dirs, files in os.walk(p):
            dirs[:] = [d for d in dirs if d not in _IGNORE_DIRS and not d.startswith(".")]
            for fname in files:
                fpath = Path(root) / fname
                ext = fpath.suffix.lower()
                lang = _EXT_LANG_MAP.get(ext)
                if lang is None:
                    continue
                try:
                    lines = len(fpath.read_text(encoding="utf-8", errors="ignore").splitlines())
                except OSError:
                    continue
                lang_name = lang.value
                counts[lang_name] = counts.get(lang_name, 0) + lines

        return dict(sorted(counts.items(), key=lambda x: -x[1]))

    # ------------------------------------------------------------------
    # detect_language
    # ------------------------------------------------------------------

    def detect_language(self, project_path: str) -> dict[str, int]:
        """Detect language distribution by file count."""
        counts: dict[str, int] = {}
        p = Path(project_path)

        for root, dirs, files in os.walk(p):
            dirs[:] = [d for d in dirs if d not in _IGNORE_DIRS and not d.startswith(".")]
            for fname in files:
                ext = Path(fname).suffix.lower()
                lang = _EXT_LANG_MAP.get(ext)
                if lang:
                    lang_name = lang.value
                    counts[lang_name] = counts.get(lang_name, 0) + 1

        return dict(sorted(counts.items(), key=lambda x: -x[1]))

    # ------------------------------------------------------------------
    # find_dependencies
    # ------------------------------------------------------------------

    def find_dependencies(self, project_path: str) -> list[dict[str, Any]]:
        """Parse dependency files and return a unified list."""
        p = Path(project_path)
        all_deps: list[dict[str, Any]] = []

        parsers = [
            ("requirements.txt", _parse_requirements_txt),
            ("setup.py", _parse_requirements_txt),
            ("Pipfile", _parse_requirements_txt),
            ("pyproject.toml", _parse_requirements_txt),
            ("package.json", _parse_package_json),
            ("go.mod", _parse_go_mod),
            ("Cargo.toml", _parse_cargo_toml),
            ("Gemfile", _parse_gemfile),
            ("composer.json", _parse_composer_json),
        ]

        seen: set[str] = set()
        for fname, parser in parsers:
            fpath = p / fname
            for dep in parser(fpath):
                key = f"{dep['name']}:{dep['source']}"
                if key not in seen:
                    seen.add(key)
                    all_deps.append(dep)

        # Also check subdirectories for monorepos
        for child in p.iterdir():
            if child.is_dir() and child.name not in _IGNORE_DIRS and not child.name.startswith("."):
                for fname, parser in parsers:
                    fpath = child / fname
                    for dep in parser(fpath):
                        dep["name"] = f"{child.name}/{dep['name']}"
                        key = f"{dep['name']}:{dep['source']}"
                        if key not in seen:
                            seen.add(key)
                            all_deps.append(dep)

        return all_deps

    # ------------------------------------------------------------------
    # analyze_structure
    # ------------------------------------------------------------------

    def analyze_structure(self, project_path: str) -> dict[str, Any]:
        """Analyze directory tree, file types, and naming conventions."""
        p = Path(project_path)
        structure: dict[str, Any] = {
            "name": p.name,
            "total_files": 0,
            "total_dirs": 0,
            "file_types": {},
            "directory_tree": {},
            "naming_conventions": {"snake_case": 0, "camel_case": 0, "kebab_case": 0, "pascal_case": 0, "other": 0},
            "max_depth": 0,
            "large_files": [],
        }

        for root, dirs, files in os.walk(p):
            dirs[:] = [d for d in dirs if d not in _IGNORE_DIRS and not d.startswith(".")]
            rel = os.path.relpath(root, p)
            depth = len(Path(rel).parts) if rel != "." else 0
            structure["max_depth"] = max(structure["max_depth"], depth)
            structure["total_dirs"] += len(dirs)

            # Build tree
            tree_node = structure["directory_tree"]
            if rel != ".":
                for part in Path(rel).parts:
                    tree_node = tree_node.setdefault(part, {})

            for fname in files:
                structure["total_files"] += 1
                ext = Path(fname).suffix.lower() or "(no ext)"
                structure["file_types"][ext] = structure["file_types"].get(ext, 0) + 1

                # Naming convention detection
                stem = Path(fname).stem
                if re.match(r"^[a-z][a-z0-9]*(_[a-z0-9]+)*$", stem):
                    structure["naming_conventions"]["snake_case"] += 1
                elif re.match(r"^[A-Z][a-zA-Z0-9]*$", stem):
                    structure["naming_conventions"]["pascal_case"] += 1
                elif re.match(r"^[a-z][a-zA-Z0-9]*$", stem):
                    structure["naming_conventions"]["camel_case"] += 1
                elif re.match(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$", stem):
                    structure["naming_conventions"]["kebab_case"] += 1
                else:
                    structure["naming_conventions"]["other"] += 1

                # Large files (>100KB)
                try:
                    size = (Path(root) / fname).stat().st_size
                    if size > 100_000:
                        structure["large_files"].append({"path": str(Path(root) / fname), "size": size})
                except OSError:
                    pass

        structure["large_files"].sort(key=lambda x: -x["size"])
        return structure

    # ------------------------------------------------------------------
    # health_score
    # ------------------------------------------------------------------

    def health_score(self, project_path: str) -> dict[str, Any]:
        """Calculate overall project health (0-100)."""
        p = Path(project_path)
        score = 100.0
        deductions: list[dict[str, Any]] = []

        # Check for README
        if not any((p / name).exists() for name in ("README.md", "README.rst", "README.txt", "README")):
            score -= 10
            deductions.append({"reason": "No README file", "points": -10})

        # Check for license
        if not any((p / name).exists() for name in ("LICENSE", "LICENSE.md", "LICENSE.txt", "LICENCE")):
            score -= 5
            deductions.append({"reason": "No LICENSE file", "points": -5})

        # Check for test directory/files
        has_tests = False
        for root, dirs, files in os.walk(p):
            dirs[:] = [d for d in dirs if d not in _IGNORE_DIRS]
            for f in files:
                if "test" in f.lower() or "spec" in f.lower():
                    has_tests = True
                    break
            if has_tests:
                break
        if not has_tests:
            score -= 15
            deductions.append({"reason": "No test files found", "points": -15})

        # Check for CI config
        ci_files = [".github/workflows", ".gitlab-ci.yml", ".circleci", "Jenkinsfile", ".travis.yml", "azure-pipelines.yml"]
        has_ci = any((p / name).exists() or (p / name).is_dir() for name in ci_files)
        if not has_ci:
            score -= 5
            deductions.append({"reason": "No CI/CD configuration", "points": -5})

        # Check for .gitignore
        if not (p / ".gitignore").exists():
            score -= 3
            deductions.append({"reason": "No .gitignore file", "points": -3})

        # Check for type hints (Python)
        py_files = list(p.rglob("*.py"))
        if py_files:
            typed_files = 0
            for pf in py_files[:20]:  # Sample up to 20 files
                try:
                    content = pf.read_text(encoding="utf-8", errors="ignore")
                    if re.search(r":\s*(int|str|float|bool|list|dict|tuple|set|None|Optional|Union|List|Dict|Tuple|Set)", content):
                        typed_files += 1
                except OSError:
                    continue
            type_ratio = typed_files / min(len(py_files), 20) if py_files else 0
            if type_ratio < 0.3:
                score -= 5
                deductions.append({"reason": "Low type hint coverage", "points": -5})

        # Check for docstrings (Python)
        if py_files:
            documented = 0
            for pf in py_files[:20]:
                try:
                    content = pf.read_text(encoding="utf-8", errors="ignore")
                    tree = ast.parse(content)
                    for node in ast.walk(tree):
                        if isinstance(node, (ast.FunctionDef, ast.AsyncDef, ast.ClassDef)):
                            if ast.get_docstring(node):
                                documented += 1
                                break
                except (SyntaxError, OSError):
                    continue
            if py_files and documented / min(len(py_files), 20) < 0.3:
                score -= 5
                deductions.append({"reason": "Low docstring coverage", "points": -5})

        # Check for large files (>500 lines)
        large_count = 0
        for root, dirs, files in os.walk(p):
            dirs[:] = [d for d in dirs if d not in _IGNORE_DIRS and not d.startswith(".")]
            for f in files:
                fpath = Path(root) / f
                ext = fpath.suffix.lower()
                if ext in _EXT_LANG_MAP:
                    try:
                        line_count = len(fpath.read_text(encoding="utf-8", errors="ignore").splitlines())
                        if line_count > 500:
                            large_count += 1
                    except OSError:
                        continue
        if large_count > 3:
            score -= 5
            deductions.append({"reason": f"{large_count} files over 500 lines", "points": -5})

        score = max(0, min(100, score))
        return {
            "score": round(score),
            "grade": "A" if score >= 90 else "B" if score >= 80 else "C" if score >= 70 else "D" if score >= 60 else "F",
            "deductions": deductions,
        }

    # ------------------------------------------------------------------
    # find_entry_points
    # ------------------------------------------------------------------

    def find_entry_points(self, project_path: str) -> list[str]:
        """Detect main/entry point files."""
        p = Path(project_path)
        entry_points: list[str] = []

        # Common entry point names
        candidates = [
            "main.py", "app.py", "server.py", "index.py", "run.py", "manage.py", "wsgi.py", "asgi.py",
            "index.js", "server.js", "app.js", "main.js", "cli.js",
            "index.ts", "server.ts", "app.ts", "main.ts", "cli.ts",
            "main.go", "cmd",
            "src/main.rs", "src/lib.rs",
            "config.ru", "config.ru",
            "index.php", "public/index.php",
            "bin/console", "bin/rails",
        ]

        for cand in candidates:
            fpath = p / cand
            if fpath.exists():
                entry_points.append(str(fpath))
            elif fpath.is_dir():
                for child in fpath.iterdir():
                    if child.is_file() and child.suffix in (".py", ".js", ".ts", ".go", ".rs"):
                        entry_points.append(str(child))

        # Check package.json scripts
        pkg_json = p / "package.json"
        if pkg_json.exists():
            try:
                data = json.loads(pkg_json.read_text(encoding="utf-8"))
                main = data.get("main", "")
                if main:
                    mp = p / main
                    if mp.exists():
                        entry_points.append(str(mp))
                bin_entries = data.get("bin", {})
                if isinstance(bin_entries, dict):
                    for bname, bpath in bin_entries.items():
                        bp = p / bpath
                        if bp.exists():
                            entry_points.append(str(bp))
            except (json.JSONDecodeError, OSError):
                pass

        # Check Cargo.toml
        cargo = p / "Cargo.toml"
        if cargo.exists():
            try:
                content = cargo.read_text(encoding="utf-8")
                if "[[bin]]" in content:
                    for m in re.finditer(r'path\s*=\s*"([^"]+)"', content):
                        bp = p / m.group(1)
                        if bp.exists():
                            entry_points.append(str(bp))
            except OSError:
                pass

        return entry_points

    # ------------------------------------------------------------------
    # security_audit
    # ------------------------------------------------------------------

    def security_audit(self, project_path: str) -> list[CodeIssue]:
        """Check for known vulnerability patterns in source code."""
        issues: list[CodeIssue] = []
        p = Path(project_path)

        for root, dirs, files in os.walk(p):
            dirs[:] = [d for d in dirs if d not in _IGNORE_DIRS and not d.startswith(".")]
            for fname in files:
                fpath = Path(root) / fname
                ext = fpath.suffix.lower()
                lang = _EXT_LANG_MAP.get(ext)
                if lang is None:
                    continue

                try:
                    content = fpath.read_text(encoding="utf-8", errors="ignore")
                except OSError:
                    continue

                lang_name = lang.value
                for vuln in _VULNERABILITY_PATTERNS:
                    if vuln["language"] not in (lang_name, "all"):
                        continue
                    pattern = re.compile(vuln["pattern"])
                    for m in pattern.finditer(content):
                        line_num = content[:m.start()].count("\n") + 1
                        issues.append(CodeIssue(
                            file=str(fpath),
                            line=line_num,
                            severity=vuln["severity"],
                            code="SEC",
                            message=vuln["message"],
                            suggestion="Review and remediate the security issue.",
                        ))

        # Check for hardcoded secrets
        secret_patterns = [
            (re.compile(r"""(?:password|passwd|pwd)\s*=\s*['"][^'"]+['"]""", re.IGNORECASE), "Possible hardcoded password"),
            (re.compile(r"""(?:api_key|apikey|api_secret)\s*=\s*['"][^'"]+['"]""", re.IGNORECASE), "Possible hardcoded API key"),
            (re.compile(r"""(?:secret|token)\s*=\s*['"][^'"]+['"]""", re.IGNORECASE), "Possible hardcoded secret/token"),
            (re.compile(r"""(?:AWS_ACCESS_KEY_ID|AWS_SECRET_ACCESS_KEY)\s*=\s*['"][^'"]+['"]"""), "Possible AWS credentials"),
            (re.compile(r"""-----BEGIN\s+(RSA\s+)?PRIVATE\s+KEY-----"""), "Embedded private key"),
        ]

        for root, dirs, files in os.walk(p):
            dirs[:] = [d for d in dirs if d not in _IGNORE_DIRS and not d.startswith(".")]
            for fname in files:
                if fname.endswith((".py", ".js", ".ts", ".java", ".go", ".rb", ".php", ".env", ".cfg", ".ini", ".yaml", ".yml", ".json")):
                    fpath = Path(root) / fname
                    try:
                        content = fpath.read_text(encoding="utf-8", errors="ignore")
                    except OSError:
                        continue
                    for pat, msg in secret_patterns:
                        for m in pat.finditer(content):
                            line_num = content[:m.start()].count("\n") + 1
                            issues.append(CodeIssue(
                                file=str(fpath),
                                line=line_num,
                                severity=Severity.CRITICAL,
                                code="SEC-SECRET",
                                message=msg,
                                suggestion="Move secrets to environment variables or a secrets manager.",
                            ))

        return issues
