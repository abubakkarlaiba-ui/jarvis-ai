"""
JARVIS Coding module.
=====================
Autonomous coding assistant with 15 capabilities.

Quick Start:
    from jarvis.core.coding import CodingAgent, CodingTask, TaskType

    agent = CodingAgent()
    result = await agent.generate_code("A FastAPI server with /users endpoint")
    result = await agent.explain_code(code)
    result = await agent.debug_code(code, error="TypeError: ...")
"""

from jarvis.core.coding.base import (
    CodeAnalysis,
    CodeLanguage,
    CodeIssue,
    CodingResult,
    CodingTask,
    GitStatus,
    ProjectPlan,
    Severity,
    TaskType,
    TestResult,
)
from jarvis.core.coding.bug_detector import BugDetector
from jarvis.core.coding.code_explainer import CodeExplainer
from jarvis.core.coding.code_generator import CodeGenerator
from jarvis.core.coding.coding_agent import CodingAgent
from jarvis.core.coding.debugger import Debugger
from jarvis.core.coding.doc_generator import DocGenerator
from jarvis.core.coding.git_ops import GitOps
from jarvis.core.coding.project_analyzer import ProjectAnalyzer
from jarvis.core.coding.project_planner import ProjectPlanner
from jarvis.core.coding.refactoring import CodeRefactorer
from jarvis.core.coding.test_runner import TestRunner

__all__ = [
    "CodeAnalysis",
    "CodeLanguage",
    "CodeIssue",
    "CodingResult",
    "CodingTask",
    "GitStatus",
    "ProjectPlan",
    "Severity",
    "TaskType",
    "TestResult",
    "BugDetector",
    "CodeExplainer",
    "CodeGenerator",
    "CodingAgent",
    "Debugger",
    "DocGenerator",
    "GitOps",
    "ProjectAnalyzer",
    "ProjectPlanner",
    "CodeRefactorer",
    "TestRunner",
]
