import time
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.server import app
from app.api.routes import workflows as workflows_module
from app.jobs.manager import JobManager
from app.monitoring.metrics import metrics


def test_workflow_api_end_to_end(monkeypatch):
    def fake_run_workflow(
        self,
        workflow_id: str,
        task: str,
        max_retries: int,
    ):
        result = {
            "workflow_id": workflow_id,
            "task": task,
            "status": "completed",
            "selected_agent": "research",
            "retry_count": 0,
            "final_result": "Fake workflow completed successfully.",
            "error": "",
        }

        self.database.update_workflow(
            workflow_id,
            status="completed",
            selected_agent="research",
            final_result=result["final_result"],
            error="",
            state=result,
        )

        self.memory.record_event(
            workflow_id,
            {
                "type": "workflow_completed",
                "message": "Workflow completed successfully.",
            },
        )

        return result

    monkeypatch.setattr(
        JobManager,
        "_run_workflow",
        fake_run_workflow,
    )

    before = metrics.snapshot()

    with TestClient(app) as client:
        response = client.post(
            "/workflows",
            json={
                "task": "Test API workflow execution.",
                "max_retries": 2,
            },
        )

        assert response.status_code == 202

        workflow_id = response.json()["workflow_id"]

        assert response.json()["status"] == "pending"

        deadline = time.time() + 5

        while time.time() < deadline:
            status_response = client.get(
                f"/workflows/{workflow_id}"
            )

            assert status_response.status_code == 200

            status = status_response.json()["status"]

            if status == "completed":
                break

            time.sleep(0.05)

        assert status == "completed"

        status_data = status_response.json()

        assert status_data["workflow_id"] == workflow_id
        assert status_data["selected_agent"] == "research"
        assert (
            status_data["final_result"]
            == "Fake workflow completed successfully."
        )

        events_response = client.get(
            f"/workflows/{workflow_id}/events"
        )

        assert events_response.status_code == 200

        events = events_response.json()["events"]

        event_types = [event["type"] for event in events]

        assert "workflow_submitted" in event_types
        assert "workflow_completed" in event_types

        metrics_response = client.get("/metrics")

        assert metrics_response.status_code == 200

        after = metrics_response.json()

        assert (
            after["workflows_submitted"]
            >= before["workflows_submitted"] + 1
        )


def test_workflow_cancellation_api(monkeypatch):
    class FakeJobManager:
        def __init__(self):
            self.database = workflows_module.database
            self.memory = workflows_module.memory
            self.workflow_id = None

        def submit(self, task: str, max_retries: int = 2) -> str:
            workflow_id = f"api-cancel-test-{uuid4()}"

            self.workflow_id = workflow_id

            self.database.create_workflow(
                workflow_id=workflow_id,
                task=task,
                status="running",
            )

            self.memory.record_event(
                workflow_id,
                {
                    "type": "workflow_submitted",
                    "message": "Workflow submitted through FastAPI.",
                },
            )

            return workflow_id

        def cancel(self, workflow_id: str) -> tuple[str, str]:
            workflow = self.database.get_workflow(workflow_id)

            if workflow is None:
                raise ValueError("Workflow not found.")

            state = dict(workflow.state or {})
            state["cancel_requested"] = True

            self.database.update_workflow(
                workflow_id,
                status="cancelled",
                error="Workflow cancelled.",
                state=state,
            )

            self.memory.record_event(
                workflow_id,
                {
                    "type": "workflow_cancel_requested",
                    "message": (
                        "Cancellation requested; workflow will stop "
                        "at the next node boundary."
                    ),
                },
            )

            self.memory.record_event(
                workflow_id,
                {
                    "type": "workflow_cancelled",
                    "message": "Workflow cancelled.",
                },
            )

            return (
                "cancelled",
                "Workflow cancelled.",
            )

    fake_manager = FakeJobManager()

    monkeypatch.setattr(
        workflows_module,
        "job_manager",
        fake_manager,
    )

    with TestClient(app) as client:
        response = client.post(
            "/workflows",
            json={
                "task": "Test workflow cancellation.",
                "max_retries": 2,
            },
        )

        assert response.status_code == 202

        workflow_id = response.json()["workflow_id"]


        cancel_response = client.post(
            f"/workflows/{workflow_id}/cancel"
        )

        assert cancel_response.status_code == 200

        cancel_data = cancel_response.json()

        assert cancel_data["workflow_id"] == workflow_id
        assert cancel_data["status"] == "cancelled"

        status_response = client.get(
            f"/workflows/{workflow_id}"
        )

        assert status_response.status_code == 200

        status_data = status_response.json()

        assert status_data["status"] == "cancelled"
        assert status_data["error"] == "Workflow cancelled."

        events_response = client.get(
            f"/workflows/{workflow_id}/events"
        )

        assert events_response.status_code == 200

        event_types = [
            event["type"]
            for event in events_response.json()["events"]
        ]

        assert "workflow_cancel_requested" in event_types
        assert "workflow_cancelled" in event_types
