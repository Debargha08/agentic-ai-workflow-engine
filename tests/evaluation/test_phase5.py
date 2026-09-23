import uuid

import app.workflow.graph as graph_module
from app.database.repository import WorkflowRepository


class FakeSupervisor:
    def create_plan(self, task):
        return {
            "objective": "Produce a correct result.",
            "agent": "research",
            "steps": [
                "Generate a result",
                "Validate the result",
            ],
        }


class PassingResearchAgent:
    def execute(self, state):
        return {
            **state,
            "agent_result": "CORRECT RESULT",
            "tool_requests": [],
            "tool_calls": [],
            "status": "running",
            "error": "",
        }


class RetryThenPassResearchAgent:
    def __init__(self):
        self.calls = 0

    def execute(self, state):
        self.calls += 1

        result = (
            "INTENTIONALLY INCOMPLETE RESULT"
            if self.calls == 1
            else "CORRECTED RESULT AFTER RETRY"
        )

        return {
            **state,
            "agent_result": result,
            "tool_requests": [],
            "tool_calls": [],
            "status": "running",
            "error": "",
        }


class AlwaysBadResearchAgent:
    def __init__(self):
        self.calls = 0

    def execute(self, state):
        self.calls += 1

        return {
            **state,
            "agent_result": f"BAD RESULT {self.calls}",
            "tool_requests": [],
            "tool_calls": [],
            "status": "running",
            "error": "",
        }


class PassingReflectionAgent:
    def evaluate(self, state):
        return {
            "decision": "pass",
            "reason": "The result satisfies the task.",
        }


class RetryThenPassReflectionAgent:
    def __init__(self):
        self.calls = 0

    def evaluate(self, state):
        self.calls += 1

        if self.calls == 1:
            return {
                "decision": "retry",
                "reason": "The first result is intentionally incomplete.",
            }

        return {
            "decision": "pass",
            "reason": "The corrected result satisfies the task.",
        }


class AlwaysRetryReflectionAgent:
    def evaluate(self, state):
        return {
            "decision": "retry",
            "reason": "Intentional retry-limit test.",
        }


def make_state(workflow_id):
    return {
        "workflow_id": workflow_id,
        "task": "Test Phase 5 workflow.",
        "status": "pending",
        "retry_count": 0,
        "max_retries": 2,
        "attempt_history": [],
        "tool_requests": [],
        "tool_results": [],
        "tool_calls": [],
        "tool_round": 0,
        "error": "",
    }


def test_reflection_pass_path(monkeypatch):
    workflow_id = f"phase5-pass-{uuid.uuid4()}"

    monkeypatch.setattr(
        graph_module,
        "supervisor",
        FakeSupervisor(),
    )
    monkeypatch.setattr(
        graph_module,
        "research_agent",
        PassingResearchAgent(),
    )
    monkeypatch.setattr(
        graph_module,
        "reflection_agent",
        PassingReflectionAgent(),
    )

    workflow = graph_module.build_workflow()
    result = workflow.invoke(make_state(workflow_id))

    assert result["status"] == "completed"
    assert result["final_result"] == "CORRECT RESULT"
    assert result["reflection_decision"] == "pass"
    assert result["retry_count"] == 0
    assert len(result["attempt_history"]) == 1


def test_end_to_end_retry_and_postgres_persistence(monkeypatch):
    workflow_id = f"phase5-retry-{uuid.uuid4()}"

    research = RetryThenPassResearchAgent()

    monkeypatch.setattr(
        graph_module,
        "supervisor",
        FakeSupervisor(),
    )
    monkeypatch.setattr(
        graph_module,
        "research_agent",
        research,
    )
    monkeypatch.setattr(
        graph_module,
        "reflection_agent",
        RetryThenPassReflectionAgent(),
    )

    workflow = graph_module.build_workflow()
    result = workflow.invoke(make_state(workflow_id))

    assert result["status"] == "completed"
    assert result["final_result"] == "CORRECTED RESULT AFTER RETRY"
    assert result["reflection_decision"] == "pass"
    assert result["retry_count"] == 1
    assert len(result["attempt_history"]) == 2
    assert research.calls == 2

    repo = WorkflowRepository()
    evaluations = repo.get_reflection_evaluations(workflow_id)

    assert len(evaluations) == 2
    assert evaluations[0].attempt == 1
    assert evaluations[0].decision == "retry"
    assert evaluations[1].attempt == 2
    assert evaluations[1].decision == "pass"


def test_maximum_retry_protection(monkeypatch):
    workflow_id = f"phase5-limit-{uuid.uuid4()}"

    research = AlwaysBadResearchAgent()

    monkeypatch.setattr(
        graph_module,
        "supervisor",
        FakeSupervisor(),
    )
    monkeypatch.setattr(
        graph_module,
        "research_agent",
        research,
    )
    monkeypatch.setattr(
        graph_module,
        "reflection_agent",
        AlwaysRetryReflectionAgent(),
    )

    workflow = graph_module.build_workflow()
    result = workflow.invoke(make_state(workflow_id))

    assert result["status"] == "failed"
    assert result["retry_count"] == 2
    assert len(result["attempt_history"]) == 3
    assert "Maximum retries exhausted." in result["error"]
    assert research.calls == 3

    repo = WorkflowRepository()
    evaluations = repo.get_reflection_evaluations(workflow_id)

    assert len(evaluations) == 3
    assert all(
        evaluation.decision == "retry"
        for evaluation in evaluations
    )
