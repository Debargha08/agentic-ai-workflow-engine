from typing import Any

from app.memory.short_term import RedisShortTermMemory
from app.workflow.state import WorkflowState


class MemoryManager:
    def __init__(self):
        self.short_term = RedisShortTermMemory()

    def save_state(
        self,
        workflow_id: str,
        state: WorkflowState,
    ) -> None:
        self.short_term.save_state(
            workflow_id,
            state,
        )

    def load_state(
        self,
        workflow_id: str,
    ) -> WorkflowState | None:
        return self.short_term.load_state(
            workflow_id,
        )

    def record_event(
        self,
        workflow_id: str,
        event: dict[str, Any],
    ) -> None:
        self.short_term.append_event(
            workflow_id,
            event,
        )

    def get_events(
        self,
        workflow_id: str,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        return self.short_term.get_events(
            workflow_id,
            limit,
        )

    def request_cancel(self, workflow_id: str) -> None:
        self.short_term.request_cancel(workflow_id)

    def is_cancel_requested(self, workflow_id: str) -> bool:
        return self.short_term.is_cancel_requested(workflow_id)

    def clear(self, workflow_id: str) -> None:
        self.short_term.clear(workflow_id)
