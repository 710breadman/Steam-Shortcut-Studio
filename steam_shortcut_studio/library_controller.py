from __future__ import annotations

from dataclasses import asdict, dataclass
from threading import RLock
from typing import Mapping
from uuid import uuid4

from .job_queue import BackgroundJobQueue, JobEvent, JobExecutionResult
from .jobs import JobKind, JobRecord, JobState, TERMINAL_JOB_STATES
from .library_store import LibraryStore
from .selection import SelectionState
from .source_scans import PersistedSourceScan, SourceScanCoordinator
from .sources.base import SourceAdapter


@dataclass(frozen=True, slots=True)
class LibraryRow:
    item_id: str
    title: str
    source: str
    external_id: str
    platform: str
    install_path: str
    launch_target: str
    launch_arguments: str
    working_directory: str
    size_bytes: int
    version: str
    is_present: bool
    launch_target_exists: bool | None
    status: str
    overridden_fields: frozenset[str]
    locked_slots: frozenset[str]


@dataclass(frozen=True, slots=True)
class LibrarySnapshot:
    rows: tuple[LibraryRow, ...]
    active_item_id: str | None
    selected_ids: frozenset[str]

    @property
    def total(self) -> int:
        return len(self.rows)

    @property
    def selected_count(self) -> int:
        return len(self.selected_ids)


@dataclass(frozen=True, slots=True)
class LibraryControllerEvent:
    event: JobEvent
    snapshot: LibrarySnapshot | None = None


