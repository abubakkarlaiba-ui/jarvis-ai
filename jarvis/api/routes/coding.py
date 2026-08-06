"""
Coding Agent route — autonomous coding assistant API.
=====================================================
Exposes all 15 coding capabilities via REST endpoints.
"""

from __future__ import annotations

import logging
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/coding", tags=["coding"])


# ── Request / Response models ─────────────────────────────────────


class GenerateRequest(BaseModel):
    description: str = Field(..., description="What to generate")
    language: str = Field(default="python", description="Target language")
    context: dict = Field(default_factory=dict, description="Additional context")


class ExplainRequest(BaseModel):
    code: str = Field(..., description="Code to explain")
    language: str = Field(default="python")
    detail_level: str = Field(default="full", description="minimal, normal, full")


class DebugRequest(BaseModel):
    code: str = Field(..., description="Code to debug")
    language: str = Field(default="python")
    error_message: str = Field(default="", description="Error message if available")


class RefactorRequest(BaseModel):
    code: str = Field(..., description="Code to refactor")
    language: str = Field(default="python")


class TestRequest(BaseModel):
    project_path: str = Field(default="", description="Project path (empty = cwd)")
    framework: str = Field(default="", description="Test framework to use")
    filter: str = Field(default="", description="Test filter pattern")


class AnalyzeRequest(BaseModel):
    project_path: str = Field(default="", description="Project path (empty = cwd)")


class BuildAPIRequest(BaseModel):
    name: str = Field(..., description="Project name")
    framework: str = Field(default="fastapi", description="API framework")
    models: list[dict] = Field(default_factory=list, description="Data models")
    endpoints: list[dict] = Field(default_factory=list, description="API endpoints")
    output_dir: str = Field(default="", description="Output directory")


class BuildWebsiteRequest(BaseModel):
    name: str = Field(..., description="Project name")
    framework: str = Field(default="react", description="Frontend framework")
    pages: list[str] = Field(default_factory=lambda: ["home"], description="Pages to create")
    output_dir: str = Field(default="", description="Output directory")


class BuildDesktopRequest(BaseModel):
    name: str = Field(..., description="Project name")
    framework: str = Field(default="electron", description="Desktop framework")
    features: list[str] = Field(default_factory=list, description="App features")
    output_dir: str = Field(default="", description="Output directory")


class BuildAIRequest(BaseModel):
    name: str = Field(..., description="Project name")
    project_type: str = Field(default="chatbot", description="AI project type")
    framework: str = Field(default="pytorch", description="ML framework")
    output_dir: str = Field(default="", description="Output directory")


class GitRequest(BaseModel):
    action: str = Field(..., description="Git action: status, commit, log, diff, branch, etc.")
    message: str = Field(default="", description="Commit message")
    files: list[str] | None = Field(default=None, description="Files to stage")
    branch: str = Field(default="", description="Branch name")
    count: int = Field(default=10, description="Log count")
    file: str = Field(default="", description="File for blame/diff")


class PlanRequest(BaseModel):
    name: str = Field(..., description="Project name")
    description: str = Field(..., description="Project description")
    project_type: str = Field(default="web_app", description="Project type")
    tech_preference: str = Field(default="default", description="Tech preference")
    features: list[str] | None = Field(default=None, description="Features to include")


class CodingResponse(BaseModel):
    success: bool
    output: dict | str | list | None = None
    code: str = ""
    explanation: str = ""
    issues: list[dict] = Field(default_factory=list)
    error: str = ""
    metadata: dict = Field(default_factory=dict)


# ── Dependency helper ─────────────────────────────────────────────


def _get_agent():
    from jarvis.api.app import get_jarvis_core
    core = get_jarvis_core()
    if not hasattr(core, "coding_agent"):
        raise HTTPException(status_code=503, detail="Coding agent not initialized")
    return core.coding_agent


