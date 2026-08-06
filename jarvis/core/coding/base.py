"""
Coding Agent — base types and configuration.
=============================================
Shared dataclasses, enums, and settings for all coding submodules.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any


class CodeLanguage(Enum):
    """Supported programming languages."""
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    JAVA = "java"
    GO = "go"
    RUST = "rust"
    CPP = "cpp"
    C = "c"
    CSHARP = "csharp"
    RUBY = "ruby"
    PHP = "php"
    SWIFT = "swift"
    KOTLIN = "kotlin"
    SQL = "sql"
    HTML = "html"
    CSS = "css"
    BASH = "bash"
    POWERSHELL = "powershell"
    YAML = "yaml"
    JSON = "json"
    MARKDOWN = "markdown"

    @classmethod
    def from_ext(cls, ext: str) -> CodeLanguage:
        ext = ext.lstrip(".").lower()
        mapping = {
            "py": cls.PYTHON, "js": cls.JAVASCRIPT, "ts": cls.TYPESCRIPT,
            "java": cls.JAVA, "go": cls.GO, "rs": cls.RUST,
            "cpp": cls.CPP, "cc": cls.CPP, "cxx": cls.CPP, "c": cls.C,
            "cs": cls.CSHARP, "rb": cls.RUBY, "php": cls.PHP,
            "swift": cls.SWIFT, "kt": cls.KOTLIN, "sql": cls.SQL,
            "html": cls.HTML, "css": cls.CSS, "sh": cls.BASH,
            "bash": cls.BASH, "ps1": cls.POWERSHELL, "yml": cls.YAML,
            "yaml": cls.YAML, "json": cls.JSON, "md": cls.MARKDOWN,
        }
        return mapping.get(ext, cls.PYTHON)


class Severity(Enum):
    """Issue severity levels."""
    INFO = auto()
    LOW = auto()
    MEDIUM = auto()
    HIGH = auto()
    CRITICAL = auto()


class TaskType(Enum):
    """Types of coding tasks the agent can perform."""
    GENERATE = "generate"
    EXPLAIN = "explain"
    DEBUG = "debug"
    REFACTOR = "refactor"
    TEST = "test"
    ANALYZE = "analyze"
    DETECT_BUGS = "detect_bugs"
    GENERATE_DOCS = "generate_docs"
    BUILD_API = "build_api"
    BUILD_WEBSITE = "build_website"
    BUILD_DESKTOP = "build_desktop"
    BUILD_AI = "build_ai"
    GIT = "git"
    PLAN = "plan"


@dataclass
class CodeIssue:
    """A single detected issue in code."""
    file: str
    line: int
    column: int = 0
    severity: Severity = Severity.MEDIUM
    code: str = ""
    message: str = ""
    suggestion: str = ""
    fix_available: bool = False
    fix_code: str = ""


@dataclass
class CodeAnalysis:
    """Result of analyzing a codebase or file."""
    language: CodeLanguage = CodeLanguage.PYTHON
    files_analyzed: int = 0
    total_lines: int = 0
    functions: int = 0
    classes: int = 0
    imports: int = 0
    comments: int = 0
    blank_lines: int = 0
    complexity: float = 0.0
    maintainability: float = 100.0
    issues: list[CodeIssue] = field(default_factory=list)
    summary: str = ""


@dataclass
class TestResult:
    """Result of running a test suite."""
    framework: str = ""
    total: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    errors: int = 0
    duration: float = 0.0
    output: str = ""
    failures: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class GitStatus:
    """Git repository status."""
    branch: str = ""
    ahead: int = 0
    behind: int = 0
    staged: list[str] = field(default_factory=list)
    modified: list[str] = field(default_factory=list)
    untracked: list[str] = field(default_factory=list)
    clean: bool = True


@dataclass
class ProjectPlan:
    """A project planning document."""
    name: str = ""
    description: str = ""
    tech_stack: list[str] = field(default_factory=list)
    phases: list[dict[str, Any]] = field(default_factory=list)
    files: list[dict[str, Any]] = field(default_factory=list)
    estimated_effort: str = ""
    dependencies: list[str] = field(default_factory=list)


@dataclass
class CodingTask:
    """A coding task to be processed by the agent."""
    task_type: TaskType = TaskType.GENERATE
    language: CodeLanguage = CodeLanguage.PYTHON
    input_code: str = ""
    description: str = ""
    file_path: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)
    context: dict[str, Any] = field(default_factory=dict)


@dataclass
class CodingResult:
    """Unified result from any coding agent operation."""
    success: bool = True
    task_type: TaskType = TaskType.GENERATE
    output: Any = None
    code: str = ""
    explanation: str = ""
    issues: list[CodeIssue] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    error: str = ""
