from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from enum import StrEnum
from threading import Event
from typing import Any, Iterable


class JobKind(StrEnum):
    SCAN = "scan"
    METADATA = "metadata"
    ARTWORK = "artwork"
    VALIDATE = "validate"
    APPLY = "apply"


class JobState(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    NEEDS_REVIEW = "needs_review"
    SKIPPED = "skipped"
    FAILED = "failed"
    CANCELLED = "cancelled"


TERMINAL_JOB_STATES = {
    JobState.SUCCEEDED,
    JobState.NEEDS_REVIEW,
    JobState.SKIPPED,
    JobState.FAILED,
    JobState.CANCELLED,
}

_ALLOWED_TRANSITIONS: dict[JobState, set[JobState]] = {
    JobState.QUEUED: {JobState.RUNNING, JobState.SKIPPED, JobState.CANCELLED},
    JobState.RUNNING: {
        JobState.SUCCEEDED,
        JobState.NEEDS_REVIEW,
        JobState.SKIPPED,
        JobState.FAILED,
        JobState.CANCELLED,
    },
    JobState.FAILED: {JobState.QUEUED, JobState.CANCELLED},
    JobState.NEEDS_REVIEW: {JobState.QUEUED, JobState.SKIPPED, JobState.CANCELLED},
    JobState.SUCCEEDED: set(),
    JobState.SKIPPED: {JobState.QUEUED},
    JobState.CANCELLED: {JobState.QUEUED},
}


@dataclass(slots=True)
class CancellationToken:
    _event: Event = field(default_factory=Event)

    def cancel(self) -> None:
        self._event.set()

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()

    def raise_if_cancelled(self) -> None:
        if self.cancelled:
            raise JobCancelledError("Job was cancelled.")


class JobCancelledError(RuntimeError):
    pass


@dataclass(slots=True)
class JobRecord:
    job_id: str
    item_id: str
    kind: JobKind
    state: JobState = JobState.QUEUED
    progress: float = 0.0
    message: str = ""
    attempts: int = 0
    error: str = ""
    result: dict[str, Any] = field(default_factory=dict)

    def transition(self, state: JobState, *, message: str | None = None) -> None:
        if state == self.state:
            if message is not None:
                self.message = message
            return
        allowed = _ALLOWED_TRANSITIONS[self.state]
        if state not in allowed:
            raise ValueError(f"Invalid job transition: {self.state} -> {state}")
        self.state = state
        if state is JobState.RUNNING:
            self.attempts += 1
            self.error = ""
        if state in TERMINAL_JOB_STATES and state is not JobState.FAILED:
            self.progress = 1.0
        if message is not None:
            self.message = message

    def update_progress(self, value: float, *, message: str | None = None) -> None:
        if self.state is not JobState.RUNNING:
            raise ValueError("Progress can only be updated while a job is running.")
        if not 0.0 <= value <= 1.0:
            raise ValueError("Progress must be between 0.0 and 1.0.")
        self.progress = value
        if message is not None:
            self.message = message

    def fail(self, error: BaseException | str) -> None:
        self.error = str(error)
        self.transition(JobState.FAILED, message=self.error)

    def retry(self) -> None:
        if self.state not in {
            JobState.FAILED,
            JobState.NEEDS_REVIEW,
            JobState.SKIPPED,
            JobState.CANCELLED,
        }:
            raise ValueError(f"Job in state {self.state} cannot be retried.")
        self.progress = 0.0
        self.result.clear()
        self.transition(JobState.QUEUED, message="Queued for retry")

    @property
    def terminal(self) -> bool:
        return self.state in TERMINAL_JOB_STATES


@dataclass(frozen=True, slots=True)
class BatchSummary:
    total: int
    queued: int
    running: int
    succeeded: int
    needs_review: int
    skipped: int
    failed: int
    cancelled: int

    @classmethod
    def from_jobs(cls, jobs: Iterable[JobRecord]) -> "BatchSummary":
        records = list(jobs)
        counts = Counter(job.state for job in records)
        return cls(
            total=len(records),
            queued=counts[JobState.QUEUED],
            running=counts[JobState.RUNNING],
            succeeded=counts[JobState.SUCCEEDED],
            needs_review=counts[JobState.NEEDS_REVIEW],
            skipped=counts[JobState.SKIPPED],
            failed=counts[JobState.FAILED],
            cancelled=counts[JobState.CANCELLED],
        )

    @property
    def complete(self) -> bool:
        return self.total > 0 and self.queued == 0 and self.running == 0

    @property
    def finished(self) -> int:
        return self.total - self.queued - self.running
