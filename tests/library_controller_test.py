from __future__ import annotations

import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from steam_shortcut_studio.library_controller import LibraryController  # noqa: E402
from steam_shortcut_studio.library_store import (  # noqa: E402
    ArtworkLock,
    LibraryStore,
    ManualOverrides,
)
from steam_shortcut_studio.sources.base import (  # noqa: E402
    SourceIssue,
    SourceLibraryItem,
    SourceScanResult,
    stable_source_item_id,
)
from steam_shortcut_studio.jobs import JobState  # noqa: E402


def _item(external_id: str, title: str, *, exists: bool = True) -> SourceLibraryItem:
    return SourceLibraryItem(
        stable_id=stable_source_item_id("epic", external_id=external_id),
        source="epic",
        external_id=external_id,
        title=title,
        install_path=rf"C:\Games\{title}",
        launch_target=rf"C:\Games\{title}\{title}.exe",
        launch_arguments="-windowed",
        working_directory=rf"C:\Games\{title}",
        platform="windows",
        size_bytes=1024,
        launch_target_exists=exists,
    )


@dataclass
class FakeAdapter:
    result: SourceScanResult | None = None
    error: Exception | None = None
    source_name: str = "epic"

    def scan(self) -> SourceScanResult:
        if self.error is not None:
            raise self.error
        assert self.result is not None
        return self.result


def test_controller_builds_immutable_effective_rows_and_selection() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        store = LibraryStore(Path(tmp) / "library.sqlite3")
        ready = _item("ready", "Ready")
        customized = _item("custom", "Source Title")
        review = _item("review", "Review", exists=False)
        store.replace_source_snapshot("epic", [ready, customized, review])
        store.save_overrides(
            ManualOverrides(
                item_id=customized.stable_id,
                display_title="My Custom Title",
            )
        )
        store.set_artwork_lock(
            ArtworkLock(item_id=customized.stable_id, slot="grid")
        )

        controller = LibraryController(store)
        try:
            snapshot = controller.snapshot()
            assert [row.title for row in snapshot.rows] == [
                "My Custom Title",
                "Ready",
                "Review",
            ]
            by_id = {row.item_id: row for row in snapshot.rows}
            assert by_id[ready.stable_id].status == "ready"
            assert by_id[customized.stable_id].status == "customized"
            assert by_id[customized.stable_id].locked_slots == frozenset({"grid"})
            assert by_id[review.stable_id].status == "review"
            artwork_items = controller.bulk_artwork_items()
            assert artwork_items[customized.stable_id].locked_slots == frozenset({"grid"})
            assert artwork_items[ready.stable_id].title == "Ready"

            controller.set_active(ready.stable_id)
            controller.set_selected(customized.stable_id, True)
            selected = controller.snapshot()
            assert selected.active_item_id == ready.stable_id
            assert selected.selected_ids == frozenset({customized.stable_id})
            assert [row.item_id for row in controller.selected_rows()] == [
                customized.stable_id
            ]
            assert controller.selected_sources() == ("epic",)

            controller.select_all()
            assert controller.snapshot().selected_count == 3
            controller.clear_selection()
            assert controller.snapshot().selected_count == 0
        finally:
            controller.close()


def test_successful_async_scan_persists_and_refreshes_rows() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        store = LibraryStore(Path(tmp) / "library.sqlite3")
        controller = LibraryController(store)
        item = _item("one", "One")
        try:
            job = controller.scan_source(
                FakeAdapter(SourceScanResult("epic", (item,), ()))
            )
            assert controller.job_queue.wait_for_idle(timeout=5.0)
            events = controller.poll_events()

            assert job.state is JobState.SUCCEEDED
            terminal = [event for event in events if event.event.state is JobState.SUCCEEDED]
            assert len(terminal) == 1
            assert terminal[0].snapshot is not None
            assert [row.title for row in terminal[0].snapshot.rows] == ["One"]
            assert controller.snapshot().rows[0].item_id == item.stable_id
            assert job.result["snapshot"] == {
                "inserted": 1,
                "updated": 0,
                "marked_missing": 0,
            }
        finally:
            controller.close()


