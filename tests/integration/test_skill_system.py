import pytest
from jarvis.core.skills import SkillManager


@pytest.mark.integration
class TestSkillDiscovery:
    def test_discover_skills(self):
        mgr = SkillManager()
        skills = mgr.discover_skills()
        assert isinstance(skills, (list, dict))
        assert len(skills) > 0


@pytest.mark.integration
class TestSkillInstallRemove:
    def test_install_skill(self):
        mgr = SkillManager()
        result = mgr.install_skill("test_skill_path.mock_skill")
        assert result is not None

    def test_remove_skill(self):
        mgr = SkillManager()
        mgr.install_skill("test_skill_path.mock_skill")
        removed = mgr.remove_skill("mock_skill")
        assert removed is True


@pytest.mark.integration
class TestSkillEnableDisable:
    def test_enable_disable(self):
        mgr = SkillManager()
        mgr.install_skill("test_skill_path.mock_skill")
        mgr.disable_skill("mock_skill")
        assert mgr.is_enabled("mock_skill") is False
        mgr.enable_skill("mock_skill")
        assert mgr.is_enabled("mock_skill") is True


@pytest.mark.integration
class TestSkillSearch:
    def test_search_skills(self):
        mgr = SkillManager()
        results = mgr.search_skills("test")
        assert isinstance(results, (list, dict))


@pytest.mark.integration
class TestSkillStats:
    def test_skill_stats(self):
        mgr = SkillManager()
        stats = mgr.get_ecosystem_stats()
        assert stats is not None
        assert "total" in stats or "count" in stats


@pytest.mark.integration
class TestMultipleSkills:
    def test_multiple_skills(self):
        mgr = SkillManager()
        results = mgr.execute_multiple(
            [{"skill": "skill1", "params": {}}, {"skill": "skill2", "params": {}}]
        )
        assert isinstance(results, list)