def _result_to_response(result) -> CodingResponse:
    output = result.output
    if hasattr(output, "__dict__"):
        output = vars(output)
    elif hasattr(output, "__iter__") and not isinstance(output, (str, dict, list)):
        output = list(output)

    issues = []
    for issue in (result.issues or []):
        if hasattr(issue, "__dict__"):
            issues.append(vars(issue))
        else:
            issues.append(issue)

    return CodingResponse(
        success=result.success,
        output=output,
        code=result.code,
        explanation=result.explanation,
        issues=issues,
        error=result.error,
        metadata=result.metadata,
    )


# ── Endpoints ─────────────────────────────────────────────────────


@router.post("/generate", response_model=CodingResponse)
async def generate_code(request: GenerateRequest) -> CodingResponse:
    """Generate code from a natural language description."""
    from jarvis.core.coding.base import CodeLanguage
    agent = _get_agent()
    lang = CodeLanguage(request.language.lower()) if request.language.lower() in [e.value for e in CodeLanguage] else CodeLanguage.PYTHON
    result = await agent.generate_code(request.description, lang, **request.context)
    return _result_to_response(result)


@router.post("/explain", response_model=CodingResponse)
async def explain_code(request: ExplainRequest) -> CodingResponse:
    """Explain what a piece of code does."""
    from jarvis.core.coding.base import CodeLanguage
    agent = _get_agent()
    lang = CodeLanguage(request.language.lower()) if request.language.lower() in [e.value for e in CodeLanguage] else CodeLanguage.PYTHON
    result = await agent.explain_code(request.code, lang)
    return _result_to_response(result)


@router.post("/debug", response_model=CodingResponse)
async def debug_code(request: DebugRequest) -> CodingResponse:
    """Debug code and suggest fixes."""
    from jarvis.core.coding.base import CodeLanguage
    agent = _get_agent()
    lang = CodeLanguage(request.language.lower()) if request.language.lower() in [e.value for e in CodeLanguage] else CodeLanguage.PYTHON
    result = await agent.debug_code(request.code, lang, request.error_message)
    return _result_to_response(result)


@router.post("/refactor", response_model=CodingResponse)
async def refactor_code(request: RefactorRequest) -> CodingResponse:
    """Analyze code and suggest refactoring improvements."""
    from jarvis.core.coding.base import CodeLanguage
    agent = _get_agent()
    lang = CodeLanguage(request.language.lower()) if request.language.lower() in [e.value for e in CodeLanguage] else CodeLanguage.PYTHON
    result = await agent.refactor_code(request.code, lang)
    return _result_to_response(result)


@router.post("/test", response_model=CodingResponse)
async def run_tests(request: TestRequest) -> CodingResponse:
    """Discover and run tests in a project."""
    agent = _get_agent()
    result = await agent.run_tests(request.project_path, request.framework)
    return _result_to_response(result)


@router.post("/analyze", response_model=CodingResponse)
async def analyze_project(request: AnalyzeRequest) -> CodingResponse:
    """Analyze a project's structure, quality, and dependencies."""
    agent = _get_agent()
    result = await agent.analyze_project(request.project_path)
    return _result_to_response(result)


@router.post("/detect-bugs", response_model=CodingResponse)
async def detect_bugs(request: AnalyzeRequest) -> CodingResponse:
    """Scan a project for bugs and code smells."""
    agent = _get_agent()
    result = await agent.detect_bugs(request.project_path)
    return _result_to_response(result)


@router.post("/generate-docs", response_model=CodingResponse)
async def generate_docs(request: AnalyzeRequest) -> CodingResponse:
    """Generate documentation for a project."""
    agent = _get_agent()
    result = await agent.handle_task(
        __import__("jarvis.core.coding.base", fromlist=["CodingTask"]).CodingTask(
            task_type=__import__("jarvis.core.coding.base", fromlist=["TaskType"]).TaskType.GENERATE_DOCS,
            parameters={"project_path": request.project_path or "", "doc_type": "readme"},
        )
    )
    return _result_to_response(result)


