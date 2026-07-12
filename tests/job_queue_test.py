from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from steam_shortcut_studio.job_queue import (  # noqa: E402
    BackgroundJobQueue,
    JobExecutionResult,
)
from steam_shortcut_studio.jobs import JobKind, JobRecord, JobState  # noqa: E402


def _job(index: int, *, kind: JobKind = JobKind.ARTWORK) -> JobRecord:
    return JobRecord(job_id=f"job-{index}", item_id=f"game-{index}", kind=kind)


def test_queue_bounds_concurrency_and_emits_progress_events() -> None:
    active = 0
    max_active = 0
    lock = threading.Lock()

    def handler(record, token, report_progress):
        nonlocal active, max_active
        token.raise_if_cancelled()
        with lock:
            active += 1
            max_active = max(max_active, active)
        try:
            report_progress(0.5, "Halfway")
            time.sleep(0.015)
            return {"item": record.item_id}
        finally:
            with lock:
                active -= 1

    with BackgroundJobQueue(max_workers=3) as jobs:
        for index in range(20):
            jobs.submit(_job(index), handler)

        assert jobs.wait_for_idle(timeout=5.0)
        summary = jobs.summary()
        events = jobs.drain_events()

    assert max_active <= 3
    assert summary.total == 20
    assert summary.succeeded == 20
    assert summary.failed == 0
    assert all(record.attempts == 1 for record in jobs.records())
    assert any(event.state is JobState.RUNNING for event in events)
    assert any(event.progress == 0.5 and event.message == "Halfway" for event in events)
    assert all(record.result == {"item": record.item_id} for record in jobs.records())


def test_failed_job_is_isolated_and_retry_runs_only_that_job() -> None:
    attempts: dict[str, int] = {}

    def handler(record, token, report_progress):
        attempts[record.job_id] = attempts.get(record.job_id, 0) + 1
        token.raise_if_cancelled()
        if record.job_id == "job-1" and attempts[record.job_id] == 1:
            raise RuntimeError("temporary provider error")
        return {"attempt": attempts[record.job_id]}

    with BackgroundJobQueue(max_workers=2) as jobs:
        records = [_job(index) for index in range(3)]
        for record in records:
            jobs.submit(record, handler)
        assert jobs.wait_for_idle(timeout=5.0)

        assert records[0].state is JobState.SUCCEEDED
        assert records[1].state is JobState.FAILED
        assert records[2].state is JobState.SUCCEEDED

        jobs.retry("job-1")
        assert jobs.wait_for_idle(timeout=5.0)

    assert attempts == {"job-0": 1, "job-1": 2, "job-2": 1}
    assert records[1].state is JobState.SUCCEEDED
    assert records[1].attempts == 2
    assert records[1].result == {"attempt": 2}


def test_cancel_stops_running_and_queued_jobs_without_starting_more_work() -> None:
    first_started = threading.Event()
    release_first = threading.Event()
    second_started = threading.Event()

    def first_handler(record, token, report_progress):
        first_started.set()
        while not release_first.wait(0.01):
            token.raise_if_cancelled()
        token.raise_if_cancelled()
        return None

    def second_handler(record, token, report_progress):
        second_started.set()
        return None

    jobs = BackgroundJobQueue(max_workers=1)
    first = _job(0)
    second = _job(1)
    jobs.submit(first, first_handler)
    jobs.submit(second, second_handler)

    assert first_started.wait(2.0)
    assert jobs.cancel("job-1")
    assert jobs.cancel("job-0")
    release_first.set()
    assert jobs.wait_for_idle(timeout=5.0)
    jobs.close()

    assert first.state is JobState.CANCELLED
    assert second.state is JobState.CANCELLED
    assert not second_started.is_set()


def test_handler_can_route_an_item_to_review() -> None:
    def handler(record, token, report_progress):
        return JobExecutionResult(
            state=JobState.NEEDS_REVIEW,
            result={"reason": "edition conflict"},
            message="Choose the correct edition",
        )

    with BackgroundJobQueue(max_workers=1) as jobs:
        record = _job(0)
        jobs.submit(record, handler)
        assert jobs.wait_for_idle(timeout=2.0)

    assert record.state is JobState.NEEDS_REVIEW
    assert record.result == {"reason": "edition conflict"}
    assert record.message == "Choose the correct edition"


if __name__ == "__main__":
    test_queue_bounds_concurrency_and_emits_progress_events()
    test_failed_job_is_isolated_and_retry_runs_only_that_job()
    test_cancel_stops_running_and_queued_jobs_without_starting_more_work()
    test_handler_can_route_an_item_to_review()
    print("Background job queue tests passed.")
