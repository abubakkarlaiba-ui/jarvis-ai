"""Unit tests for the SkillRegistry and skill lifecycle."""

from __future__ import annotations

import pytest

from tests.conftest import run_async

from jarvis.core.skills.module import (
    BaseSkill,
    SkillContext,
    SkillMetadata,
    SkillRegistry,
    SkillResult,
    SkillState,
)


class AlphaSkill(BaseSkill):
    metadata = SkillMetadata(
        name="alpha",
        version="1.0.0",
        description="Alpha test skill",
        tags=["test"],
    )

    async def execute(self, context: SkillContext) -> SkillResult:
        return SkillResult(success=True, output=f"alpha:{context.user_input}")


class BetaSkill(BaseSkill):
    metadata = SkillMetadata(
        name="beta",
        version="0.5.0",
        description="Beta test skill",
        tags=["test", "beta"],
    )

    async def execute(self, context: SkillContext) -> SkillResult:
        return SkillResult(success=True, output=f"beta:{context.user_input}")


@pytest.fixture
def registry():
    return SkillRegistry()


@pytest.mark.unit
class TestSkillRegistry:
    def test_register_skill(self, registry):
        registry.register_class(AlphaSkill)
        skill = registry.get_skill("alpha")
        assert skill is not None
        assert skill.metadata.name == "alpha"

    def test_register_duplicate(self, registry):
        registry.register_class(AlphaSkill)
        with pytest.raises(ValueError, match="already registered"):
            registry.register_class(AlphaSkill)

    def test_execute_skill(self, registry):
        registry.register_class(AlphaSkill)
        ctx = SkillContext(user_input="hello")
        result = run_async(registry.execute("alpha", ctx))
        assert result.success is True
        assert result.output == "alpha:hello"

    def test_execute_unknown(self, registry):
        ctx = SkillContext(user_input="hello")
        result = run_async(registry.execute("nonexistent", ctx))
        assert result.success is False
        assert "not found" in result.error

    def test_enable_disable(self, registry):
        registry.register_class(AlphaSkill)
        assert registry.disable("alpha") is True
        ctx = SkillContext(user_input="hello")
        result = run_async(registry.execute("alpha", ctx))
        assert result.success is False
        assert "disabled" in result.error

        assert registry.enable("alpha") is True
        result = run_async(registry.execute("alpha", ctx))
        assert result.success is True

    def test_list_skills(self, registry):
        registry.register_class(AlphaSkill)
        registry.register_class(BetaSkill)
        skills = registry.list_skills()
        names = [s["name"] for s in skills]
        assert "alpha" in names
        assert "beta" in names

    def test_skill_lifecycle(self, registry):
        registry.register_class(AlphaSkill)
        run_async(registry.initialize_all())

        skill = registry.get_skill("alpha")
        ctx = SkillContext(user_input="test")
        result = run_async(registry.execute("alpha", ctx))
        assert result.success is True

        run_async(registry.shutdown_all())

    def test_skill_metadata(self, registry):
        registry.register_class(BetaSkill)
        skill = registry.get_skill("beta")
        assert skill.metadata.version == "0.5.0"
        assert skill.metadata.description == "Beta test skill"
        assert "beta" in skill.metadata.tags
