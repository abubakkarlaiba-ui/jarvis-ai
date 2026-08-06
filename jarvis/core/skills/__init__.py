"""
JARVIS Skills module.
=====================
Plugin system for extensible functionality.

Quick Start:
    from jarvis.core.skills import BaseSkill, SkillRegistry, SkillContext, SkillResult

    class MySkill(BaseSkill):
        metadata = SkillMetadata(name="my_skill", description="Does something cool")
        async def execute(self, context):
            return SkillResult(success=True, output="Done!")
"""

from jarvis.core.skills.module import (
    BaseSkill,
    SkillRegistry,
    SkillLoader,
    SkillContext,
    SkillResult,
    SkillMetadata,
    SkillState,
)
from jarvis.core.skills.skill_manager import SkillManager

__all__ = [
    "BaseSkill",
    "SkillRegistry",
    "SkillLoader",
    "SkillManager",
    "SkillContext",
    "SkillResult",
    "SkillMetadata",
    "SkillState",
]
