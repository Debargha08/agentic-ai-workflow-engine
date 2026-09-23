import time

from app.jobs.manager import JobManager


def test_job_manager_shutdown_waits_for_running_job():
    manager = JobManager(max_workers=1)

    future = manager.executor.submit(
        lambda: (time.sleep(0.2), "completed")[1]
    )

    manager.futures["shutdown-test"] = future

    manager.shutdown()

    assert future.done()
    assert future.result() == "completed"
    assert manager.futures == {}


def test_job_manager_shutdown_cancels_queued_jobs():
    manager = JobManager(max_workers=1)

    running = manager.executor.submit(
        lambda: (time.sleep(0.2), "running")[1]
    )

    queued = manager.executor.submit(
        lambda: "queued",
    )

    manager.futures["running"] = running
    manager.futures["queued"] = queued

    manager.shutdown()

    assert running.done()
    assert manager.futures == {}
    assert queued.cancelled() or queued.done()
