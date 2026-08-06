"""
Coding Agent — autonomous coding assistant orchestrator.
========================================================
Coordinates all coding submodules to handle any development task.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from jarvis.core.coding.base import (
    CodeAnalysis,
    CodeLanguage,
    CodeIssue,
    CodingResult,
    CodingTask,
    GitStatus,
    Severity,
    TaskType,
    TestResult,
)
from jarvis.core.coding.bug_detector import BugDetector
from jarvis.core.coding.code_explainer import CodeExplainer
from jarvis.core.coding.code_generator import CodeGenerator
from jarvis.core.coding.debugger import Debugger
from jarvis.core.coding.doc_generator import DocGenerator
from jarvis.core.coding.git_ops import GitOps
from jarvis.core.coding.project_analyzer import ProjectAnalyzer
from jarvis.core.coding.project_planner import ProjectPlanner
from jarvis.core.coding.refactoring import CodeRefactorer
from jarvis.core.coding.test_runner import TestRunner

logger = logging.getLogger(__name__)


class CodingAgent:
    """Autonomous coding assistant that coordinates all coding submodules.

    Routes tasks to the appropriate sub-agent and combines results
    for complex multi-step operations.
    """

    def __init__(self, working_directory: str = "."):
        self.working_dir = Path(working_directory)
        self.generator = CodeGenerator()
        self.explainer = CodeExplainer()
        self.debugger = Debugger()
        self.refactorer = CodeRefactorer()
        self.test_runner = TestRunner()
        self.analyzer = ProjectAnalyzer()
        self.bug_detector = BugDetector()
        self.doc_generator = DocGenerator()
        self.git = GitOps(str(self.working_dir))
        self.planner = ProjectPlanner()

    async def handle_task(self, task: CodingTask) -> CodingResult:
        """Route a coding task to the appropriate sub-agent.

        Args:
            task: The coding task to process.

        Returns:
            CodingResult with the operation output.
        """
        handlers = {
            TaskType.GENERATE: self._handle_generate,
            TaskType.EXPLAIN: self._handle_explain,
            TaskType.DEBUG: self._handle_debug,
            TaskType.REFACTOR: self._handle_refactor,
            TaskType.TEST: self._handle_test,
            TaskType.ANALYZE: self._handle_analyze,
            TaskType.DETECT_BUGS: self._handle_detect_bugs,
            TaskType.GENERATE_DOCS: self._handle_generate_docs,
            TaskType.BUILD_API: self._handle_build_api,
            TaskType.BUILD_WEBSITE: self._handle_build_website,
            TaskType.BUILD_DESKTOP: self._handle_build_desktop,
            TaskType.BUILD_AI: self._handle_build_ai,
            TaskType.GIT: self._handle_git,
            TaskType.PLAN: self._handle_plan,
        }

        handler = handlers.get(task.task_type)
        if handler is None:
            return CodingResult(
                success=False,
                error=f"Unknown task type: {task.task_type}",
            )

        try:
            return await handler(task)
        except Exception as e:
            logger.error("Task failed: %s", e, exc_info=True)
            return CodingResult(success=False, error=str(e))

    # ── Individual handlers ───────────────────────────────────────

    async def _handle_generate(self, task: CodingTask) -> CodingResult:
        return self.generator.generate(
            description=task.description,
            language=task.language,
            context=task.context,
        )

    async def _handle_explain(self, task: CodingTask) -> CodingResult:
        return self.explainer.explain(
            code=task.input_code,
            language=task.language,
            detail_level=task.parameters.get("detail_level", "full"),
        )

    async def _handle_debug(self, task: CodingTask) -> CodingResult:
        return self.debugger.debug(
            code=task.input_code,
            language=task.language,
            error_message=task.parameters.get("error_message", ""),
        )

    async def _handle_refactor(self, task: CodingTask) -> CodingResult:
        return self.refactorer.analyze(
            code=task.input_code,
            language=task.language,
        )

    async def _handle_test(self, task: CodingTask) -> CodingResult:
        project_path = task.parameters.get("project_path", str(self.working_dir))
        results = self.test_runner.run_tests(
            project_path=project_path,
            framework=task.parameters.get("framework", ""),
            test_filter=task.parameters.get("filter", ""),
        )
        return CodingResult(
            success=True,
            task_type=TaskType.TEST,
            output=results,
            explanation=self.test_runner.generate_test_report([results]),
        )

    async def _handle_analyze(self, task: CodingTask) -> CodingResult:
        project_path = task.parameters.get("project_path", str(self.working_dir))
        return self.analyzer.analyze_project(project_path)

    async def _handle_detect_bugs(self, task: CodingTask) -> CodingResult:
        project_path = task.parameters.get("project_path", str(self.working_dir))
        issues = self.bug_detector.scan_project(project_path)
        summary = self.bug_detector.severity_summary(issues)
        return CodingResult(
            success=True,
            task_type=TaskType.DETECT_BUGS,
            output=issues,
            issues=issues,
            explanation=f"Found {len(issues)} issues: {summary}",
        )

    async def _handle_generate_docs(self, task: CodingTask) -> CodingResult:
        project_path = task.parameters.get("project_path", str(self.working_dir))
        doc_type = task.parameters.get("doc_type", "readme")

        if doc_type == "readme":
            output = self.doc_generator.generate_readme(project_path)
        elif doc_type == "changelog":
            output = self.doc_generator.generate_changelog(project_path)
        elif doc_type == "contributing":
            output = self.doc_generator.generate_contribution_guide(project_path)
        elif doc_type == "architecture":
            output = self.doc_generator.generate_architecture_doc(project_path)
        elif doc_type == "api":
            output = self.doc_generator.generate_api_docs(
                task.input_code, task.language
            )
        elif doc_type == "docstring":
            output = self.doc_generator.generate_docstring(
                task.input_code,
                task.language,
                style=task.parameters.get("style", "google"),
            )
        else:
            output = self.doc_generator.generate_readme(project_path)

        return CodingResult(
            success=True,
            task_type=TaskType.GENERATE_DOCS,
            output=output,
        )

    async def _handle_build_api(self, task: CodingTask) -> CodingResult:
        from jarvis.core.coding.api_builder import APIBuilder
        builder = APIBuilder()

        name = task.parameters.get("name", "my_api")
        framework = task.parameters.get("framework", "fastapi")
        output_dir = task.parameters.get("output_dir", str(self.working_dir / name))

        result = builder.build_rest_api(
            name=name,
            framework=framework,
            models=task.parameters.get("models", []),
            endpoints=task.parameters.get("endpoints", []),
            output_dir=output_dir,
        )

        return CodingResult(
            success=True,
            task_type=TaskType.BUILD_API,
            output=result,
            explanation=f"API project '{name}' created with {framework} in {output_dir}",
        )

    async def _handle_build_website(self, task: CodingTask) -> CodingResult:
        from jarvis.core.coding.website_builder import WebsiteBuilder
        builder = WebsiteBuilder()

        name = task.parameters.get("name", "my_website")
        framework = task.parameters.get("framework", "react")
        output_dir = task.parameters.get("output_dir", str(self.working_dir / name))

        result = builder.build_frontend(
            name=name,
            framework=framework,
            pages=task.parameters.get("pages", ["home"]),
            output_dir=output_dir,
        )

        return CodingResult(
            success=True,
            task_type=TaskType.BUILD_WEBSITE,
            output=result,
            explanation=f"Website '{name}' created with {framework} in {output_dir}",
        )

    async def _handle_build_desktop(self, task: CodingTask) -> CodingResult:
        from jarvis.core.coding.desktop_app_builder import DesktopAppBuilder
        builder = DesktopAppBuilder()

        name = task.parameters.get("name", "my_app")
        framework = task.parameters.get("framework", "electron")
        output_dir = task.parameters.get("output_dir", str(self.working_dir / name))

        result = builder.build_app(
            name=name,
            framework=framework,
            features=task.parameters.get("features", []),
            output_dir=output_dir,
        )

        return CodingResult(
            success=True,
            task_type=TaskType.BUILD_DESKTOP,
            output=result,
            explanation=f"Desktop app '{name}' created with {framework} in {output_dir}",
        )

    async def _handle_build_ai(self, task: CodingTask) -> CodingResult:
        from jarvis.core.coding.ai_project_builder import AIProjectBuilder
        builder = AIProjectBuilder()

        name = task.parameters.get("name", "my_ai_project")
        project_type = task.parameters.get("project_type", "chatbot")
        framework = task.parameters.get("framework", "pytorch")
        output_dir = task.parameters.get("output_dir", str(self.working_dir / name))

        result = builder.build_project(
            name=name,
            project_type=project_type,
            framework=framework,
            output_dir=output_dir,
        )

        return CodingResult(
            success=True,
            task_type=TaskType.BUILD_AI,
            output=result,
            explanation=f"AI project '{name}' ({project_type}) created with {framework} in {output_dir}",
        )

    async def _handle_git(self, task: CodingTask) -> CodingResult:
        action = task.parameters.get("action", "status")

        git_ops = GitOps(str(self.working_dir))

        if action == "status":
            output = git_ops.status()
        elif action == "commit":
            message = task.parameters.get("message", "")
            files = task.parameters.get("files")
            if not message:
                diff = git_ops.diff()
                message = git_ops.generate_commit_message(diff)
            output = git_ops.commit(message, files)
        elif action == "log":
            count = task.parameters.get("count", 10)
            output = git_ops.log(count)
        elif action == "diff":
            file_path = task.parameters.get("file")
            output = git_ops.diff(file_path)
        elif action == "branch":
            name = task.parameters.get("name")
            output = git_ops.branch(name)
        elif action == "switch":
            branch = task.parameters.get("branch", "main")
            output = git_ops.switch(branch)
        elif action == "merge":
            branch = task.parameters.get("branch", "")
            output = git_ops.merge(branch)
        elif action == "blame":
            file_path = task.parameters.get("file", "")
            output = git_ops.blame(file_path)
        elif action == "init":
            output = git_ops.init()
        elif action == "add":
            files = task.parameters.get("files", ".")
            output = git_ops.add(files)
        elif action == "stash":
            message = task.parameters.get("message", "")
            output = git_ops.stash(message)
        elif action == "stash_pop":
            output = git_ops.stash_pop()
        elif action == "push":
            branch = task.parameters.get("branch", "")
            output = git_ops.push(branch)
        elif action == "pull":
            output = git_ops.pull()
        elif action == "tag":
            name = task.parameters.get("tag_name", "")
            message = task.parameters.get("message", "")
            output = git_ops.create_tag(name, message)
        elif action == "remote":
            url = task.parameters.get("url")
            output = git_ops.remote(url)
        else:
            output = {"error": f"Unknown git action: {action}"}

        return CodingResult(
            success=True,
            task_type=TaskType.GIT,
            output=output,
        )

    async def _handle_plan(self, task: CodingTask) -> CodingResult:
        return self.planner.plan_project(
            name=task.parameters.get("name", "my_project"),
            description=task.description,
            project_type=task.parameters.get("project_type", "web_app"),
            tech_preference=task.parameters.get("tech_preference", "default"),
            features=task.parameters.get("features"),
        )

    # ── Convenience methods ───────────────────────────────────────

    async def generate_code(
        self, description: str, language: CodeLanguage = CodeLanguage.PYTHON, **kwargs
    ) -> CodingResult:
        task = CodingTask(
            task_type=TaskType.GENERATE,
            language=language,
            description=description,
            parameters=kwargs,
        )
        return await self.handle_task(task)

    async def explain_code(self, code: str, language: CodeLanguage = CodeLanguage.PYTHON) -> CodingResult:
        task = CodingTask(
            task_type=TaskType.EXPLAIN,
            language=language,
            input_code=code,
        )
        return await self.handle_task(task)

    async def debug_code(
        self, code: str, language: CodeLanguage = CodeLanguage.PYTHON, error: str = ""
    ) -> CodingResult:
        task = CodingTask(
            task_type=TaskType.DEBUG,
            language=language,
            input_code=code,
            parameters={"error_message": error},
        )
        return await self.handle_task(task)

    async def refactor_code(self, code: str, language: CodeLanguage = CodeLanguage.PYTHON) -> CodingResult:
        task = CodingTask(
            task_type=TaskType.REFACTOR,
            language=language,
            input_code=code,
        )
        return await self.handle_task(task)

    async def run_tests(self, project_path: str = "", framework: str = "") -> CodingResult:
        task = CodingTask(
            task_type=TaskType.TEST,
            parameters={"project_path": project_path or str(self.working_dir), "framework": framework},
        )
        return await self.handle_task(task)

    async def analyze_project(self, project_path: str = "") -> CodingResult:
        task = CodingTask(
            task_type=TaskType.ANALYZE,
            parameters={"project_path": project_path or str(self.working_dir)},
        )
        return await self.handle_task(task)

    async def detect_bugs(self, project_path: str = "") -> CodingResult:
        task = CodingTask(
            task_type=TaskType.DETECT_BUGS,
            parameters={"project_path": project_path or str(self.working_dir)},
        )
        return await self.handle_task(task)

    async def git_status(self) -> CodingResult:
        task = CodingTask(task_type=TaskType.GIT, parameters={"action": "status"})
        return await self.handle_task(task)

    async def git_commit(self, message: str = "", files: list[str] | None = None) -> CodingResult:
        params: dict[str, Any] = {"action": "commit"}
        if message:
            params["message"] = message
        if files:
            params["files"] = files
        task = CodingTask(task_type=TaskType.GIT, parameters=params)
        return await self.handle_task(task)

    async def plan_project(
        self, name: str, description: str, project_type: str = "web_app", **kwargs
    ) -> CodingResult:
        task = CodingTask(
            task_type=TaskType.PLAN,
            description=description,
            parameters={"name": name, "project_type": project_type, **kwargs},
        )
        return await self.handle_task(task)
