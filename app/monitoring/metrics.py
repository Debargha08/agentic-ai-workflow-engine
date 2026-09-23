from threading import Lock
from time import perf_counter


class Metrics:
    def __init__(self) -> None:
        self._lock = Lock()

        self.workflows_submitted = 0
        self.workflows_completed = 0
        self.workflows_failed = 0
        self.workflows_cancelled = 0
        self.workflows_running = 0

        self.total_execution_time = 0.0
        self.completed_execution_count = 0

    def workflow_submitted(self) -> None:
        with self._lock:
            self.workflows_submitted += 1
            self.workflows_running += 1

    def workflow_completed(self, duration: float) -> None:
        with self._lock:
            self.workflows_completed += 1
            self.workflows_running = max(
                0,
                self.workflows_running - 1,
            )
            self.total_execution_time += duration
            self.completed_execution_count += 1

    def workflow_failed(self, duration: float) -> None:
        with self._lock:
            self.workflows_failed += 1
            self.workflows_running = max(
                0,
                self.workflows_running - 1,
            )
            self.total_execution_time += duration
            self.completed_execution_count += 1

    def workflow_cancelled(self, duration: float) -> None:
        with self._lock:
            self.workflows_cancelled += 1
            self.workflows_running = max(
                0,
                self.workflows_running - 1,
            )
            self.total_execution_time += duration
            self.completed_execution_count += 1

    def snapshot(self) -> dict[str, int | float]:
        with self._lock:
            average_execution_time = (
                self.total_execution_time
                / self.completed_execution_count
                if self.completed_execution_count
                else 0.0
            )

            return {
                "workflows_submitted": self.workflows_submitted,
                "workflows_completed": self.workflows_completed,
                "workflows_failed": self.workflows_failed,
                "workflows_cancelled": self.workflows_cancelled,
                "workflows_running": self.workflows_running,
                "total_execution_time_seconds": round(
                    self.total_execution_time,
                    4,
                ),
                "average_execution_time_seconds": round(
                    average_execution_time,
                    4,
                ),
            }


metrics = Metrics()


class WorkflowTimer:
    def __init__(self) -> None:
        self._start = perf_counter()

    def elapsed(self) -> float:
        return perf_counter() - self._start