def test_partial_scan_routes_to_review_and_preserves_existing_rows() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        store = LibraryStore(Path(tmp) / "library.sqlite3")
        existing = _item("one", "One")
        store.replace_source_snapshot("epic", [existing])
        controller = LibraryController(store)
        partial = SourceScanResult(
            "epic",
            (),
            (
                SourceIssue(
                    source="epic",
                    code="manifest_directory_missing",
                    message="Epic is unavailable",
                    severity="info",
                ),
            ),
        )
        try:
            job = controller.scan_source(FakeAdapter(partial))
            assert controller.job_queue.wait_for_idle(timeout=5.0)
            events = controller.poll_events()

            assert job.state is JobState.NEEDS_REVIEW
            assert [row.title for row in controller.snapshot().rows] == ["One"]
            terminal = [
                event for event in events
                if event.event.state is JobState.NEEDS_REVIEW
            ]
            assert terminal and terminal[0].snapshot is not None
            assert terminal[0].event.result["persisted"] is False
        finally:
            controller.close()


def test_review_scan_can_be_retried_and_refreshes_rows() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        store = LibraryStore(Path(tmp) / "library.sqlite3")
        controller = LibraryController(store)
        partial = SourceScanResult(
            "epic",
            (),
            (
                SourceIssue(
                    source="epic",
                    code="manifest_directory_missing",
                    message="Epic is unavailable",
                    severity="info",
                ),
            ),
        )
        adapter = FakeAdapter(partial)
        item = _item("retry", "Retry")
        try:
            job = controller.scan_source(adapter)
            assert controller.job_queue.wait_for_idle(timeout=5.0)
            controller.poll_events()
            assert job.state is JobState.NEEDS_REVIEW

            adapter.result = SourceScanResult("epic", (item,), ())
            retried = controller.retry_scan(job.job_id)
            assert retried.state is JobState.QUEUED
            assert controller.job_queue.wait_for_idle(timeout=5.0)
            events = controller.poll_events()

            assert job.state is JobState.SUCCEEDED
            terminal = [event for event in events if event.event.state is JobState.SUCCEEDED]
            assert terminal and terminal[0].snapshot is not None
            assert [row.title for row in terminal[0].snapshot.rows] == ["Retry"]
        finally:
            controller.close()


def test_adapter_exception_becomes_isolated_failed_job() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        store = LibraryStore(Path(tmp) / "library.sqlite3")
        controller = LibraryController(store)
        try:
            job = controller.scan_source(
                FakeAdapter(error=RuntimeError("launcher unavailable"))
            )
            assert controller.job_queue.wait_for_idle(timeout=5.0)
            events = controller.poll_events()

            assert job.state is JobState.FAILED
            assert "launcher unavailable" in job.error
            assert any(event.event.state is JobState.FAILED for event in events)
            assert controller.snapshot().rows == ()
        finally:
            controller.close()


def test_artwork_job_results_persist_accepts_and_rejections() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        store = LibraryStore(Path(tmp) / "library.sqlite3")
        item = _item("art", "Art Game")
        store.replace_source_snapshot("epic", [item])
        controller = LibraryController(store)
        try:
            accepted = controller.persist_artwork_job_result(
                {
                    "item_id": item.stable_id,
                    "decision": "auto_accept",
                    "provider": "fixture",
                    "candidate_ids": {"grid": "grid-one", "logo": "logo-one"},
                    "details": {
                        "validated_files": {
                            "grid": {"path": str(Path(tmp) / "grid.png")},
                            "logo": {"path": str(Path(tmp) / "logo.png")},
                        }
                    },
                }
            )
            rejected = controller.persist_artwork_job_result(
                {
                    "item_id": item.stable_id,
                    "decision": "reject",
                    "provider": "fixture",
                    "candidate_ids": {"hero": "hero-one"},
                    "reasons": ["Wrong edition"],
                }
            )

            assert accepted.accepted == 2
            assert rejected.rejected == 1
            locks = {lock.slot: lock for lock in store.list_artwork_locks(item.stable_id)}
            assert locks["grid"].candidate_id == "grid-one"
            assert locks["grid"].source == "fixture"
            assert locks["grid"].local_path.endswith("grid.png")
            assert store.is_match_rejected(item.stable_id, "fixture", "hero", "hero-one")
            assert store.list_rejected_matches(item.stable_id)[0].reason == "Wrong edition"
            assert "grid" in controller.snapshot().rows[0].locked_slots
        finally:
            controller.close()


if __name__ == "__main__":
    test_controller_builds_immutable_effective_rows_and_selection()
    test_successful_async_scan_persists_and_refreshes_rows()
    test_partial_scan_routes_to_review_and_preserves_existing_rows()
    test_review_scan_can_be_retried_and_refreshes_rows()
    test_adapter_exception_becomes_isolated_failed_job()
    test_artwork_job_results_persist_accepts_and_rejections()
    print("Library controller tests passed.")
