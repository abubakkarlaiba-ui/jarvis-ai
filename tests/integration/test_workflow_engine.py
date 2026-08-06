import pytest
from jarvis.core.workflow import WorkflowEngine


@pytest.mark.integration
class TestWorkflowCreation:
    def test_create_workflow(self):
        engine = WorkflowEngine()
        steps = [{"id": "step1", "action": "test"}]
        workflow = engine.create_workflow(name="test", steps=steps)
        assert workflow is not None

    def test_plan_from_goal(self):
        engine = WorkflowEngine()
        plan = engine.plan_from_goal("Analyze sales data and generate report")
        assert plan is not None


@pytest.mark.integration
class TestWorkflowExecution:
    def test_execute_simple(self):
        engine = WorkflowEngine()
        steps = [{"id": "step1", "action": "test"}]
        workflow = engine.create_workflow(name="simple", steps=steps)
        result = engine.execute(workflow.id)
        assert result is not None

    def test_execute_with_deps(self):
        engine = WorkflowEngine()
        steps = [
            {"id": "step1", "action": "test"},
            {"id": "step2", "action": "test", "depends_on": ["step1"]},
        ]
        workflow = engine.create_workflow(name="deps", steps=steps)
        result = engine.execute(workflow.id)
        assert result is not None

    def test_execute_parallel(self):
        engine = WorkflowEngine()
        steps = [
            {"id": "step1", "action": "test"},
            {"id": "step2", "action": "test"},
        ]
        workflow = engine.create_workflow(name="parallel", steps=steps)
        result = engine.execute(workflow.id)
        assert result is not None


@pytest.mark.integration
class TestWorkflowControl:
    def test_pause_resume(self):
        engine = WorkflowEngine()
        steps = [{"id": "step1", "action": "test"}]
        workflow = engine.create_workflow(name="pause_resume", steps=steps)
        engine.execute(workflow.id)
        engine.pause(workflow.id)
        assert engine.get_status(workflow.id) == "paused"
        engine.resume(workflow.id)
        assert engine.get_status(workflow.id) != "paused"

    def test_cancel(self):
        engine = WorkflowEngine()
        steps = [{"id": "step1", "action": "test"}]
        workflow = engine.create_workflow(name="cancel", steps=steps)
        engine.execute(workflow.id)
        engine.cancel(workflow.id)
        assert engine.get_status(workflow.id) == "cancelled"

    def test_retry_failed(self):
        engine = WorkflowEngine()
        steps = [{"id": "step1", "action": "test"}]
        workflow = engine.create_workflow(name="retry", steps=steps)
        engine.execute(workflow.id)
        engine.retry_failed(workflow.id)
        assert engine.get_status(workflow.id) is not None


@pytest.mark.integration
class TestWorkflowPersistence:
    def test_persistence(self):
        engine = WorkflowEngine()
        steps = [{"id": "step1", "action": "test"}]
        workflow = engine.create_workflow(name="persist", steps=steps)
        engine.save(workflow.id)
        loaded = engine.load(workflow.id)
        assert loaded is not None
        assert loaded.id == workflow.id


@pytest.mark.integration
class TestWorkflowProgress:
    def test_progress_tracking(self):
        engine = WorkflowEngine()
        steps = [{"id": "step1", "action": "test"}]
        workflow = engine.create_workflow(name="progress", steps=steps)
        engine.execute(workflow.id)
        progress = engine.get_progress(workflow.id)
        assert progress is not None
