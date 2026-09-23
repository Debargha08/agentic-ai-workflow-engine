import time

import httpx


BASE_URL = "http://localhost:8000"


def test_container_workflow_end_to_end():
    with httpx.Client(base_url=BASE_URL, timeout=10.0) as client:
        health = client.get("/health")

        assert health.status_code == 200
        assert health.json()["status"] == "healthy"

        response = client.post(
            "/workflows",
            json={
                "task": "Explain what a REST API is.",
                "max_retries": 1,
            },
        )

        assert response.status_code == 202

        workflow_id = response.json()["workflow_id"]

        deadline = time.time() + 60

        while time.time() < deadline:
            status_response = client.get(
                f"/workflows/{workflow_id}"
            )

            assert status_response.status_code == 200

            data = status_response.json()

            if data["status"] in {"completed", "failed", "cancelled"}:
                break

            time.sleep(1)

        assert data["status"] == "completed"
        assert data["workflow_id"] == workflow_id
        assert data["final_result"]
        assert data["error"] == ""
