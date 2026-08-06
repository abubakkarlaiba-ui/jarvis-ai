"""
Test Runner — discover and run tests across multiple frameworks.
===============================================================
Uses subprocess to execute actual test commands and parse output.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Any

from jarvis.core.coding.base import (
    CodeLanguage,
    CodingResult,
    TaskType,
    TestResult,
)


# ---------------------------------------------------------------------------
# Framework detection and command mapping
# ---------------------------------------------------------------------------

_FRAMEWORK_COMMANDS: dict[str, dict[str, Any]] = {
    "pytest": {
        "detect_files": ["pytest.ini", "pyproject.toml", "setup.cfg", "conftest.py"],
        "test_patterns": ["test_*.py", "*_test.py"],
        "cmd": "python -m pytest {path} -v --tb=short{filter}",
        "filter_cmd": " -k {filter}",
        "coverage_cmd": "python -m pytest {path} --cov=. --cov-report=json --cov-report=term",
        "parse": "pytest",
    },
    "unittest": {
        "detect_files": [],
        "test_patterns": ["test_*.py", "*_test.py"],
        "cmd": "python -m unittest discover -s {path} -v{filter}",
        "filter_cmd": " -k {filter}",
        "coverage_cmd": "python -m coverage run -m unittest discover -s {path}; python -m coverage json",
        "parse": "unittest",
    },
    "jest": {
        "detect_files": ["jest.config.js", "jest.config.ts", "jest.config.json", "package.json"],
        "test_patterns": ["*.test.js", "*.test.ts", "*.spec.js", "*.spec.ts", "__tests__/**/*.js", "__tests__/**/*.ts"],
        "cmd": "npx jest{filter} --verbose",
        "filter_cmd": " -t {filter}",
        "coverage_cmd": "npx jest --coverage{filter}",
        "parse": "jest",
    },
    "mocha": {
        "detect_files": [".mocharc.yml", ".mocharc.js", ".mocharc.json", "mocha.opts"],
        "test_patterns": ["test/**/*.js", "test/**/*.ts", "*.test.js", "*.spec.js"],
        "cmd": "npx mocha {path}{filter} --reporter spec",
        "filter_cmd": " --grep {filter}",
        "coverage_cmd": "npx nyc mocha {path}",
        "parse": "mocha",
    },
    "vitest": {
        "detect_files": ["vitest.config.js", "vitest.config.ts", "vitest.config.mjs"],
        "test_patterns": ["*.test.js", "*.test.ts", "*.spec.js", "*.spec.ts"],
        "cmd": "npx vitest run{filter}",
        "filter_cmd": " -t {filter}",
        "coverage_cmd": "npx vitest run --coverage{filter}",
        "parse": "vitest",
    },
    "go test": {
        "detect_files": ["go.mod"],
        "test_patterns": ["*_test.go"],
        "cmd": "go test -v ./...{filter}",
        "filter_cmd": " -run {filter}",
        "coverage_cmd": "go test -v -coverprofile=coverage.out ./...; go tool cover -func=coverage.out",
        "parse": "go",
    },
    "cargo test": {
        "detect_files": ["Cargo.toml"],
        "test_patterns": ["src/**/*.rs", "tests/**/*.rs"],
        "cmd": "cargo test{filter} -- --nocapture",
        "filter_cmd": " {filter}",
        "coverage_cmd": "cargo tarpaulin --out Json{filter}",
        "parse": "cargo",
    },
    "rspec": {
        "detect_files": [".rspec", "Gemfile"],
        "test_patterns": ["spec/**/*_spec.rb", "spec/**/*_test.rb"],
        "cmd": "bundle exec rspec{filter} --format documentation",
        "filter_cmd": " -e {filter}",
        "coverage_cmd": "bundle exec rspec{filter} --require spec_helper",
        "parse": "rspec",
    },
    "phpunit": {
        "detect_files": ["phpunit.xml", "phpunit.xml.dist", "composer.json"],
        "test_patterns": ["tests/**/*Test.php", "tests/**/*_test.php"],
        "cmd": "vendor/bin/phpunit{filter} --verbose",
        "filter_cmd": " --filter {filter}",
        "coverage_cmd": "vendor/bin/phpunit --coverage-text{filter}",
        "parse": "phpunit",
    },
}

_FRAMEWORK_LANG_MAP: dict[str, CodeLanguage] = {
    "pytest": CodeLanguage.PYTHON,
    "unittest": CodeLanguage.PYTHON,
    "jest": CodeLanguage.JAVASCRIPT,
    "mocha": CodeLanguage.JAVASCRIPT,
    "vitest": CodeLanguage.TYPESCRIPT,
    "go test": CodeLanguage.GO,
    "cargo test": CodeLanguage.RUST,
    "rspec": CodeLanguage.RUBY,
    "phpunit": CodeLanguage.PHP,
}


# ---------------------------------------------------------------------------
# Output parsers
# ---------------------------------------------------------------------------

def _parse_pytest(output: str) -> dict[str, Any]:
    result: dict[str, Any] = {"total": 0, "passed": 0, "failed": 0, "skipped": 0, "errors": 0, "failures": []}
    summary_match = re.search(r"=+\s*(\d+)\s+passed.*?(\d+)\s+failed.*?(\d+)\s+skipped", output)
    if summary_match:
        result["passed"] = int(summary_match.group(1))
        result["failed"] = int(summary_match.group(2))
        result["skipped"] = int(summary_match.group(3))
    else:
        passed = len(re.findall(r"PASSED", output))
        failed = len(re.findall(r"FAILED", output))
        skipped = len(re.findall(r"SKIPPED", output))
        errors = len(re.findall(r"ERROR", output))
        result["passed"] = passed
        result["failed"] = failed
        result["skipped"] = skipped
        result["errors"] = errors
    result["total"] = result["passed"] + result["failed"] + result["skipped"] + result["errors"]
    for m in re.finditer(r"FAILED\s+(\S+)", output):
        result["failures"].append({"test": m.group(1), "message": "FAILED"})
    return result


def _parse_unittest(output: str) -> dict[str, Any]:
    result: dict[str, Any] = {"total": 0, "passed": 0, "failed": 0, "skipped": 0, "errors": 0, "failures": []}
    run_match = re.search(r"Ran\s+(\d+)\s+test", output)
    if run_match:
        result["total"] = int(run_match.group(1))
    if "OK" in output:
        result["passed"] = result["total"]
    else:
        result["failed"] = len(re.findall(r"FAIL:\s+(\S+)", output))
        result["errors"] = len(re.findall(r"ERROR:\s+(\S+)", output))
        result["skipped"] = len(re.findall(r"Skipping\s+(\S+)", output))
        result["passed"] = result["total"] - result["failed"] - result["errors"] - result["skipped"]
    for m in re.finditer(r"FAIL:\s+(\S+)\s*.*?AssertionError:\s*(.*)", output, re.DOTALL):
        result["failures"].append({"test": m.group(1), "message": m.group(2).strip()})
    return result


def _parse_jest(output: str) -> dict[str, Any]:
    result: dict[str, Any] = {"total": 0, "passed": 0, "failed": 0, "skipped": 0, "errors": 0, "failures": []}
    summary = re.search(r"Tests:\s+(\d+)\s+failed.*?(\d+)\s+passed", output)
    if summary:
        result["failed"] = int(summary.group(1))
        result["passed"] = int(summary.group(2))
    else:
        passed = len(re.findall(r"\s+✓\s", output))
        failed = len(re.findall(r"\s+✕\s", output))
        result["passed"] = passed
        result["failed"] = failed
    result["total"] = result["passed"] + result["failed"] + result["skipped"]
    for m in re.finditer(r"FAIL\s+(\S+)", output):
        result["failures"].append({"test": m.group(1), "message": "FAILED"})
    return result


def _parse_mocha(output: str) -> dict[str, Any]:
    result: dict[str, Any] = {"total": 0, "passed": 0, "failed": 0, "skipped": 0, "errors": 0, "failures": []}
    summary = re.search(r"(\d+)\s+passing.*?(\d+)\s+failing", output)
    if summary:
        result["passed"] = int(summary.group(1))
        result["failed"] = int(summary.group(2))
    result["total"] = result["passed"] + result["failed"]
    for m in re.finditer(r"\d+\)\s+(.+?)$", output, re.MULTILINE):
        result["failures"].append({"test": m.group(1).strip(), "message": "FAILED"})
    return result


def _parse_vitest(output: str) -> dict[str, Any]:
    result: dict[str, Any] = {"total": 0, "passed": 0, "failed": 0, "skipped": 0, "errors": 0, "failures": []}
    summary = re.search(r"Tests\s+(\d+)\s+passed.*?(\d+)\s+failed", output)
    if summary:
        result["passed"] = int(summary.group(1))
        result["failed"] = int(summary.group(2))
    else:
        result["passed"] = len(re.findall(r"✓", output))
        result["failed"] = len(re.findall(r"×", output))
    result["total"] = result["passed"] + result["failed"]
    for m in re.finditer(r"FAIL\s+(\S+)", output):
        result["failures"].append({"test": m.group(1), "message": "FAILED"})
    return result


def _parse_go(output: str) -> dict[str, Any]:
    result: dict[str, Any] = {"total": 0, "passed": 0, "failed": 0, "skipped": 0, "errors": 0, "failures": []}
    result["passed"] = len(re.findall(r"--- PASS:", output))
    result["failed"] = len(re.findall(r"--- FAIL:", output))
    result["skipped"] = len(re.findall(r"--- SKIP:", output))
    result["total"] = result["passed"] + result["failed"] + result["skipped"]
    for m in re.finditer(r"--- FAIL:\s+(\S+)", output):
        result["failures"].append({"test": m.group(1), "message": "FAILED"})
    return result


def _parse_cargo(output: str) -> dict[str, Any]:
    result: dict[str, Any] = {"total": 0, "passed": 0, "failed": 0, "skipped": 0, "errors": 0, "failures": []}
    result["passed"] = len(re.findall(r"test\s+\S+\s+\.\.\.\s+ok", output))
    result["failed"] = len(re.findall(r"test\s+\S+\s+\.\.\.\s+FAILED", output))
    result["skipped"] = len(re.findall(r"test\s+\S+\s+\.\.\.\s+ignored", output))
    result["total"] = result["passed"] + result["failed"] + result["skipped"]
    for m in re.finditer(r"---- (\S+)\s+stdout", output):
        result["failures"].append({"test": m.group(1), "message": "FAILED"})
    return result


def _parse_rspec(output: str) -> dict[str, Any]:
    result: dict[str, Any] = {"total": 0, "passed": 0, "failed": 0, "skipped": 0, "errors": 0, "failures": []}
    summary = re.search(r"(\d+)\s+examples?,\s+(\d+)\s+failures?", output)
    if summary:
        result["total"] = int(summary.group(1))
        result["failed"] = int(summary.group(2))
        result["passed"] = result["total"] - result["failed"]
    for m in re.finditer(r"rspec\s+(\S+\.rb:\d+)", output):
        result["failures"].append({"test": m.group(1), "message": "FAILED"})
    return result


def _parse_phpunit(output: str) -> dict[str, Any]:
    result: dict[str, Any] = {"total": 0, "passed": 0, "failed": 0, "skipped": 0, "errors": 0, "failures": []}
    summary = re.search(r"Tests:\s+(\d+),\s+Assertions:\s+(\d+),\s+Failures:\s+(\d+),\s+Errors:\s+(\d+)", output)
    if summary:
        result["total"] = int(summary.group(1))
        result["failed"] = int(summary.group(3))
        result["errors"] = int(summary.group(4))
        result["passed"] = result["total"] - result["failed"] - result["errors"]
    for m in re.finditer(r"Failed asserting that\s+(.+)", output):
        result["failures"].append({"test": "assertion", "message": m.group(1).strip()})
    return result


_PARSERS: dict[str, Any] = {
    "pytest": _parse_pytest,
    "unittest": _parse_unittest,
    "jest": _parse_jest,
    "mocha": _parse_mocha,
    "vitest": _parse_vitest,
    "go": _parse_go,
    "cargo": _parse_cargo,
    "rspec": _parse_rspec,
    "phpunit": _parse_phpunit,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _detect_framework(project_path: str) -> str | None:
    """Auto-detect the test framework from project config files."""
    p = Path(project_path)
    for fw, info in _FRAMEWORK_COMMANDS.items():
        for det in info["detect_files"]:
            if (p / det).exists():
                return fw
    return None


def _detect_language_frameworks(project_path: str, language: str) -> list[str]:
    """Return frameworks that match a given language."""
    lang_enum = CodeLanguage.from_ext(language)
    return [
        fw for fw, lang in _FRAMEWORK_LANG_MAP.items()
        if lang == lang_enum
    ]


def _run_command(cmd: str, cwd: str, timeout: int = 300) -> tuple[str, str, int]:
    """Run a subprocess and return (stdout, stderr, returncode)."""
    try:
        proc = subprocess.run(
            cmd,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return proc.stdout, proc.stderr, proc.returncode
    except subprocess.TimeoutExpired:
        return "", "Command timed out after {timeout}s", 1
    except Exception as exc:
        return "", str(exc), 1


# ---------------------------------------------------------------------------
# TestRunner
# ---------------------------------------------------------------------------

class TestRunner:
    """Discover and run tests across multiple frameworks."""

    # ------------------------------------------------------------------
    # discover_tests
    # ------------------------------------------------------------------

    def discover_tests(
        self,
        project_path: str,
        language: str = "",
    ) -> list[str]:
        """Find test files in a project."""
        p = Path(project_path)
        if not p.exists():
            return []

        test_files: list[str] = []

        # Auto-detect frameworks
        frameworks = []
        detected_fw = _detect_framework(project_path)
        if detected_fw:
            frameworks.append(detected_fw)
        if language:
            frameworks.extend(_detect_language_frameworks(project_path, language))

        # Collect patterns from detected frameworks
        patterns: set[str] = set()
        for fw in frameworks:
            for pat in _FRAMEWORK_COMMANDS[fw]["test_patterns"]:
                patterns.add(pat)

        # Fallback generic patterns
        if not patterns:
            patterns = {
                "test_*.py", "*_test.py",
                "*.test.js", "*.test.ts", "*.spec.js", "*.spec.ts",
                "*_test.go", "*_test.rs", "*_spec.rb",
            }

        # Walk the directory and match
        for root, _dirs, files in os.walk(p):
            # Skip hidden dirs and node_modules
            rel_root = os.path.relpath(root, p)
            if any(part.startswith(".") or part == "node_modules" or part == "vendor" for part in Path(rel_root).parts):
                continue
            for fname in files:
                for pat in patterns:
                    import fnmatch
                    if fnmatch.fnmatch(fname, pat):
                        test_files.append(os.path.join(root, fname))
                        break

        return sorted(set(test_files))

    # ------------------------------------------------------------------
    # run_tests
    # ------------------------------------------------------------------

    def run_tests(
        self,
        project_path: str,
        framework: str = "",
        test_filter: str = "",
    ) -> TestResult:
        """Execute tests using the specified or auto-detected framework."""
        fw = framework.lower().strip()
        if not fw:
            fw = _detect_framework(project_path) or "pytest"

        if fw not in _FRAMEWORK_COMMANDS:
            return TestResult(
                framework=fw,
                output=f"Unsupported framework: {fw}. Supported: {', '.join(sorted(_FRAMEWORK_COMMANDS))}",
            )

        info = _FRAMEWORK_COMMANDS[fw]
        filter_part = info["filter_cmd"].format(filter=test_filter) if test_filter else ""
        cmd = info["cmd"].format(path=project_path, filter=test_filter, filter_cmd=filter_part)

        start = time.monotonic()
        stdout, stderr, rc = _run_command(cmd, project_path)
        duration = time.monotonic() - start

        combined = stdout + "\n" + stderr
        parser = _PARSERS.get(info["parse"], _parse_pytest)
        parsed = parser(combined)

        return TestResult(
            framework=fw,
            total=parsed.get("total", 0),
            passed=parsed.get("passed", 0),
            failed=parsed.get("failed", 0),
            skipped=parsed.get("skipped", 0),
            errors=parsed.get("errors", 0),
            duration=round(duration, 3),
            output=combined.strip(),
            failures=parsed.get("failures", []),
        )

    # ------------------------------------------------------------------
    # run_single_test
    # ------------------------------------------------------------------

    def run_single_test(
        self,
        test_file: str,
        test_name: str,
    ) -> TestResult:
        """Run a single test by file and test name."""
        p = Path(test_file)
        if not p.exists():
            return TestResult(output=f"Test file not found: {test_file}")

        # Detect framework from file extension
        ext = p.suffix.lower()
        fw_map = {
            ".py": "pytest",
            ".js": "jest",
            ".ts": "jest",
            ".go": "go test",
            ".rs": "cargo test",
            ".rb": "rspec",
            ".php": "phpunit",
        }
        fw = fw_map.get(ext, "pytest")

        if fw == "go test":
            cmd = f"go test -v -run {test_name} ./..."
        elif fw == "cargo test":
            cmd = f"cargo test {test_name} -- --nocapture"
        elif fw in ("jest",):
            cmd = f"npx jest --testPathPattern={test_file} -t {test_name} --verbose"
        elif fw == "rspec":
            cmd = f"bundle exec rspec {test_file}:{test_name} --format documentation"
        elif fw == "phpunit":
            cmd = f"vendor/bin/phpunit --filter={test_name} {test_file}"
        else:
            cmd = f"python -m pytest {test_file} -k {test_name} -v --tb=short"

        cwd = str(p.parent) if fw == "go test" else str(p.parent)
        start = time.monotonic()
        stdout, stderr, rc = _run_command(cmd, cwd)
        duration = time.monotonic() - start

        combined = stdout + "\n" + stderr
        info = _FRAMEWORK_COMMANDS.get(fw, _FRAMEWORK_COMMANDS["pytest"])
        parser = _PARSERS.get(info["parse"], _parse_pytest)
        parsed = parser(combined)

        return TestResult(
            framework=fw,
            total=max(parsed.get("total", 0), 1),
            passed=parsed.get("passed", 0) if rc == 0 else 0,
            failed=parsed.get("failed", 0) if rc != 0 else 0,
            skipped=parsed.get("skipped", 0),
            errors=parsed.get("errors", 0),
            duration=round(duration, 3),
            output=combined.strip(),
            failures=parsed.get("failures", []),
        )

    # ------------------------------------------------------------------
    # get_coverage
    # ------------------------------------------------------------------

    def get_coverage(self, project_path: str) -> dict[str, Any]:
        """Get code coverage information for the project."""
        fw = _detect_framework(project_path) or "pytest"
        if fw not in _FRAMEWORK_COMMANDS:
            return {"error": f"Unsupported framework: {fw}"}

        info = _FRAMEWORK_COMMANDS[fw]
        cmd = info["coverage_cmd"].format(path=project_path, filter="")

        stdout, stderr, rc = _run_command(cmd, project_path)
        combined = stdout + "\n" + stderr

        coverage: dict[str, Any] = {
            "framework": fw,
            "returncode": rc,
            "output": combined.strip(),
            "summary": {},
            "files": {},
        }

        # Try to parse JSON coverage report
        json_paths = [
            Path(project_path) / "coverage.json",
            Path(project_path) / "coverage" / "coverage-final.json",
            Path(project_path) / ".coverage.json",
        ]
        for jp in json_paths:
            if jp.exists():
                try:
                    data = json.loads(jp.read_text(encoding="utf-8"))
                    if "totals" in data:
                        coverage["summary"] = {
                            "total_statements": data["totals"].get("num_statements", 0),
                            "covered": data["totals"].get("covered_lines", 0),
                            "percent": data["totals"].get("percent_covered", 0),
                        }
                    if "files" in data:
                        coverage["files"] = {
                            k: {
                                "statements": v.get("num_statements", 0),
                                "covered": v.get("covered_lines", 0),
                                "percent": v.get("percent_covered", 0),
                            }
                            for k, v in data["files"].items()
                        }
                    break
                except (json.JSONDecodeError, KeyError):
                    continue

        # Parse go coverage from stdout
        if fw == "go test" and "total:" in combined:
            m = re.search(r"total:\s+\(statements\)\s+(\d+\.\d+)%", combined)
            if m:
                coverage["summary"] = {"percent": float(m.group(1))}

        return coverage

    # ------------------------------------------------------------------
    # generate_test_report
    # ------------------------------------------------------------------

    def generate_test_report(self, results: list[TestResult]) -> str:
        """Format test results as a readable report."""
        lines: list[str] = []
        lines.append("=" * 60)
        lines.append("TEST REPORT")
        lines.append("=" * 60)

        total_all = sum(r.total for r in results)
        passed_all = sum(r.passed for r in results)
        failed_all = sum(r.failed for r in results)
        skipped_all = sum(r.skipped for r in results)
        errors_all = sum(r.errors for r in results)
        duration_all = sum(r.duration for r in results)

        lines.append(f"Total: {total_all} | Passed: {passed_all} | Failed: {failed_all} | Skipped: {skipped_all} | Errors: {errors_all}")
        lines.append(f"Duration: {duration_all:.2f}s")
        lines.append("")

        for r in results:
            status = "PASSED" if r.failed == 0 and r.errors == 0 else "FAILED"
            lines.append(f"[{status}] {r.framework} ({r.total} tests, {r.duration:.2f}s)")

            if r.failures:
                lines.append(f"  Failures ({len(r.failures)}):")
                for f in r.failures[:10]:
                    lines.append(f"    - {f.get('test', 'unknown')}: {f.get('message', '')[:80]}")

            lines.append("")

        if failed_all == 0 and errors_all == 0:
            lines.append("ALL TESTS PASSED")
        else:
            lines.append(f"{failed_all + errors_all} test(s) FAILED")

        return "\n".join(lines)
