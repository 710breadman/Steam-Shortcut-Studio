from __future__ import annotations

import queue
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Callable

from .jobs import (
    BatchSummary,
    CancellationToken,
    JobCancelledError,
    JobRecord,
    JobState,
    TERMINAL_JOB_STATES,
)


@dataclass(frozen=True, slots=True)
class JobExecutionResult:
    state: JobState = JobState.SUCCEEDED
    result: dict[str, object] = field(default_factory=dict)
    message: str = ""

    def __post_init__(self) -> None:
        if self.state not in TERMINAL_JOB_STATES:
            raise ValueError("Job execution results must use a terminal state.")
        if self.state is JobState.FAILED:
            raise ValueError("Raise an exception to fail a job instead of returning FAILED.")


@dataclass(frozen=True, slots=True)
class JobEvent:
    job_id: str
    item_id: str
    state: JobState
    progress: float
    message: str
    error: str
    result: dict[str, object]


ProgressReporter = Callable[[float, str | None], None]
JobHandler = Callable[[JobRecord, CancellationToken, ProgressReporter], JobExecutionResult | dict[str, object] | None]


@dataclass(slots=True)
class _QueuedTask:
    record: JobRecord
    handler: JobHandler
    token: CancellationToken = field(default_factory=CancellationToken)
    future: Future[None] | None = None


class BackgroundJobQueue:
    """Bounded worker queue with cancellation, retry, and UI-safe events.

    Workers never call UI callbacks. Consumers poll ``drain_events`` from the UI
    thread and update widgets from those immutable snapshots.
    """

    def __init__(self, max_workers: int = 3, *, thread_name_prefix: str = "sss-job") -> None:
        if max_workers < 1:
            raise ValueError("max_workers must be at least 1.")
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix=thread_name_prefix,
        )
        self._tasks: dict[str, _QueuedTask] = {}
        self._events: queue.Queue[JobEvent] = queue.Queue()
        self._lock = threading.RLock()
        self._closed = False

    def submit(self, record: JobRecord, handler: JobHandler) -> JobRecord:
        with self._lock:
            self._ensure_open()
            if record.job_id in self._tasks:
                raise ValueError(f"Duplicate job ID: {record.job_id}")
            if record.state is not JobState.QUEUED:
                raise ValueError("New jobs must be in the queued state.")
            task = _QueuedTask(record=record, handler=handler)
            self._tasks[record.job_id] = task
            self._emit(record)
            task.future = self._executor.submit(self._run_task, task)
            return record

    def _run_task(self, task: _QueuedTask) -> None:
        record = task.record
        try:
            with self._lock:
                if record.state is JobState.CANCELLED or task.token.cancelled:
                    if record.state is not JobState.CANCELLED:
                        record.transition(JobState.CANCELLED, message="Cancelled before start")
                    self._emit(record)
                    return
                record.transition(JobState.RUNNING, message="Running")
                self._emit(record)

            def report_progress(value: float, message: str | None = None) -> None:
                task.token.raise_if_cancelled()
                with self._lock:
                    record.update_progress(value, message=message)
                    self._emit(record)

            outcome = task.handler(record, task.token, report_progress)
            task.token.raise_if_cancelled()

            if outcome is None:
                normalized = JobExecutionResult()
            elif isinstance(outcome, JobExecutionResult):
                normalized = outcome
            elif isinstance(outcome, dict):
                normalized = JobExecutionResult(result=dict(outcome))
            else:
                raise TypeError(f"Unsupported job handler result: {type(outcome).__name__}")

            with self._lock:
                record.result = dict(normalized.result)
                record.transition(normalized.state, message=normalized.message or normalized.state.value)
                self._emit(record)
        except JobCancelledError:
            with self._lock:
                if record.state not in TERMINAL_JOB_STATES:
                    record.transition(JobState.CANCELLED, message="Cancelled")
                self._emit(record)
        except BaseException as exc:
            with self._lock:
                if record.state not in TERMINAL_JOB_STATES:
                    record.fail(exc)
                self._emit(record)

    def cancel(self, job_id: str) -> bool:
        with self._lock:
            task = self._tasks.get(job_id)
            if task is None or task.record.state in TERMINAL_JOB_STATES:
                return False
            task.token.cancel()
            if task.future is not None and task.future.cancel():
                task.record.transition(JobState.CANCELLED, message="Cancelled before start")
                self._emit(task.record)
            return True

    def cancel_all(self) -> int:
        with self._lock:
            job_ids = [
                job_id
                for job_id, task in self._tasks.items()
                if task.record.state not in TERMINAL_JOB_STATES
            ]
        return sum(1 for job_id in job_ids if self.cancel(job_id))

    def retry(self, job_id: str) -> JobRecord:
        with self._lock:
            self._ensure_open()
            task = self._tasks.get(job_id)
            if task is None:
                raise KeyError(job_id)
            if task.future is not None and not task.future.done():
                raise RuntimeError("Cannot retry a job while its previous attempt is still running.")
            task.record.retry()
            task.token = CancellationToken()
            self._emit(task.record)
            task.future = self._executor.submit(self._run_task, task)
            return task.record

    def get(self, job_id: str) -> JobRecord | None:
        with self._lock:
            task = self._tasks.get(job_id)
            return task.record if task is not None else None

    def records(self) -> list[JobRecord]:
        with self._lock:
            return [task.record for task in self._tasks.values()]

    def summary(self) -> BatchSummary:
        return BatchSummary.from_jobs(self.records())

    def drain_events(self, limit: int | None = None) -> list[JobEvent]:
        events: list[JobEvent] = []
        while limit is None or len(events) < limit:
            try:
                events.append(self._events.get_nowait())
            except queue.Empty:
                break
        return events

    def wait_for_idle(self, timeout: float | None = None) -> bool:
        deadline = None if timeout is None else time.monotonic() + max(0.0, timeout)
        while True:
            summary = self.summary()
            if summary.queued == 0 and summary.running == 0:
                return True
            if deadline is not None and time.monotonic() >= deadline:
                return False
            time.sleep(0.01)

    def close(self, *, wait: bool = True, cancel_pending: bool = False) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
        if cancel_pending:
            self.cancel_all()
        self._executor.shutdown(wait=wait, cancel_futures=cancel_pending)

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("Job queue is closed.")

    def _emit(self, record: JobRecord) -> None:
        self._events.put(
            JobEvent(
                job_id=record.job_id,
                item_id=record.item_id,
                state=record.state,
                progress=record.progress,
                message=record.message,
                error=record.error,
                result=dict(record.result),
            )
        )

    def __enter__(self) -> "BackgroundJobQueue":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close(wait=True, cancel_pending=exc is not None)
