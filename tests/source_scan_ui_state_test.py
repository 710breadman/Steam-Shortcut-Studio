from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from steam_shortcut_studio.job_queue import JobEvent  # noqa: E402
from steam_shortcut_studio.jobs import JobKind, JobRecord, JobState  # noqa: E402
from steam_shortcut_studio.library_controller import LibraryControllerEvent  # noqa: E402
from steam_shortcut_studio.source_scan_ui_state import SourceScanUiState  # noqa: E402


class FakeQueue:
    def __init__(self) -> None:
        self.records: dict[str, JobRecord] = {}

    def get(self, job_id: str) -> JobRecord | None:
        return self.records.get(job_id)


class FakeController:
    def __init__(self) -> None:
        self.job_queue = FakeQueue()
        self.count = 0

    def scan_source(self, adapter: SimpleNamespace) -> JobRecord:
        self.count += 1
        record = JobRecord(
            job_id=f"scan-{self.count}",
            item_id=f"source:{adapter.source_name}",
            kind=JobKind.SCAN,
            message=f"Queued {adapter.source_name}",
            result={"source": adapter.source_name},
        )
        self.job_queue.records[record.job_id] = record
        return record

    def retry_scan(self, job_id: str) -> JobRecord:
        old = self.job_queue.records[job_id]
        record = JobRecord(
            job_id=f"{job_id}-retry",
            item_id=old.item_id,
            kind=old.kind,
            message="Retry queued",
            result=old.result,
        )
        self.job_queue.records[record.job_id] = record
        return record


def test_source_scan_ui_state_tracks_queue_progress_and_finish_summary() -> None:
    controller = FakeController()
    state = SourceScanUiState(controller)  # type: ignore[arg-type]

    queued = state.queue_adapters((SimpleNamespace(source_name="epic"), SimpleNamespace(source_name="folder")))

    assert [scan.source for scan in queued] == ["epic", "folder"]
    assert state.progress_summary() == "Source refresh: Epic queued 0%; Folder queued 0%"

    event = LibraryControllerEvent(
        event=JobEvent(
            job_id="scan-1",
            item_id="source:epic",
            state=JobState.NEEDS_REVIEW,
            progress=1,
            message="Needs review",
            error="",
            result={"source": "epic", "detected_items": 0, "issue_count": 1, "issues": [{"code": "missing"}]},
        ),
    )

    update = state.handle_event(event)

    assert update.handled is True
    assert update.terminal is True
    assert "Epic scan needs review" in update.message
    assert state.retry_job_ids == {"scan-1"}

    controller.job_queue.records["scan-1"].transition(JobState.RUNNING, message="Running")
    controller.job_queue.records["scan-1"].transition(JobState.NEEDS_REVIEW, message="Needs review")
    controller.job_queue.records["scan-2"].transition(JobState.RUNNING, message="Running")
    controller.job_queue.records["scan-2"].transition(JobState.SUCCEEDED, message="Done")

    retry = state.retry_available()

    assert [scan.job_id for scan in retry] == ["scan-1-retry"]
    assert state.finish_summary() == "Persistent source scans finished: 1/3 complete, 1 review"


def test_selected_source_plan_reports_unavailable_sources() -> None:
    state = SourceScanUiState(FakeController())  # type: ignore[arg-type]

    plan = state.selected_source_plan(
        {"epic", "steam", "folder"},
        steam_path=None,
        collection_root=None,
        include_epic=True,
    )

    assert [adapter.source_name for adapter in plan.adapters] == ["epic"]
    assert plan.unavailable_sources == ("folder", "steam")


if __name__ == "__main__":
    test_source_scan_ui_state_tracks_queue_progress_and_finish_summary()
    test_selected_source_plan_reports_unavailable_sources()
    print("Source scan UI state tests passed.")