@router.post("/build-api", response_model=CodingResponse)
async def build_api(request: BuildAPIRequest) -> CodingResponse:
    """Scaffold a new REST or GraphQL API project."""
    agent = _get_agent()
    result = await agent.handle_task(
        __import__("jarvis.core.coding.base", fromlist=["CodingTask"]).CodingTask(
            task_type=__import__("jarvis.core.coding.base", fromlist=["TaskType"]).TaskType.BUILD_API,
            parameters={
                "name": request.name,
                "framework": request.framework,
                "models": request.models,
                "endpoints": request.endpoints,
                "output_dir": request.output_dir,
            },
        )
    )
    return _result_to_response(result)


@router.post("/build-website", response_model=CodingResponse)
async def build_website(request: BuildWebsiteRequest) -> CodingResponse:
    """Scaffold a new frontend website project."""
    agent = _get_agent()
    result = await agent.handle_task(
        __import__("jarvis.core.coding.base", fromlist=["CodingTask"]).CodingTask(
            task_type=__import__("jarvis.core.coding.base", fromlist=["TaskType"]).TaskType.BUILD_WEBSITE,
            parameters={
                "name": request.name,
                "framework": request.framework,
                "pages": request.pages,
                "output_dir": request.output_dir,
            },
        )
    )
    return _result_to_response(result)


@router.post("/build-desktop", response_model=CodingResponse)
async def build_desktop(request: BuildDesktopRequest) -> CodingResponse:
    """Scaffold a new desktop application project."""
    agent = _get_agent()
    result = await agent.handle_task(
        __import__("jarvis.core.coding.base", fromlist=["CodingTask"]).CodingTask(
            task_type=__import__("jarvis.core.coding.base", fromlist=["TaskType"]).TaskType.BUILD_DESKTOP,
            parameters={
                "name": request.name,
                "framework": request.framework,
                "features": request.features,
                "output_dir": request.output_dir,
            },
        )
    )
    return _result_to_response(result)


@router.post("/build-ai", response_model=CodingResponse)
async def build_ai(request: BuildAIRequest) -> CodingResponse:
    """Scaffold a new AI/ML project."""
    agent = _get_agent()
    result = await agent.handle_task(
        __import__("jarvis.core.coding.base", fromlist=["CodingTask"]).CodingTask(
            task_type=__import__("jarvis.core.coding.base", fromlist=["TaskType"]).TaskType.BUILD_AI,
            parameters={
                "name": request.name,
                "project_type": request.project_type,
                "framework": request.framework,
                "output_dir": request.output_dir,
            },
        )
    )
    return _result_to_response(result)


@router.post("/git", response_model=CodingResponse)
async def git_operations(request: GitRequest) -> CodingResponse:
    """Perform git operations (status, commit, log, diff, branch, etc.)."""
    agent = _get_agent()
    params = {"action": request.action}
    if request.message:
        params["message"] = request.message
    if request.files:
        params["files"] = request.files
    if request.branch:
        params["branch"] = request.branch
    if request.count:
        params["count"] = request.count
    if request.file:
        params["file"] = request.file
    result = await agent.handle_task(
        __import__("jarvis.core.coding.base", fromlist=["CodingTask"]).CodingTask(
            task_type=__import__("jarvis.core.coding.base", fromlist=["TaskType"]).TaskType.GIT,
            parameters=params,
        )
    )
    return _result_to_response(result)


@router.post("/plan", response_model=CodingResponse)
async def plan_project(request: PlanRequest) -> CodingResponse:
    """Generate a project plan with tech stack, phases, and file structure."""
    agent = _get_agent()
    result = await agent.plan_project(
        name=request.name,
        description=request.description,
        project_type=request.project_type,
        tech_preference=request.tech_preference,
        features=request.features,
    )
    return _result_to_response(result)


@router.get("/languages")
async def list_languages() -> list[dict]:
    """List all supported programming languages."""
    from jarvis.core.coding.base import CodeLanguage
    return [{"name": lang.name, "value": lang.value} for lang in CodeLanguage]


@router.get("/templates")
async def list_templates() -> dict[str, list[str]]:
    """List all available project templates."""
    from jarvis.core.coding.project_planner import ProjectPlanner
    planner = ProjectPlanner()
    return {
        template_name: list(template["tech_stacks"].keys())
        for template_name, template in planner.TEMPLATES.items()
    }
