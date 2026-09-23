from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any
from uuid import uuid4

from app.database.repository import WorkflowRepository
from app.memory.manager import MemoryManager
from app.monitoring.metrics import WorkflowTimer, metrics
from app.workflow.graph import build_workflow


class JobManager:
    def __init__(self, max_workers: int = 2):
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="workflow-worker",
        )
        self.futures: dict[str, Future[Any]] = {}
        self.database = WorkflowRepository()
        self.memory = MemoryManager()

    def _ensure_executor(self) -> None:
        if getattr(self.executor, "_shutdown", False):
            self.executor = ThreadPoolExecutor(
                max_workers=self.max_workers,
                thread_name_prefix="workflow-worker",
            )

    def submit(
        self,
        task: str,
        max_retries: int = 2,
    ) -> str:
        self._ensure_executor()
        workflow_id = str(uuid4())

        self.database.create_workflow(
            workflow_id=workflow_id,
            task=task,
            status="pending",
        )

        metrics.workflow_submitted()

        self.memory.record_event(
            workflow_id,
            {
                "type": "workflow_submitted",
                "message": "Workflow submitted through FastAPI.",
            },
        )

        future = self.executor.submit(
            self._run_workflow,
            workflow_id,
            task,
            max_retries,
        )

        self.futures[workflow_id] = future

        return workflow_id

    def _run_workflow(
        self,
        workflow_id: str,
        task: str,
        max_retries: int,
    ) -> dict:
        timer = WorkflowTimer()

        if self.memory.is_cancel_requested(workflow_id):
            result = {
                "workflow_id": workflow_id,
                "task": task,
                "status": "cancelled",
                "cancel_requested": True,
                "error": "Workflow cancelled before execution.",
            }

            self.database.update_workflow(
                workflow_id,
                status="cancelled",
                error=result["error"],
                state=result,
            )

            metrics.workflow_cancelled(timer.elapsed())

            self.memory.record_event(
                workflow_id,
                {
                    "type": "workflow_cancelled",
                    "message": "Workflow cancelled before execution started.",
                },
            )

            return result

        # Worker has started: PENDING -> RUNNING.
        self.database.update_workflow(
            workflow_id,
            status="running",
        )

        self.memory.record_event(
            workflow_id,
            {
                "type": "workflow_started",
                "message": "Workflow execution started by worker.",
            },
        )

        workflow = build_workflow()

        state = {
            "workflow_id": workflow_id,
            "task": task,
            "status": "running",
            "retry_count": 0,
            "max_retries": max_retries,
            "attempt_history": [],
            "tool_requests": [],
            "tool_results": [],
            "tool_calls": [],
            "tool_round": 0,
            "cancel_requested": False,
            "error": "",
        }

        try:
            result = workflow.invoke(state)

            final_status = result.get("status", "completed")

            if final_status == "cancelled":
                self.database.update_workflow(
                    workflow_id,
                    status="cancelled",
                    error=result.get("error"),
                    state=result,
                    selected_agent=result.get("selected_agent"),
                    final_result=result.get("final_result"),
                )

                metrics.workflow_cancelled(timer.elapsed())

                self.memory.record_event(
                    workflow_id,
                    {
                        "type": "workflow_cancelled",
                        "message": "Workflow execution cancelled.",
                    },
                )

                return result

            if final_status == "failed":
                self.database.update_workflow(
                    workflow_id,
                    status="failed",
                    error=result.get("error"),
                    state=result,
                    selected_agent=result.get("selected_agent"),
                    final_result=result.get("final_result"),
                )

                metrics.workflow_failed(timer.elapsed())

                self.memory.record_event(
                    workflow_id,
                    {
                        "type": "workflow_failed",
                        "message": result.get(
                            "error",
                            "Workflow execution failed.",
                        ),
                    },
                )

                return result

            # Successful terminal state.
            metrics.workflow_completed(timer.elapsed())

            self.database.update_workflow(
                workflow_id,
                status="completed",
                selected_agent=result.get("selected_agent"),
                final_result=result.get("final_result"),
                error=result.get("error"),
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

        except Exception as exc:
            error = f"Worker error: {exc}"

            metrics.workflow_failed(timer.elapsed())

            self.database.update_workflow(
                workflow_id,
                status="failed",
                error=error,
            )

            self.memory.record_event(
                workflow_id,
                {
                    "type": "workflow_failed",
                    "message": error,
                },
            )

            raise

        finally:
            self._cleanup_future(workflow_id)

    def _cleanup_future(self, workflow_id: str) -> None:
        self.futures.pop(workflow_id, None)

    def cancel(self, workflow_id: str) -> tuple[str, str]:
        workflow = self.database.get_workflow(workflow_id)

        if workflow is None:
            raise ValueError("Workflow not found.")

        if workflow.status in {
            "completed",
            "failed",
            "cancelled",
        }:
            return (
                workflow.status,
                f"Workflow is already {workflow.status}.",
            )

        self.memory.request_cancel(workflow_id)

        state = dict(workflow.state or {})
        state["cancel_requested"] = True

        future = self.futures.get(workflow_id)

        # Worker has not started yet.
        if future is not None and future.cancel():
            message = "Workflow cancelled before execution started."

            self.database.update_workflow(
                workflow_id,
                status="cancelled",
                error=message,
                state=state,
            )

            # The worker never starts in this branch, so there is no
            # worker timer to account for.
            metrics.workflow_cancelled(0.0)

            self.memory.record_event(
                workflow_id,
                {
                    "type": "workflow_cancelled",
                    "message": message,
                },
            )

            self._cleanup_future(workflow_id)

            return "cancelled", message

        # Worker is already running. Cancellation is cooperative.
        self.database.update_workflow(
            workflow_id,
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

        return (
            "cancellation_requested",
            "Cancellation requested; workflow is still running.",
        )

    def get_future(self, workflow_id: str) -> Future[Any] | None:
        return self.futures.get(workflow_id)

    def shutdown(self) -> None:
        """Gracefully shut down workflow workers.

        Running workflows are allowed to finish. Queued workflows that
        have not started are cancelled.
        """
        self.executor.shutdown(
            wait=True,
            cancel_futures=True,
        )
        self.futures.clear()
