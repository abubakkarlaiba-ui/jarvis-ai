"""
Coding Agent — documentation generator.
========================================
Auto-generates README, docstrings, API docs, changelogs, contribution
guides, inline comments, and architecture docs using AST (Python) or
regex (other languages).
"""

from __future__ import annotations

import ast
import os
import re
import subprocess
from datetime import datetime
from textwrap import indent, dedent

from jarvis.core.coding.base import CodeLanguage


class DocGenerator:
    """Generates various forms of documentation for codebases."""

    # ─────────────────────────────────────────────────────────────────
    # README generation
    # ─────────────────────────────────────────────────────────────────

    def generate_readme(self, project_path: str) -> str:
        """Generate a README.md for a project based on its structure."""
        project_name = os.path.basename(os.path.abspath(project_path))

        # Gather file stats
        py_files: list[str] = []
        js_files: list[str] = []
        other_files: list[str] = []
        total_lines = 0

        for root, _dirs, files in os.walk(project_path):
            for f in files:
                ext = os.path.splitext(f)[1].lower()
                rel = os.path.relpath(os.path.join(root, f), project_path)
                if ext == ".py":
                    py_files.append(rel)
                elif ext in (".js", ".ts", ".jsx", ".tsx"):
                    js_files.append(rel)
                else:
                    other_files.append(rel)
                try:
                    with open(os.path.join(root, f), encoding="utf-8", errors="ignore") as fh:
                        total_lines += sum(1 for _ in fh)
                except (OSError, UnicodeDecodeError):
                    pass

        # Detect key files
        has_readme = os.path.isfile(os.path.join(project_path, "README.md"))
        has_requirements = os.path.isfile(os.path.join(project_path, "requirements.txt"))
        has_package_json = os.path.isfile(os.path.join(project_path, "package.json"))
        has_setup = os.path.isfile(os.path.join(project_path, "setup.py"))
        has_pyproject = os.path.isfile(os.path.join(project_path, "pyproject.toml"))
        has_docker = os.path.isfile(os.path.join(project_path, "Dockerfile"))
        has_ci = os.path.isdir(os.path.join(project_path, ".github"))

        # Detect main module from __init__.py or app.py
        main_module = ""
        for candidate in ("app.py", "main.py", "__init__.py", "index.js", "index.ts"):
            if os.path.isfile(os.path.join(project_path, candidate)):
                main_module = candidate
                break

        # Detect test directory
        has_tests = os.path.isdir(os.path.join(project_path, "tests")) or \
                    os.path.isdir(os.path.join(project_path, "test"))

        lines: list[str] = []
        lines.append(f"# {project_name}\n")

        # Try to read existing README description
        desc = self._extract_project_description(project_path)
        if desc:
            lines.append(f"{desc}\n")
        else:
            lines.append(f"Project with {len(py_files) + len(js_files) + len(other_files)} source files "
                         f"({total_lines:,} lines).\n")

        # Tech stack
        lines.append("## Tech Stack\n")
        if py_files:
            lines.append("- Python")
        if js_files:
            lines.append("- JavaScript / TypeScript")
        if has_package_json:
            lines.append("- Node.js")
        if has_docker:
            lines.append("- Docker")
        lines.append("")

        # Installation
        lines.append("## Installation\n")
        if has_requirements:
            lines.append("```bash\npip install -r requirements.txt\n```")
        elif has_setup or has_pyproject:
            lines.append("```bash\npip install .\n```")
        if has_package_json:
            lines.append("```bash\nnpm install\n```")
        lines.append("")

        # Usage
        if main_module:
            lines.append("## Usage\n")
            if main_module.endswith(".py"):
                lines.append(f"```bash\npython {main_module}\n```")
            else:
                lines.append(f"```bash\nnode {main_module}\n```")
            lines.append("")

        # Project structure
        lines.append("## Project Structure\n")
        lines.append("```")
        lines.append(f"{project_name}/")
        dirs_shown: set[str] = set()
        for f in sorted(py_files + js_files + other_files)[:30]:
            parts = f.split(os.sep)
            for i in range(len(parts) - 1):
                d = os.sep.join(parts[:i + 1])
                if d not in dirs_shown:
                    dirs_shown.add(d)
                    lines.append(f"  {'  ' * i}{parts[i]}/")
            lines.append(f"  {'  ' * (len(parts) - 1)}{parts[-1]}")
        if len(py_files) + len(js_files) + len(other_files) > 30:
            lines.append("  ...")
        lines.append("```\n")

        # Testing
        if has_tests:
            lines.append("## Testing\n")
            lines.append("```bash\npytest\n```\nn")

        # Contributing
        lines.append("## Contributing\n")
        lines.append("Contributions welcome. Please open an issue or submit a pull request.\n")

        # License
        if os.path.isfile(os.path.join(project_path, "LICENSE")):
            lines.append("## License\n")
            lines.append("See [LICENSE](LICENSE) for details.\n")

        return "\n".join(lines)

    def _extract_project_description(self, project_path: str) -> str:
        """Try to extract a description from setup.py, pyproject.toml, or package.json."""
        setup_py = os.path.join(project_path, "setup.py")
        if os.path.isfile(setup_py):
            try:
                with open(setup_py, encoding="utf-8") as fh:
                    content = fh.read()
                m = re.search(r'description\s*=\s*["\'](.+?)["\']', content)
                if m:
                    return m.group(1)
            except (OSError, UnicodeDecodeError):
                pass

        pyproject = os.path.join(project_path, "pyproject.toml")
        if os.path.isfile(pyproject):
            try:
                with open(pyproject, encoding="utf-8") as fh:
                    content = fh.read()
                m = re.search(r'description\s*=\s*"(.+?)"', content)
                if m:
                    return m.group(1)
            except (OSError, UnicodeDecodeError):
                pass

        pkg_json = os.path.join(project_path, "package.json")
        if os.path.isfile(pkg_json):
            try:
                with open(pkg_json, encoding="utf-8") as fh:
                    content = fh.read()
                m = re.search(r'"description"\s*:\s*"(.+?)"', content)
                if m:
                    return m.group(1)
            except (OSError, UnicodeDecodeError):
                pass

        return ""

    # ─────────────────────────────────────────────────────────────────
    # Docstring generation / improvement
    # ─────────────────────────────────────────────────────────────────

    def generate_docstring(self, code: str, language: CodeLanguage,
                           style: str = "google") -> str:
        """Add or improve docstrings in code. Supported styles: google, numpy, sphinx."""
        if language == CodeLanguage.PYTHON:
            return self._add_py_docstrings(code, style)
        return self._add_generic_docstrings(code, language, style)

    def _add_py_docstrings(self, code: str, style: str) -> str:
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return code

        lines = code.splitlines(keepends=True)
        insertions: list[tuple[int, str]] = []

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            if ast.get_docstring(node):
                continue

            docstring = self._build_py_docstring(node, style)
            if not docstring:
                continue

            body = node.body
            first_stmt = body[0]
            indent_level = first_stmt.col_offset if hasattr(first_stmt, "col_offset") else 0
            quote = '"""'
            ds_lines = [
                " " * indent_level + quote + "\n",
                indent(docstring, " " * (indent_level + 4)) + "\n",
                " " * indent_level + quote + "\n",
            ]
            insertions.append((first_stmt.lineno - 1, ds_lines))

        # Insert from bottom to top so line numbers stay valid
        insertions.sort(key=lambda x: x[0], reverse=True)
        for lineno, ds_lines in insertions:
            for i, dl in enumerate(reversed(ds_lines)):
                lines.insert(lineno, dl)

        return "".join(lines)

    def _build_py_docstring(self, node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef,
                            style: str) -> str:
        if isinstance(node, ast.ClassDef):
            parts = [f"Class {node.name}."]
            return self._format_docstring("\n".join(parts), style)

        parts: list[str] = []
        func_name = node.name

        # Args
        args = node.args
        all_args: list[str] = []
        defaults_offset = len(args.args) - len(args.defaults)

        for i, arg in enumerate(args.args):
            if arg.arg in ("self", "cls"):
                continue
            annotation = ""
            if arg.annotation:
                annotation = f" ({ast.unparse(arg.annotation)})"
            all_args.append(f"{arg.arg}{annotation}")

        for i, arg in enumerate(args.kwonlyargs):
            annotation = ""
            if arg.annotation:
                annotation = f" ({ast.unparse(arg.annotation)})"
            all_args.append(f"{arg.arg}{annotation}")

        if args.vararg:
            annotation = ""
            if args.vararg.annotation:
                annotation = f" ({ast.unparse(args.vararg.annotation)})"
            all_args.append(f"*{args.vararg.arg}{annotation}")

        if args.kwarg:
            annotation = ""
            if args.kwarg.annotation:
                annotation = f" ({ast.unparse(args.kwarg.annotation)})"
            all_args.append(f"**{args.kwarg.arg}{annotation}")

        # Returns
        returns = ""
        if node.returns:
            returns = ast.unparse(node.returns)

        parts.append(f"Perform {func_name} operation.")

        if all_args:
            parts.append("")
            if style == "google":
                parts.append("Args:")
                for a in all_args:
                    parts.append(f"    {a}: Description.")
            elif style == "numpy":
                parts.append("Parameters")
                parts.append("----------")
                for a in all_args:
                    parts.append(f"{a} : type")
                    parts.append("    Description.")
            elif style == "sphinx":
                parts.append("")
                for a in all_args.split(", "):
                    parts.append(f":param {a}: Description.")

        if returns:
            parts.append("")
            if style == "google":
                parts.append(f"Returns:\n    {returns}: Description.")
            elif style == "numpy":
                parts.append("Returns")
                parts.append("-------")
                parts.append(f"{returns}")
                parts.append("    Description.")
            elif style == "sphinx":
                parts.append(f":returns: Description of {returns}.")

        return "\n".join(parts)

    def _add_generic_docstrings(self, code: str, language: CodeLanguage, style: str) -> str:
        """Add JSDoc / Javadoc style comments to functions in non-Python code."""
        lines = code.splitlines(keepends=True)
        func_pattern = re.compile(
            r'^(?:(?:export\s+|public\s+|private\s+|protected\s+|static\s+|async\s+)*'
            r'(?:function\s+(\w+)|'
            r'(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?\(|'
            r'(?:\w+\s+)+(\w+)\s*\([^)]*\)\s*(?:\{|=>))'
        )

        insertions: list[tuple[int, str]] = []
        for idx, line in enumerate(lines):
            m = func_pattern.search(line)
            if m:
                func_name = next(g for g in m.groups() if g)
                indent_level = len(line) - len(line.lstrip())
                prefix = " " * indent_level
                comment = f"{prefix}/**\n{prefix} * {func_name} function.\n{prefix} */\n"
                insertions.append((idx, comment))

        insertions.sort(key=lambda x: x[0], reverse=True)
        for idx, comment in insertions:
            lines.insert(idx, comment)

        return "".join(lines)

    # ─────────────────────────────────────────────────────────────────
    # API documentation
    # ─────────────────────────────────────────────────────────────────

    def generate_api_docs(self, code: str, language: CodeLanguage) -> str:
        """Generate API documentation from code (functions, classes, methods)."""
        if language == CodeLanguage.PYTHON:
            return self._generate_py_api_docs(code)
        return self._generate_generic_api_docs(code, language)

    def _generate_py_api_docs(self, code: str) -> str:
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return "Unable to parse code."

        sections: list[str] = []
        sections.append("# API Documentation\n")

        classes = [n for n in ast.iter_child_nodes(tree) if isinstance(n, ast.ClassDef)]
        funcs = [n for n in ast.iter_child_nodes(tree)
                 if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]

        if classes:
            sections.append("## Classes\n")
            for cls in classes:
                docstring = ast.get_docstring(cls) or "No description."
                sections.append(f"### {cls.name}\n")
                sections.append(f"{docstring}\n")

                methods = [n for n in cls.body
                           if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
                if methods:
                    sections.append("**Methods:**\n")
                    for m in methods:
                        sig = self._py_func_signature(m)
                        mdoc = ast.get_docstring(m) or "No description."
                        sections.append(f"- `{cls.name}.{sig}` — {mdoc.splitlines()[0]}\n")
                sections.append("")

        if funcs:
            sections.append("## Functions\n")
            for f in funcs:
                sig = self._py_func_signature(f)
                docstring = ast.get_docstring(f) or "No description."
                sections.append(f"### {f.name}\n")
                sections.append(f"```python\n{sig}\n```\n")
                sections.append(f"{docstring}\n")

        return "".join(sections)

    def _py_func_signature(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
        parts: list[str] = []
        args = node.args

        all_args: list[str] = []
        for arg in args.args:
            if arg.arg in ("self", "cls"):
                continue
            ann = f": {ast.unparse(arg.annotation)}" if arg.annotation else ""
            all_args.append(f"{arg.arg}{ann}")

        for arg in args.kwonlyargs:
            ann = f": {ast.unparse(arg.annotation)}" if arg.annotation else ""
            all_args.append(f"{arg.arg}{ann}")

        if args.vararg:
            all_args.append(f"*{args.vararg.arg}")
        if args.kwarg:
            all_args.append(f"**{args.kwarg.arg}")

        ret = f" -> {ast.unparse(node.returns)}" if node.returns else ""
        return f"{node.name}({', '.join(all_args)}){ret}"

    def _generate_generic_api_docs(self, code: str, language: CodeLanguage) -> str:
        lines = code.splitlines()
        sections: list[str] = ["# API Documentation\n"]

        func_pattern = re.compile(
            r'(?:(?:export\s+|public\s+|private\s+|static\s+|async\s+)*'
            r'(?:function\s+(\w+)|(?:\w+\s+)+(\w+)\s*\([^)]*\)))'
        )

        for idx, line in enumerate(lines):
            m = func_pattern.search(line)
            if m:
                name = next(g for g in m.groups() if g)
                # grab preceding JSDoc comment
                doc_lines: list[str] = []
                for back in range(1, min(5, idx + 1)):
                    prev = lines[idx - back].strip()
                    if prev.startswith("/**") or prev.startswith("*") or prev.startswith("*/"):
                        doc_lines.insert(0, prev)
                    elif prev.startswith("//"):
                        doc_lines.insert(0, prev)
                    else:
                        break
                doc = " ".join(l.strip("/* ") for l in doc_lines) if doc_lines else "No description."
                sections.append(f"### {name}\n")
                sections.append(f"```{language.value}\n{line.strip()}\n```\n")
                sections.append(f"{doc}\n")

        return "".join(sections)

    # ─────────────────────────────────────────────────────────────────
    # Changelog generation
    # ─────────────────────────────────────────────────────────────────

    def generate_changelog(self, project_path: str) -> str:
        """Generate CHANGELOG.md from git history."""
        log = self._git_log(project_path)
        if not log:
            return "# Changelog\n\nNo git history found.\n"

        entries = self._parse_git_log(log)
        lines: list[str] = ["# Changelog\n"]
        lines.append(f"_Generated on {datetime.now().strftime('%Y-%m-%d')}_\n")

        for date, subject in entries:
            lines.append(f"## {date}\n")
            lines.append(f"- {subject}\n")

        return "".join(lines)

    def _git_log(self, project_path: str) -> str:
        try:
            result = subprocess.run(
                ["git", "log", "--pretty=format:%ad | %s", "--date=short", "-50"],
                cwd=project_path, capture_output=True, text=True, timeout=10,
            )
            return result.stdout
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            return ""

    def _parse_git_log(self, log: str) -> list[tuple[str, str]]:
        entries: list[tuple[str, str]] = []
        for line in log.strip().splitlines():
            if "|" in line:
                parts = line.split("|", 1)
                entries.append((parts[0].strip(), parts[1].strip()))
        return entries

    # ─────────────────────────────────────────────────────────────────
    # Contributing guide
    # ─────────────────────────────────────────────────────────────────

    def generate_contribution_guide(self, project_path: str) -> str:
        """Generate CONTRIBUTING.md."""
        project_name = os.path.basename(os.path.abspath(project_path))
        has_tests = os.path.isdir(os.path.join(project_path, "tests")) or \
                    os.path.isdir(os.path.join(project_path, "test"))
        has_lint = os.path.isfile(os.path.join(project_path, ".flake8")) or \
                   os.path.isfile(os.path.join(project_path, "pyproject.toml"))
        has_ci = os.path.isdir(os.path.join(project_path, ".github"))

        sections = [
            f"# Contributing to {project_name}\n",
            "Thank you for considering contributing!\n",
            "## Getting Started\n",
            "1. Fork the repository",
            "2. Create a feature branch (`git checkout -b feature/amazing-feature`)",
            "3. Make your changes",
            "4. Run tests",
            "5. Commit your changes (`git commit -m 'Add amazing feature'`)",
            "6. Push to the branch (`git push origin feature/amazing-feature`)",
            "7. Open a Pull Request\n",
        ]

        if has_tests:
            sections.extend([
                "## Running Tests\n",
                "```bash\npytest\n```\n",
            ])

        if has_lint:
            sections.extend([
                "## Code Style\n",
                "Please follow the project linting configuration.\n",
                "```bash\nflake8 .\n```\n",
            ])

        if has_ci:
            sections.extend([
                "## CI/CD\n",
                "All pull requests must pass CI checks before merging.\n",
            ])

        sections.extend([
            "## Reporting Issues\n",
            "Use the issue tracker to report bugs or request features.\n",
            "Please include:\n",
            "- Steps to reproduce",
            "- Expected behavior",
            "- Actual behavior\n",
        ])

        return "\n".join(sections)

    # ─────────────────────────────────────────────────────────────────
    # Inline code comments
    # ─────────────────────────────────────────────────────────────────

    def generate_code_comments(self, code: str, language: CodeLanguage) -> str:
        """Add inline comments to uncommented code."""
        if language == CodeLanguage.PYTHON:
            return self._add_py_comments(code)
        return self._add_generic_comments(code, language)

    def _add_py_comments(self, code: str) -> str:
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return code

        lines = code.splitlines(keepends=True)
        insertions: list[tuple[int, str]] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and not ast.get_docstring(node):
                targets = ", ".join(ast.unparse(t) for t in node.targets)
                insert_line = node.lineno - 1
                indent_level = node.col_offset
                comment = " " * indent_level + f"# Assign to {targets}\n"
                insertions.append((insert_line, comment))
            elif isinstance(node, ast.Return) and node.value:
                insert_line = node.lineno - 1
                indent_level = node.col_offset
                comment = " " * indent_level + f"# Return {ast.unparse(node.value)[:60]}\n"
                insertions.append((insert_line, comment))

        # Deduplicate and insert from bottom
        seen: set[int] = set()
        unique: list[tuple[int, str]] = []
        for pos, c in insertions:
            if pos not in seen:
                seen.add(pos)
                unique.append((pos, c))
        unique.sort(key=lambda x: x[0], reverse=True)

        for pos, comment in unique:
            lines.insert(pos, comment)

        return "".join(lines)

    def _add_generic_comments(self, code: str, language: CodeLanguage) -> str:
        lines = code.splitlines(keepends=True)
        comment_char = "//" if language in (
            CodeLanguage.JAVASCRIPT, CodeLanguage.TYPESCRIPT, CodeLanguage.JAVA,
            CodeLanguage.GO, CodeLanguage.RUST, CodeLanguage.CPP, CodeLanguage.C,
            CodeLanguage.CSHARP, CodeLanguage.SWIFT, CodeLanguage.KOTLIN,
        ) else "#"

        func_pattern = re.compile(
            r'^(?:(?:export\s+|public\s+|private\s+|static\s+|async\s+)*'
            r'(?:function\s+(\w+)|(\w+)\s*\([^)]*\)\s*(?:\{|=>)))'
        )

        insertions: list[tuple[int, str]] = []
        for idx, line in enumerate(lines):
            m = func_pattern.search(line)
            if m:
                name = next(g for g in m.groups() if g)
                indent_level = len(line) - len(line.lstrip())
                comment = " " * indent_level + f"{comment_char} {name} implementation\n"
                insertions.append((idx, comment))

        insertions.sort(key=lambda x: x[0], reverse=True)
        for idx, comment in insertions:
            lines.insert(idx, comment)

        return "".join(lines)

    # ─────────────────────────────────────────────────────────────────
    # Docstring formatting
    # ─────────────────────────────────────────────────────────────────

    def format_docstring(self, docstring: str, style: str) -> str:
        """Reformat a docstring between google, numpy, and sphinx styles."""
        parsed = self._parse_existing_docstring(docstring)

        if style == "google":
            return self._to_google(parsed)
        elif style == "numpy":
            return self._to_numpy(parsed)
        elif style == "sphinx":
            return self._to_sphinx(parsed)
        return docstring

    def _parse_existing_docstring(self, docstring: str) -> dict:
        """Best-effort parse of an existing docstring."""
        result: dict = {"summary": "", "description": "", "args": [], "returns": ""}
        lines = docstring.strip().splitlines()

        if not lines:
            return result

        result["summary"] = lines[0].strip()

        section = "desc"
        for line in lines[1:]:
            stripped = line.strip()
            lower = stripped.lower()

            if lower.startswith("args:") or lower.startswith("parameters"):
                section = "args"
                continue
            elif lower.startswith("returns:") or lower.startswith("return"):
                section = "returns"
                continue
            elif lower.startswith("raises:") or lower.startswith("raise"):
                section = "raises"
                continue

            if section == "args" and stripped and ":" in stripped:
                result["args"].append(stripped)
            elif section == "returns" and stripped:
                result["returns"] = stripped

        return result

    def _to_google(self, parsed: dict) -> str:
        parts = [parsed["summary"]]
        if parsed["description"]:
            parts.append(parsed["description"])
        if parsed["args"]:
            parts.append("\nArgs:")
            for arg in parsed["args"]:
                parts.append(f"    {arg}")
        if parsed["returns"]:
            parts.append(f"\nReturns:\n    {parsed['returns']}")
        return "\n".join(parts)

    def _to_numpy(self, parsed: dict) -> str:
        parts = [parsed["summary"]]
        if parsed["description"]:
            parts.append(parsed["description"])
        if parsed["args"]:
            parts.append("\nParameters\n----------")
            for arg in parsed["args"]:
                parts.append(f"{arg}")
        if parsed["returns"]:
            parts.append(f"\nReturns\n-------\n{parsed['returns']}")
        return "\n".join(parts)

    def _to_sphinx(self, parsed: dict) -> str:
        parts = [parsed["summary"]]
        if parsed["description"]:
            parts.append(parsed["description"])
        for arg in parsed["args"]:
            name = arg.split(":")[0].strip() if ":" in arg else arg
            parts.append(f":param {name}: Description.")
        if parsed["returns"]:
            parts.append(f":returns: {parsed['returns']}")
        return "\n".join(parts)

    # ─────────────────────────────────────────────────────────────────
    # Architecture documentation
    # ─────────────────────────────────────────────────────────────────

    def generate_architecture_doc(self, project_path: str) -> str:
        """Generate architecture documentation by analyzing project structure."""
        project_name = os.path.basename(os.path.abspath(project_path))

        modules: dict[str, list[str]] = {}
        imports_graph: dict[str, set[str]] = {}
        entry_points: list[str] = []

        for root, _dirs, files in os.walk(project_path):
            for f in files:
                if not f.endswith(".py"):
                    continue
                full = os.path.join(root, f)
                rel = os.path.relpath(full, project_path)
                mod = os.path.dirname(rel).replace(os.sep, ".") or project_name

                if mod not in modules:
                    modules[mod] = []
                modules[mod].append(f)

                # Check for entry points
                if f in ("__main__.py", "app.py", "main.py", "manage.py"):
                    entry_points.append(rel)

                # Parse imports
                try:
                    with open(full, encoding="utf-8", errors="ignore") as fh:
                        tree = ast.parse(fh.read())
                    local_imports: set[str] = set()
                    for node in ast.walk(tree):
                        if isinstance(node, ast.Import):
                            for alias in node.names:
                                if alias.name.startswith(project_name.lower()):
                                    local_imports.add(alias.name)
                        elif isinstance(node, ast.ImportFrom):
                            if node.module and node.module.startswith(project_name.lower()):
                                local_imports.add(node.module)
                    imports_graph[mod] = local_imports
                except (SyntaxError, OSError):
                    pass

        # Build document
        sections: list[str] = [f"# Architecture — {project_name}\n"]

        # Overview
        total_modules = len(modules)
        total_files = sum(len(v) for v in modules.values())
        sections.append(f"## Overview\n")
        sections.append(f"This project contains **{total_modules}** modules with **{total_files}** Python files.\n")

        # Entry points
        if entry_points:
            sections.append("## Entry Points\n")
            for ep in entry_points:
                sections.append(f"- `{ep}`")
            sections.append("")

        # Module structure
        sections.append("## Module Structure\n")
        for mod in sorted(modules.keys()):
            sections.append(f"### `{mod}`\n")
            for fname in sorted(modules[mod]):
                sections.append(f"- {fname}")
            sections.append("")

        # Dependency graph
        if imports_graph:
            sections.append("## Internal Dependencies\n")
            for mod in sorted(imports_graph.keys()):
                deps = imports_graph[mod]
                if deps:
                    sections.append(f"**{mod}** imports:")
                    for d in sorted(deps):
                        sections.append(f"  - `{d}`")
                    sections.append("")

        # Data flow
        sections.append("## Data Flow\n")
        sections.append("```")
        for mod in sorted(imports_graph.keys()):
            deps = imports_graph[mod]
            for d in deps:
                sections.append(f"  {mod} --> {d}")
        sections.append("```\n")

        return "\n".join(sections)
