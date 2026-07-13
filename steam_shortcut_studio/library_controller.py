from __future__ import annotations

from dataclasses import asdict, dataclass
from threading import RLock
from typing import Mapping
from uuid import uuid4

from .job_queue import BackgroundJobQueue, JobEvent, JobExecutionResult
from .jobs import JobKind, JobRecord, JobState, TERMINAL_JOB_STATES
from .bulk_artwork import BulkArtworkItem
from .library_store import ArtworkLock, LibraryStore, RejectedMatch
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


@dataclass(frozen=True, slots=True)
class ArtworkResultPersistence:
    accepted: int = 0
    rejected: int = 0


@dataclass(frozen=True, slots=True)
class ArtworkDecisionSummary:
    item_count: int = 0
    locked_slots: int = 0
    rejected_matches: int = 0


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

    def set_items_selected(self, item_ids: tuple[str, ...], selected: bool) -> LibrarySnapshot:
        valid_ids = set(self.row_map())
        with self._lock:
            for item_id in item_ids:
                if item_id not in valid_ids:
                    continue
                if selected:
                    self.selection.add(item_id)
                else:
                    self.selection.remove(item_id)
            return self.snapshot()

    def toggle_items(self, item_ids: tuple[str, ...]) -> LibrarySnapshot:
        valid_ids = set(self.row_map())
        with self._lock:
            for item_id in item_ids:
                if item_id in valid_ids:
                    self.selection.toggle(item_id)
            return self.snapshot()

    def select_range(
        self,
        ordered_ids: tuple[str, ...],
        target_id: str,
        *,
        additive: bool = True,
    ) -> LibrarySnapshot:
        valid_order = tuple(item_id for item_id in ordered_ids if item_id in self.row_map())
        with self._lock:
            self.selection.select_range(valid_order, target_id, additive=additive)
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

    def artwork_decision_summary(self, item_ids: tuple[str, ...] | list[str] | None = None) -> ArtworkDecisionSummary:
        with self._lock:
            scoped_ids = tuple(item_ids) if item_ids is not None else tuple(self.selection.selected_ids)
        locked = 0
        rejected = 0
        for item_id in scoped_ids:
            locked += len(self.store.list_artwork_locks(item_id))
            rejected += len(self.store.list_rejected_matches(item_id))
        return ArtworkDecisionSummary(
            item_count=len(scoped_ids),
            locked_slots=locked,
            rejected_matches=rejected,
        )

    def clear_rejected_artwork_matches(self, item_ids: tuple[str, ...] | list[str] | None = None) -> int:
        with self._lock:
            scoped_ids = tuple(item_ids) if item_ids is not None else tuple(self.selection.selected_ids)
        cleared = 0
        for item_id in scoped_ids:
            for rejection in self.store.list_rejected_matches(item_id):
                if self.store.clear_rejected_match(
                    rejection.item_id,
                    rejection.provider,
                    rejection.slot,
                    rejection.candidate_id,
                ):
                    cleared += 1
        return cleared

    def bulk_artwork_items(self) -> Mapping[str, BulkArtworkItem]:
        with self._lock:
            return {
                row.item_id: BulkArtworkItem(
                    item_id=row.item_id,
                    title=row.title,
                    locked_slots=row.locked_slots,
                )
                for row in self._rows
            }

    def persist_artwork_job_result(
        self,
        result: Mapping[str, object],
        *,
        decision_override: str = "",
        reason_override: str = "",
    ) -> ArtworkResultPersistence:
        item_id = str(result.get("item_id") or "")
        if not item_id:
            return ArtworkResultPersistence()
        decision = decision_override or str(result.get("decision") or "")
        provider = str(result.get("provider") or "provider")
        candidate_ids = {
            str(slot): str(candidate_id)
            for slot, candidate_id in dict(result.get("candidate_ids") or {}).items()
            if str(candidate_id).strip()
        }
        details = dict(result.get("details") or {})
        validated_files = {
            str(slot): dict(file_info)
            for slot, file_info in dict(details.get("validated_files") or {}).items()
            if isinstance(file_info, Mapping)
        }
        raw_reasons = result.get("reasons") or ()
        if isinstance(raw_reasons, str):
            raw_reasons = (raw_reasons,)
        reasons = tuple(str(reason) for reason in raw_reasons if str(reason).strip())
        reason_text = reason_override or "; ".join(reasons)

        accepted = 0
        rejected = 0
        if decision == "auto_accept":
            for slot, candidate_id in candidate_ids.items():
                if slot not in {"grid", "wide", "hero", "logo", "icon"}:
                    continue
                file_info = validated_files.get(slot, {})
                self.store.set_artwork_lock(
                    ArtworkLock(
                        item_id=item_id,
                        slot=slot,
                        candidate_id=candidate_id,
                        source=provider,
                        local_path=str(file_info.get("path") or ""),
                    )
                )
                accepted += 1
        elif decision == "reject":
            for slot, candidate_id in candidate_ids.items():
                if slot not in {"grid", "wide", "hero", "logo", "icon"}:
                    continue
                self.store.reject_match(
                    RejectedMatch(
                        item_id=item_id,
                        provider=provider,
                        slot=slot,
                        candidate_id=candidate_id,
                        reason=reason_text,
                    )
                )
                rejected += 1

        if accepted or rejected:
            self.refresh()
        return ArtworkResultPersistence(accepted=accepted, rejected=rejected)

    def accept_artwork_review_result(self, result: Mapping[str, object]) -> ArtworkResultPersistence:
        return self.persist_artwork_job_result(result, decision_override="auto_accept")

    def reject_artwork_review_result(
        self,
        result: Mapping[str, object],
        *,
        reason: str = "Rejected during artwork review.",
    ) -> ArtworkResultPersistence:
        return self.persist_artwork_job_result(
            result,
            decision_override="reject",
            reason_override=reason,
        )

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
