"""
Project memory store for JARVIS.
=================================
Per-project knowledge storage for tracking project-specific facts,
decisions, code references, and context.

Each project has its own isolated memory namespace.

Usage:
    projects = ProjectMemory(settings)
    await projects.initialize()
    await projects.store("jarvis", "Using FastAPI for the REST API")
    facts = await projects.recall("jarvis", "API framework")
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from jarvis.config.settings import MemorySettings
from jarvis.utils.helpers import utc_now, ensure_directory

logger = logging.getLogger(__name__)


@dataclass
class ProjectFact:
    """A fact stored within a project namespace."""
    id: str
    content: str
    category: str  # decision, implementation, bug, note, reference
    tags: list[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""
    importance: float = 0.8
    access_count: int = 0
    linked_files: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "content": self.content,
            "category": self.category,
            "tags": self.tags,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "importance": self.importance,
            "access_count": self.access_count,
            "linked_files": self.linked_files,
        }

    @classmethod
    def from_dict(cls, data: dict) -> ProjectFact:
        return cls(**data)


@dataclass
class ProjectMemory:
    """Complete memory for a single project."""
    name: str
    description: str = ""
    facts: dict[str, ProjectFact] = field(default_factory=dict)
    created_at: str = ""
    last_accessed: str = ""
    total_facts: int = 0

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "facts": {k: v.to_dict() for k, v in self.facts.items()},
            "created_at": self.created_at,
            "last_accessed": self.last_accessed,
            "total_facts": self.total_facts,
        }

    @classmethod
    def from_dict(cls, data: dict) -> ProjectMemory:
        proj = cls(
            name=data["name"],
            description=data.get("description", ""),
            created_at=data.get("created_at", ""),
            last_accessed=data.get("last_accessed", ""),
            total_facts=data.get("total_facts", 0),
        )
        for fid, fdata in data.get("facts", {}).items():
            proj.facts[fid] = ProjectFact.from_dict(fdata)
        return proj


class ProjectMemoryStore:
    """Per-project memory storage.

    Each project gets its own file and namespace. Facts can be
    categorized as decisions, implementations, bugs, notes, or references.

    Example:
        store = ProjectMemoryStore(settings)
        await store.store("jarvis", "Using PyAudio for mic input", category="implementation")
        results = await store.search("jarvis", "audio input")
    """

    def __init__(self, settings: MemorySettings):
        self._storage_dir = Path(settings.projects_dir)
        self._max_per_project = settings.max_project_memories
        self._projects: dict[str, ProjectMemory] = {}
        self._initialized = False

    async def initialize(self) -> None:
        """Load all project memories from disk."""
        ensure_directory(self._storage_dir)

        for project_file in self._storage_dir.glob("*.json"):
            try:
                data = json.loads(project_file.read_text(encoding="utf-8"))
                project = ProjectMemory.from_dict(data)
                self._projects[project.name] = project
            except Exception as exc:
                logger.error("Failed to load project %s: %s", project_file.name, exc)

        self._initialized = True
        logger.info("ProjectMemoryStore initialized (%d projects)", len(self._projects))

    def _get_project(self, name: str) -> ProjectMemory:
        """Get or create a project memory."""
        if name not in self._projects:
            self._projects[name] = ProjectMemory(
                name=name,
                created_at=utc_now().isoformat(),
                last_accessed=utc_now().isoformat(),
            )
        proj = self._projects[name]
        proj.last_accessed = utc_now().isoformat()
        return proj

    def _save_project(self, project: ProjectMemory) -> None:
        """Persist a project to disk."""
        path = self._storage_dir / f"{project.name}.json"
        path.write_text(
            json.dumps(project.to_dict(), indent=2, default=str),
            encoding="utf-8",
        )

    async def store(
        self,
        project_name: str,
        content: str,
        category: str = "note",
        tags: list[str] | None = None,
        importance: float = 0.8,
        linked_files: list[str] | None = None,
    ) -> ProjectFact:
        """Store a fact in a project's memory.

        Args:
            project_name: Project identifier.
            content: Fact content.
            category: Fact type (decision, implementation, bug, note, reference).
            tags: Tags for categorization.
            importance: Importance score (0-1).
            linked_files: Related file paths.

        Returns:
            The created ProjectFact.
        """
        project = self._get_project(project_name)

        # Enforce limit
        if len(project.facts) >= self._max_per_project:
            # Remove least important fact
            least = min(project.facts.values(), key=lambda f: (f.importance, f.access_count))
            del project.facts[least.id]

        now = utc_now().isoformat()
        fact = ProjectFact(
            id=str(uuid.uuid4()),
            content=content,
            category=category,
            tags=tags or [],
            created_at=now,
            updated_at=now,
            importance=importance,
            linked_files=linked_files or [],
        )

        project.facts[fact.id] = fact
        project.total_facts = len(project.facts)
        self._save_project(project)

        logger.debug("Project '%s': stored fact '%s'", project_name, content[:50])
        return fact

    async def search(
        self,
        project_name: str,
        query: str,
        category: str | None = None,
        limit: int = 10,
    ) -> list[ProjectFact]:
        """Search facts within a project.

        Args:
            project_name: Project identifier.
            query: Search terms.
            category: Filter by category.
            limit: Maximum results.

        Returns:
            Matching facts sorted by relevance.
        """
        project = self._get_project(project_name)
        query_lower = query.lower()
        words = set(query_lower.split())

        scored: list[tuple[float, ProjectFact]] = []
        for fact in project.facts.values():
            if category and fact.category != category:
                continue
            content_lower = fact.content.lower()
            tag_match = any(query_lower in t.lower() for t in fact.tags)
            word_overlap = sum(1 for w in words if w in content_lower)
            score = (word_overlap / max(len(words), 1)) * fact.importance
            if tag_match:
                score += 0.3
            if score > 0:
                scored.append((score, fact))

        scored.sort(key=lambda x: x[0], reverse=True)

        results = []
        for _, fact in scored[:limit]:
            fact.access_count += 1
            results.append(fact)

        if results:
            self._save_project(project)

        return results

    async def get_recent(self, project_name: str, limit: int = 10) -> list[ProjectFact]:
        """Get the most recent facts for a project."""
        project = self._get_project(project_name)
        facts = sorted(project.facts.values(), key=lambda f: f.created_at, reverse=True)
        return facts[:limit]

    async def get_by_category(self, project_name: str, category: str) -> list[ProjectFact]:
        """Get all facts in a category."""
        project = self._get_project(project_name)
        return [f for f in project.facts.values() if f.category == category]

    async def delete_fact(self, project_name: str, fact_id: str) -> bool:
        """Delete a fact from a project."""
        project = self._get_project(project_name)
        if fact_id in project.facts:
            del project.facts[fact_id]
            project.total_facts = len(project.facts)
            self._save_project(project)
            return True
        return False

    async def list_projects(self) -> list[dict]:
        """List all projects with stats."""
        return [
            {
                "name": p.name,
                "description": p.description,
                "total_facts": p.total_facts,
                "created_at": p.created_at,
                "last_accessed": p.last_accessed,
            }
            for p in self._projects.values()
        ]

    async def get_project_context(self, project_name: str) -> str:
        """Get a formatted context string for a project."""
        project = self._get_project(project_name)
        lines = [f"Project: {project.name}"]
        if project.description:
            lines.append(f"Description: {project.description}")

        # Group facts by category
        by_cat: dict[str, list[ProjectFact]] = {}
        for fact in project.facts.values():
            if fact.category not in by_cat:
                by_cat[fact.category] = []
            by_cat[fact.category].append(fact)

        for cat, facts in sorted(by_cat.items()):
            lines.append(f"\n[{cat}]")
            for f in sorted(facts, key=lambda x: x.importance, reverse=True)[:5]:
                lines.append(f"  - {f.content}")

        return "\n".join(lines)
