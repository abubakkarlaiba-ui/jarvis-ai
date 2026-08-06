"""
Skill Manager — install, remove, update, and manage skills.
==========================================================
Provides a high-level interface for managing the JARVIS skill ecosystem.

Features:
    - Install skills from local files or URLs
    - Remove skills cleanly
    - Enable/disable individual skills
    - List installed skills with metadata
    - Search for available skills
    - Track skill dependencies and versions
"""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from jarvis.core.skills.module import SkillLoader
from jarvis.core.skills.module import (
    BaseSkill,
    SkillMetadata,
    SkillRegistry,
    SkillState,
)

logger = logging.getLogger(__name__)


class SkillManager:
    """High-level skill management facade.

    Coordinates the SkillRegistry, SkillLoader, and a JSON manifest
    that tracks installed skills and their metadata.
    """

    def __init__(
        self,
        registry: SkillRegistry,
        plugins_dir: str = "./plugins",
        manifest_path: str = "./data/skills/manifest.json",
    ):
        self.registry = registry
        self.loader = SkillLoader(registry)
        self.plugins_dir = Path(plugins_dir)
        self.plugins_dir.mkdir(parents=True, exist_ok=True)
        self.manifest_path = Path(manifest_path)
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        self._manifest: dict[str, Any] = self._load_manifest()

    # ── Manifest persistence ──────────────────────────────────────

    def _load_manifest(self) -> dict[str, Any]:
        if self.manifest_path.exists():
            try:
                return json.loads(self.manifest_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                logger.warning("Corrupt manifest, starting fresh")
        return {"version": 1, "installed": {}, "disabled": []}

    def _save_manifest(self) -> None:
        tmp = self.manifest_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._manifest, indent=2), encoding="utf-8")
        tmp.replace(self.manifest_path)

    # ── Discovery ─────────────────────────────────────────────────

    async def discover_skills(self) -> list[dict[str, Any]]:
        """Scan plugins directory and reload all skills."""
        await self.loader.load_from_directory(str(self.plugins_dir))
        return self.list_skills()

    def list_skills(self) -> list[dict[str, Any]]:
        """Return metadata for every registered skill."""
        return self.registry.list_skills()

    def get_skill(self, name: str) -> BaseSkill | None:
        return self.registry.get_skill(name)

    def get_skill_info(self, name: str) -> dict[str, Any] | None:
        """Return detailed info for a single skill."""
        for entry in self.list_skills():
            if entry["name"] == name:
                info = dict(entry)
                info["installed"] = name in self._manifest.get("installed", {})
                info["disabled"] = name in self._manifest.get("disabled", [])
                installed_meta = self._manifest.get("installed", {}).get(name, {})
                if installed_meta:
                    info["installed_at"] = installed_meta.get("installed_at")
                    info["file_hash"] = installed_meta.get("file_hash")
                return info
        return None

    # ── Install / Remove ──────────────────────────────────────────

    async def install_skill(self, source_path: str, name: str | None = None) -> dict[str, Any]:
        """Install a skill from a local .skill.py file.

        Args:
            source_path: Path to the skill source file.
            name: Optional override for the skill name.

        Returns:
            Dict with status and details.
        """
        src = Path(source_path)
        if not src.exists():
            return {"success": False, "error": f"Source not found: {source_path}"}
        if not src.suffix == ".py":
            return {"success": False, "error": "Source must be a .py file"}

        file_hash = hashlib.sha256(src.read_bytes()).hexdigest()[:16]

        # Copy into plugins directory
        dest = self.plugins_dir / src.name
        if dest.exists():
            return {"success": False, "error": f"Plugin already exists: {dest.name}"}
        shutil.copy2(str(src), str(dest))

        # Try to load it
        loaded = await self.loader.load_from_directory(str(self.plugins_dir))
        if loaded == 0:
            dest.unlink(missing_ok=True)
            return {"success": False, "error": "No valid BaseSkill found in source"}

        # Find the newly loaded skill name
        skill_name = name
        if skill_name is None:
            for s in self.list_skills():
                if s["name"] not in self._manifest.get("installed", {}):
                    skill_name = s["name"]
                    break

        if skill_name and skill_name not in self._manifest["disabled"]:
            self._manifest["installed"][skill_name] = {
                "source": str(src),
                "file_hash": file_hash,
                "installed_at": datetime.now().isoformat(),
            }
            self._save_manifest()

        return {
            "success": True,
            "skill": skill_name,
            "hash": file_hash,
            "dest": str(dest),
        }

    async def remove_skill(self, name: str) -> dict[str, Any]:
        """Remove an installed skill.

        Args:
            name: The skill name to remove.

        Returns:
            Dict with status and details.
        """
        skill = self.registry.get_skill(name)
        if skill is None:
            return {"success": False, "error": f"Skill '{name}' not found"}

        # Find and delete the plugin file
        for py_file in self.plugins_dir.glob("*.skill.py"):
            try:
                import importlib.util
                spec = importlib.util.spec_from_file_location("_check", py_file)
                if spec is None or spec.loader is None:
                    continue
                import types
                mod = types.ModuleType("_check")
                spec.loader.exec_module(mod)
                for attr in dir(mod):
                    obj = getattr(mod, attr)
                    if (
                        isinstance(obj, type)
                        and issubclass(obj, BaseSkill)
                        and obj is not BaseSkill
                    ):
                        inst = obj()
                        if inst.metadata.name == name:
                            await skill.on_shutdown()
                            py_file.unlink()
                            # Remove from registry
                            self.registry._skills.pop(name, None)
                            self.registry._metadata.pop(name, None)
                            self.registry._states.pop(name, None)
                            # Update manifest
                            self._manifest.get("installed", {}).pop(name, None)
                            if name in self._manifest.get("disabled", []):
                                self._manifest["disabled"].remove(name)
                            self._save_manifest()
                            return {"success": True, "removed": name, "file": str(py_file)}
            except Exception:
                continue

        return {"success": False, "error": "Plugin file not found on disk"}

    # ── Enable / Disable ──────────────────────────────────────────

    def enable_skill(self, name: str) -> dict[str, Any]:
        """Enable a disabled skill."""
        if name in self._manifest.get("disabled", []):
            self._manifest["disabled"].remove(name)
            self._save_manifest()
        self.registry.enable(name)
        return {"success": True, "enabled": name}

    def disable_skill(self, name: str) -> dict[str, Any]:
        """Disable a skill without removing it."""
        if name not in self._manifest.get("disabled", []):
            self._manifest.setdefault("disabled", []).append(name)
            self._save_manifest()
        self.registry.disable(name)
        return {"success": True, "disabled": name}

    # ── Search ────────────────────────────────────────────────────

    def search_skills(self, query: str) -> list[dict[str, Any]]:
        """Search skills by name, description, or tags."""
        query_lower = query.lower()
        results = []
        for skill in self.list_skills():
            if (
                query_lower in skill["name"].lower()
                or query_lower in skill.get("description", "").lower()
                or any(query_lower in t.lower() for t in skill.get("tags", []))
            ):
                results.append(skill)
        return results

    # ── Lifecycle ─────────────────────────────────────────────────

    async def initialize_all(self) -> None:
        """Initialize all loaded skills."""
        await self.registry.initialize_all()

    async def shutdown_all(self) -> None:
        """Gracefully shut down all skills."""
        await self.registry.shutdown_all()

    # ── Stats ─────────────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        """Return summary statistics about installed skills."""
        all_skills = self.list_skills()
        return {
            "total": len(all_skills),
            "enabled": sum(
                1 for s in all_skills
                if s["state"] not in ("DISABLED", "ERROR", "UNLOADED")
            ),
            "disabled": len(self._manifest.get("disabled", [])),
            "error": sum(1 for s in all_skills if s["state"] == "ERROR"),
            "installed": len(self._manifest.get("installed", {})),
        }
