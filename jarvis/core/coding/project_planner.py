"""
Project Planner — generate project plans and scaffolding.
=========================================================
Creates detailed project plans with file structures, tech stacks, and phased roadmaps.
"""

from __future__ import annotations

import logging
from typing import Any

from jarvis.core.coding.base import (
    CodeLanguage,
    CodingResult,
    ProjectPlan,
    TaskType,
)

logger = logging.getLogger(__name__)


class ProjectPlanner:
    """Generate comprehensive project plans from descriptions.

    Produces project plans with tech stack recommendations, file structures,
    implementation phases, and dependency lists.
    """

    TEMPLATES: dict[str, dict[str, Any]] = {
        "web_app": {
            "description": "Full-stack web application",
            "tech_stacks": {
                "default": ["Python", "FastAPI", "PostgreSQL", "React"],
                "simple": ["Python", "Flask", "SQLite", "HTML/CSS/JS"],
                "modern": ["TypeScript", "Next.js", "Prisma", "PostgreSQL"],
                "enterprise": ["Java", "Spring Boot", "React", "PostgreSQL"],
            },
            "phases": [
                {"name": "Setup", "tasks": ["Initialize project", "Set up database", "Configure CI/CD"]},
                {"name": "Backend", "tasks": ["Create models", "Build API endpoints", "Add authentication"]},
                {"name": "Frontend", "tasks": ["Create components", "Build pages", "Connect to API"]},
                {"name": "Testing", "tasks": ["Write unit tests", "Integration tests", "E2E tests"]},
                {"name": "Deploy", "tasks": ["Docker setup", "Deploy to cloud", "Monitor"]},
            ],
        },
        "cli_tool": {
            "description": "Command-line interface tool",
            "tech_stacks": {
                "default": ["Python", "Click", "Rich"],
                "rust": ["Rust", "Clap", "indicatif"],
                "go": ["Go", "Cobra", "Bubble Tea"],
            },
            "phases": [
                {"name": "Setup", "tasks": ["Initialize project", "Set up argument parsing"]},
                {"name": "Core", "tasks": ["Implement main logic", "Add error handling"]},
                {"name": "Interface", "tasks": ["Add CLI commands", "Format output", "Add progress bars"]},
                {"name": "Polish", "tasks": ["Add tests", "Write docs", "Add tab completion"]},
            ],
        },
        "mobile_app": {
            "description": "Mobile application",
            "tech_stacks": {
                "default": ["React Native", "TypeScript", "Expo"],
                "flutter": ["Dart", "Flutter", "Firebase"],
                "native_ios": ["Swift", "SwiftUI", "CoreData"],
                "native_android": ["Kotlin", "Jetpack Compose", "Room"],
            },
            "phases": [
                {"name": "Setup", "tasks": ["Initialize project", "Configure navigation"]},
                {"name": "Core", "tasks": ["Build screens", "Create components", "Add state management"]},
                {"name": "Features", "tasks": ["Implement features", "Add offline support"]},
                {"name": "Polish", "tasks": ["Add tests", "Optimize performance", "App store prep"]},
            ],
        },
        "ai_project": {
            "description": "AI/ML project",
            "tech_stacks": {
                "default": ["Python", "PyTorch", "FastAPI"],
                "tensorflow": ["Python", "TensorFlow", "Keras"],
                "nlp": ["Python", "Hugging Face", "spaCy"],
                "cv": ["Python", "PyTorch", "OpenCV"],
            },
            "phases": [
                {"name": "Data", "tasks": ["Collect data", "Clean data", "Create datasets"]},
                {"name": "Model", "tasks": ["Design architecture", "Implement model", "Set up training"]},
                {"name": "Train", "tasks": ["Train model", "Tune hyperparameters", "Evaluate"]},
                {"name": "Deploy", "tasks": ["Create API", "Docker setup", "Monitor model"]},
            ],
        },
        "desktop_app": {
            "description": "Desktop application",
            "tech_stacks": {
                "default": ["Python", "PyQt6", "SQLite"],
                "electron": ["TypeScript", "Electron", "React"],
                "tauri": ["Rust", "Tauri", "React"],
            },
            "phases": [
                {"name": "Setup", "tasks": ["Initialize project", "Set up build system"]},
                {"name": "Core", "tasks": ["Build main window", "Implement core features"]},
                {"name": "UI", "tasks": ["Create dialogs", "Add menus", "Style interface"]},
                {"name": "Package", "tasks": ["Create installers", "Sign app", "Test distribution"]},
            ],
        },
        "library": {
            "description": "Reusable library/package",
            "tech_stacks": {
                "python": ["Python", "setuptools", "pytest"],
                "javascript": ["TypeScript", "Rollup", "Vitest"],
                "rust": ["Rust", "Cargo"],
                "go": ["Go", "Go modules"],
            },
            "phases": [
                {"name": "Setup", "tasks": ["Initialize package", "Set up build"]},
                {"name": "Implement", "tasks": ["Implement core API", "Add type hints"]},
                {"name": "Test", "tasks": ["Write tests", "Add coverage"]},
                {"name": "Publish", "tasks": ["Write docs", "Set up CI/CD", "Publish to registry"]},
            ],
        },
        "microservice": {
            "description": "Microservice with API",
            "tech_stacks": {
                "default": ["Python", "FastAPI", "Docker", "Redis"],
                "go": ["Go", "Gin", "Docker", "Redis"],
                "java": ["Java", "Spring Boot", "Docker", "Redis"],
            },
            "phases": [
                {"name": "Setup", "tasks": ["Initialize project", "Set up Docker", "Configure logging"]},
                {"name": "API", "tasks": ["Create endpoints", "Add validation", "Add error handling"]},
                {"name": "Data", "tasks": ["Set up database", "Create migrations", "Add caching"]},
                {"name": "Ops", "tasks": ["Add health checks", "Set up monitoring", "Deploy to K8s"]},
            ],
        },
    }

    def plan_project(
        self,
        name: str,
        description: str,
        project_type: str = "web_app",
        tech_preference: str = "default",
        features: list[str] | None = None,
    ) -> CodingResult:
        """Generate a complete project plan.

        Args:
            name: Project name.
            description: Project description.
            project_type: Type of project (web_app, cli_tool, mobile_app, ai_project, etc.)
            tech_preference: Tech stack variant (default, simple, modern, etc.)
            features: List of specific features to include.

        Returns:
            CodingResult with the project plan.
        """
        template = self.TEMPLATES.get(project_type, self.TEMPLATES["web_app"])

        tech_stacks = template["tech_stacks"]
        tech_stack = tech_stacks.get(tech_preference, tech_stacks.get("default", []))

        files = self._generate_file_structure(name, project_type, tech_stack)

        plan = ProjectPlan(
            name=name,
            description=description,
            tech_stack=tech_stack,
            phases=template["phases"],
            files=files,
            estimated_effort=self._estimate_effort(project_type, features),
            dependencies=self._get_dependencies(tech_stack),
        )

        return CodingResult(
            success=True,
            task_type=TaskType.PLAN,
            output=plan,
            explanation=self._format_plan(plan),
            metadata={"project_type": project_type, "features": features or []},
        )

    def _generate_file_structure(
        self, name: str, project_type: str, tech_stack: list[str]
    ) -> list[dict[str, str]]:
        """Generate a file structure for the project."""
        files: list[dict[str, str]] = []

        # Common files
        files.append({"path": "README.md", "description": "Project documentation"})
        files.append({"path": ".gitignore", "description": "Git ignore rules"})

        if "Python" in tech_stack:
            files.extend([
                {"path": f"{name}/__init__.py", "description": "Package init"},
                {"path": f"{name}/main.py", "description": "Entry point"},
                {"path": f"{name}/config.py", "description": "Configuration"},
                {"path": "requirements.txt", "description": "Dependencies"},
                {"path": "tests/__init__.py", "description": "Test package init"},
                {"path": "tests/test_main.py", "description": "Main tests"},
            ])
            if "FastAPI" in tech_stack or "Flask" in tech_stack:
                files.extend([
                    {"path": f"{name}/api/__init__.py", "description": "API package"},
                    {"path": f"{name}/api/routes.py", "description": "API routes"},
                    {"path": f"{name}/models.py", "description": "Data models"},
                    {"path": f"{name}/schemas.py", "description": "Request/response schemas"},
                ])
            if "PyTorch" in tech_stack or "TensorFlow" in tech_stack:
                files.extend([
                    {"path": f"{name}/model.py", "description": "Model definition"},
                    {"path": f"{name}/train.py", "description": "Training script"},
                    {"path": f"{name}/data.py", "description": "Data loading"},
                    {"path": f"{name}/evaluate.py", "description": "Evaluation script"},
                ])
        elif "TypeScript" in tech_stack or "JavaScript" in tech_stack:
            files.extend([
                {"path": "package.json", "description": "Node.js package config"},
                {"path": "tsconfig.json", "description": "TypeScript config"},
                {"path": f"src/index.ts", "description": "Entry point"},
                {"path": "src/types.ts", "description": "Type definitions"},
            ])
            if "React" in tech_stack or "Next.js" in tech_stack:
                files.extend([
                    {"path": "src/App.tsx", "description": "Root component"},
                    {"path": "src/pages/index.tsx", "description": "Home page"},
                    {"path": "src/components/", "description": "UI components directory"},
                ])
        elif "Rust" in tech_stack:
            files.extend([
                {"path": "Cargo.toml", "description": "Rust package config"},
                {"path": "src/main.rs", "description": "Entry point"},
                {"path": "src/lib.rs", "description": "Library root"},
                {"path": "tests/integration_test.rs", "description": "Integration tests"},
            ])
        elif "Go" in tech_stack:
            files.extend([
                {"path": "go.mod", "description": "Go module config"},
                {"path": "main.go", "description": "Entry point"},
                {"path": "handlers/", "description": "HTTP handlers"},
                {"path": "handlers_test.go", "description": "Handler tests"},
            ])

        return files

    def _estimate_effort(self, project_type: str, features: list[str] | None) -> str:
        base_hours = {
            "web_app": 40, "cli_tool": 16, "mobile_app": 60,
            "ai_project": 80, "desktop_app": 50, "library": 20,
            "microservice": 24,
        }
        hours = base_hours.get(project_type, 40)
        if features:
            hours += len(features) * 4
        if hours <= 20:
            return f"~{hours} hours (1-2 weeks)"
        elif hours <= 60:
            return f"~{hours} hours (2-4 weeks)"
        else:
            return f"~{hours} hours (1-2 months)"

    def _get_dependencies(self, tech_stack: list[str]) -> list[str]:
        deps: list[str] = []
        for tech in tech_stack:
            t = tech.lower()
            if t == "python":
                deps.append("python>=3.10")
            elif t == "fastapi":
                deps.extend(["fastapi", "uvicorn[standard]"])
            elif t == "flask":
                deps.append("flask")
            elif t == "pytorch":
                deps.append("torch")
            elif t == "tensorflow":
                deps.append("tensorflow")
            elif t == "react" or t == "react native":
                deps.append("react")
            elif t == "next.js":
                deps.append("next")
            elif t == "postgresql":
                deps.append("postgresql")
            elif t == "docker":
                deps.append("docker")
            elif t == "redis":
                deps.append("redis")
        return deps

    def _format_plan(self, plan: ProjectPlan) -> str:
        lines = [
            f"# Project Plan: {plan.name}",
            f"",
            f"**Description:** {plan.description}",
            f"**Estimated Effort:** {plan.estimated_effort}",
            f"",
            "## Tech Stack",
            ", ".join(plan.tech_stack),
            "",
            "## Phases",
        ]
        for i, phase in enumerate(plan.phases, 1):
            lines.append(f"\n### Phase {i}: {phase['name']}")
            for task in phase.get("tasks", []):
                lines.append(f"- [ ] {task}")

        lines.append("\n## File Structure")
        for f in plan.files:
            lines.append(f"- `{f['path']}` — {f['description']}")

        if plan.dependencies:
            lines.append("\n## Dependencies")
            for d in plan.dependencies:
                lines.append(f"- {d}")

        return "\n".join(lines)
