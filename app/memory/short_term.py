import json
from typing import Any

from app.config import REDIS_KEY_PREFIX
from app.memory.redis_client import get_redis
from app.workflow.state import WorkflowState


class RedisShortTermMemory:
    def __init__(self):
        self.redis = get_redis()

    def _state_key(self, workflow_id: str) -> str:
        return f"{REDIS_KEY_PREFIX}:state:{workflow_id}"

    def _events_key(self, workflow_id: str) -> str:
        return f"{REDIS_KEY_PREFIX}:events:{workflow_id}"

    def _cancel_key(self, workflow_id: str) -> str:
        return f"{REDIS_KEY_PREFIX}:cancel:{workflow_id}"

    def save_state(
        self,
        workflow_id: str,
        state: WorkflowState,
    ) -> None:
        self.redis.set(
            self._state_key(workflow_id),
            json.dumps(state),
        )

    def load_state(
        self,
        workflow_id: str,
    ) -> WorkflowState | None:
        value = self.redis.get(
            self._state_key(workflow_id)
        )

        if value is None:
            return None

        return json.loads(value)

    def append_event(
        self,
        workflow_id: str,
        event: dict[str, Any],
    ) -> None:
        self.redis.rpush(
            self._events_key(workflow_id),
            json.dumps(event),
        )

    def get_events(
        self,
        workflow_id: str,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        values = self.redis.lrange(
            self._events_key(workflow_id),
            max(0, -limit),
            -1,
        )

        return [
            json.loads(value)
            for value in values
        ]

    def request_cancel(self, workflow_id: str) -> None:
        self.redis.set(self._cancel_key(workflow_id), "1")

    def is_cancel_requested(self, workflow_id: str) -> bool:
        return self.redis.get(self._cancel_key(workflow_id)) == "1"

    def clear(self, workflow_id: str) -> None:
        self.redis.delete(
            self._state_key(workflow_id),
            self._events_key(workflow_id),
            self._cancel_key(workflow_id),
        )