class LibraryController:
    """Tk-free library and source-scan boundary for legacy and modern UIs."""

    def __init__(
        self,
        store: LibraryStore,
        *,
        job_queue: BackgroundJobQueue | None = None,
    ) -> None:
        self.store = store
        self.job_queue = job_queue or BackgroundJobQueue(max_workers=2)
        self._owns_queue = job_queue is None
        self.selection = SelectionState()
        self._rows: tuple[LibraryRow, ...] = ()
        self._scan_job_ids: set[str] = set()
        self._lock = RLock()
        self.refresh()

    @staticmethod
    def _row_status(
        *,
        is_present: bool,
        launch_target: str,
        launch_target_exists: bool | None,
        overridden_fields: frozenset[str],
        locked_slots: frozenset[str],
    ) -> str:
        if not is_present:
            return "missing"
        if not launch_target or launch_target_exists is False:
            return "review"
        if overridden_fields or locked_slots:
            return "customized"
        return "ready"

    def refresh(
        self,
        *,
        source: str | None = None,
        include_missing: bool = False,
    ) -> LibrarySnapshot:
        rows: list[LibraryRow] = []
        for record in self.store.list_records(
            source=source,
            include_missing=include_missing,
        ):
            resolved = self.store.resolve_item(record.stable_id)
            if resolved is None:
                continue
            locked_slots = frozenset(
                lock.slot for lock in self.store.list_artwork_locks(record.stable_id)
            )
            rows.append(
                LibraryRow(
                    item_id=record.stable_id,
                    title=resolved.display_title,
                    source=record.source,
                    external_id=record.external_id,
                    platform=record.platform,
                    install_path=record.install_path,
                    launch_target=resolved.launch_target,
                    launch_arguments=resolved.launch_arguments,
                    working_directory=resolved.working_directory,
                    size_bytes=record.size_bytes,
                    version=record.version,
                    is_present=record.is_present,
                    launch_target_exists=record.launch_target_exists,
                    status=self._row_status(
                        is_present=record.is_present,
                        launch_target=resolved.launch_target,
                        launch_target_exists=record.launch_target_exists,
                        overridden_fields=resolved.overridden_fields,
                        locked_slots=locked_slots,
                    ),
                    overridden_fields=resolved.overridden_fields,
                    locked_slots=locked_slots,
                )
            )
        rows.sort(key=lambda row: (row.title.casefold(), row.item_id))
        valid_ids = {row.item_id for row in rows}
        with self._lock:
            self._rows = tuple(rows)
            self.selection.retain_available(valid_ids)
            return self.snapshot()

    def snapshot(self) -> LibrarySnapshot:
        with self._lock:
            return LibrarySnapshot(
                rows=self._rows,
                active_item_id=self.selection.active_id,
                selected_ids=frozenset(self.selection.selected_ids),
            )

    def row_map(self) -> Mapping[str, LibraryRow]:
        with self._lock:
            return {row.item_id: row for row in self._rows}

    def set_active(self, item_id: str | None) -> LibrarySnapshot:
        valid_ids = set(self.row_map())
        if item_id is not None and item_id not in valid_ids:
            raise KeyError(item_id)
        with self._lock:
            self.selection.set_active(item_id)
            return self.snapshot()

    def set_selected(self, item_id: str, selected: bool) -> LibrarySnapshot:
        if item_id not in self.row_map():
            raise KeyError(item_id)
        with self._lock:
            if selected:
                self.selection.add(item_id)
            else:
                self.selection.remove(item_id)
            return self.snapshot()

    def select_all(self) -> LibrarySnapshot:
        with self._lock:
            self.selection.select_all(row.item_id for row in self._rows)
            return self.snapshot()

    def clear_selection(self) -> LibrarySnapshot:
        with self._lock:
            self.selection.clear()
            return self.snapshot()

    def selected_rows(self) -> tuple[LibraryRow, ...]:
        with self._lock:
            selected = self.selection.selected_ids
            return tuple(row for row in self._rows if row.item_id in selected)

    def selected_sources(self) -> tuple[str, ...]:
        with self._lock:
            selected = self.selection.selected_ids
            sources = {row.source for row in self._rows if row.item_id in selected}
            return tuple(sorted(sources))

    @staticmethod
    def _scan_result_payload(execution: PersistedSourceScan) -> dict[str, object]:
        snapshot = execution.snapshot
        return {
            "scan_id": execution.scan_id,
            "source": execution.result.source,
            "status": execution.status,
            "authoritative": execution.authoritative,
            "persisted": execution.persisted,
            "detected_items": execution.result.item_count,
            "issue_count": execution.result.issue_count,
            "issues": [asdict(issue) for issue in execution.result.issues],
            "snapshot": (
                {
                    "inserted": snapshot.inserted,
                    "updated": snapshot.updated,
                    "marked_missing": snapshot.marked_missing,
                }
                if snapshot is not None
                else None
            ),
            "error": execution.error,
        }

    def scan_source(self, adapter: SourceAdapter) -> JobRecord:
        source_name = str(adapter.source_name or "").strip()
        if not source_name:
            raise ValueError("Source adapters require a source_name.")
        record = JobRecord(
            job_id=f"scan-{source_name}-{uuid4().hex[:12]}",
            item_id=f"source:{source_name}",
            kind=JobKind.SCAN,
            message=f"Queued {source_name} library scan",
        )

        def handler(job, token, report_progress):
            token.raise_if_cancelled()
            report_progress(0.1, f"Scanning {source_name}")
            execution = SourceScanCoordinator(self.store).run(adapter)
            token.raise_if_cancelled()
            payload = self._scan_result_payload(execution)
            if execution.succeeded:
                report_progress(1.0, f"{source_name} scan complete")
                return JobExecutionResult(
                    state=JobState.SUCCEEDED,
                    result=payload,
                    message=f"{source_name} scan complete",
                )

            issue_codes = {issue.code for issue in execution.result.issues}
            hard_failure = bool(
                "adapter_exception" in issue_codes
                or "mismatch" in execution.error.casefold()
                or execution.authoritative
            )
            if hard_failure:
                raise RuntimeError(execution.error or f"{source_name} scan failed")
            return JobExecutionResult(
                state=JobState.NEEDS_REVIEW,
                result=payload,
                message=execution.error or f"{source_name} scan needs review",
            )

        with self._lock:
            self._scan_job_ids.add(record.job_id)
        return self.job_queue.submit(record, handler)

    def retry_scan(self, job_id: str) -> JobRecord:
        record = self.job_queue.retry(job_id)
        with self._lock:
            self._scan_job_ids.add(job_id)
        return record

    def poll_events(self, limit: int | None = None) -> tuple[LibraryControllerEvent, ...]:
        events = self.job_queue.drain_events(limit)
        controller_events: list[LibraryControllerEvent] = []
        for event in events:
            snapshot: LibrarySnapshot | None = None
            if event.job_id in self._scan_job_ids and event.state in TERMINAL_JOB_STATES:
                snapshot = self.refresh()
                with self._lock:
                    self._scan_job_ids.discard(event.job_id)
            controller_events.append(
                LibraryControllerEvent(event=event, snapshot=snapshot)
            )
        return tuple(controller_events)

    def close(self, *, wait: bool = True, cancel_pending: bool = False) -> None:
        if self._owns_queue:
            self.job_queue.close(wait=wait, cancel_pending=cancel_pending)
