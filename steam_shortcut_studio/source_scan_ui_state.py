from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .jobs import JobRecord, TERMINAL_JOB_STATES
from .library_controller import LibraryController, LibraryControllerEvent
from .sources.base import SourceAdapter
from .ui_library_adapter import (
    source_scan_adapters,
    source_scan_event_summary,
    source_scan_progress_summary,
)


@dataclass(frozen=True, slots=True)
class QueuedSourceScan:
    job_id: str
    source: str
    state: str
    progress: float


@dataclass(frozen=True, slots=True)
class SourceScanEventUpdate:
    handled: bool
    terminal: bool = False
    message: str = ""


@dataclass(frozen=True, slots=True)
class SelectedSourceScanPlan:
    adapters: tuple[SourceAdapter, ...]
    unavailable_sources: tuple[str, ...]


class SourceScanUiState:
    def __init__(self, controller: LibraryController) -> None:
        self.controller = controller
        self.job_ids: set[str] = set()
        self.retry_job_ids: set[str] = set()
        self.progress: dict[str, dict[str, object]] = {}

    def configured_adapters(
        self,
        *,
        steam_path: str | Path | None,
        collection_root: str | Path | None,
        include_epic: bool = True,
        sources: Iterable[str] | None = None,
    ) -> tuple[SourceAdapter, ...]:
        return source_scan_adapters(
            steam_path=steam_path,
            collection_root=collection_root,
            include_epic=include_epic,
            sources=sources,
        )

    def selected_source_plan(
        self,
        sources: Iterable[str],
        *,
        steam_path: str | Path | None,
        collection_root: str | Path | None,
        include_epic: bool = True,
    ) -> SelectedSourceScanPlan:
        requested = {str(source).casefold() for source in sources if str(source).strip()}
        adapters = self.configured_adapters(
            steam_path=steam_path,
            collection_root=collection_root,
            include_epic=include_epic,
            sources=requested,
        )
        available = {adapter.source_name.casefold() for adapter in adapters}
        unavailable = tuple(sorted(requested - available))
        return SelectedSourceScanPlan(adapters=adapters, unavailable_sources=unavailable)

    def queue_adapters(self, adapters: Iterable[SourceAdapter]) -> tuple[QueuedSourceScan, ...]:
        queued: list[QueuedSourceScan] = []
        for adapter in adapters:
            job = self.controller.scan_source(adapter)
            queued_scan = self._track_job(job, adapter.source_name)
            queued.append(queued_scan)
        return tuple(queued)

    def retry_available(self) -> tuple[QueuedSourceScan, ...]:
        queued: list[QueuedSourceScan] = []
        retry_ids = [
            job_id
            for job_id in sorted(self.retry_job_ids)
            if (record := self.controller.job_queue.get(job_id)) is not None
            and record.state.value in {"needs_review", "failed", "skipped", "cancelled"}
        ]
        for job_id in retry_ids:
            record = self.controller.retry_scan(job_id)
            source = str(record.result.get("source") or record.item_id.removeprefix("source:"))
            queued.append(self._track_job(record, source))
        return tuple(queued)

    def clear_retry_jobs(self) -> int:
        count = len(self.retry_job_ids)
        self.retry_job_ids.clear()
        return count

    def records(self) -> tuple[JobRecord, ...]:
        records: list[JobRecord] = []
        for job_id in self.job_ids:
            record = self.controller.job_queue.get(job_id)
            if record is not None:
                records.append(record)
        return tuple(records)

    def active(self) -> bool:
        return any(record.state not in TERMINAL_JOB_STATES for record in self.records())

    def progress_summary(self) -> str:
        return source_scan_progress_summary(self.progress)

    def handle_event(self, controller_event: LibraryControllerEvent) -> SourceScanEventUpdate:
        event = controller_event.event
        if event.job_id not in self.job_ids:
            return SourceScanEventUpdate(handled=False)

        source = str(event.result.get("source") or event.item_id.removeprefix("source:"))
        self.progress[event.job_id] = {
            "source": source,
            "state": event.state.value,
            "progress": event.progress,
        }

        if event.state in TERMINAL_JOB_STATES:
            if event.state.value in {"needs_review", "failed"}:
                self.retry_job_ids.add(event.job_id)
            else:
                self.retry_job_ids.discard(event.job_id)
            return SourceScanEventUpdate(
                handled=True,
                terminal=True,
                message=source_scan_event_summary(
                    source=source,
                    state=event.state.value,
                    result=event.result,
                    error=event.error,
                ),
            )

        return SourceScanEventUpdate(
            handled=True,
            message=self.progress_summary() if event.message else "",
        )

    def finish_summary(self) -> str:
        records = self.records()
        succeeded = sum(1 for record in records if record.state.value == "succeeded")
        needs_review = sum(1 for record in records if record.state.value == "needs_review")
        failed = sum(1 for record in records if record.state.value == "failed")
        cancelled = sum(1 for record in records if record.state.value == "cancelled")
        total = len(records)
        self.job_ids.clear()
        self.progress.clear()
        summary = f"Persistent source scans finished: {succeeded}/{total} complete"
        if needs_review:
            summary += f", {needs_review} review"
        if failed:
            summary += f", {failed} failed"
        if cancelled:
            summary += f", {cancelled} cancelled"
        return summary

    def _track_job(self, job: JobRecord, source: str) -> QueuedSourceScan:
        queued = QueuedSourceScan(
            job_id=job.job_id,
            source=source,
            state=job.state.value,
            progress=job.progress,
        )
        self.job_ids.add(job.job_id)
        self.progress[job.job_id] = {
            "source": queued.source,
            "state": queued.state,
            "progress": queued.progress,
        }
        return queued
