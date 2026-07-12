from __future__ import annotations

import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from steam_shortcut_studio.library_store import LibraryStore  # noqa: E402
from steam_shortcut_studio.source_scans import (  # noqa: E402
    SourceScanCoordinator,
    source_scan_is_authoritative,
)
from steam_shortcut_studio.sources.base import (  # noqa: E402
    SourceIssue,
    SourceLibraryItem,
    SourceScanResult,
    stable_source_item_id,
)


def _item(external_id: str, title: str) -> SourceLibraryItem:
    return SourceLibraryItem(
        stable_id=stable_source_item_id("epic", external_id=external_id),
        source="epic",
        external_id=external_id,
        title=title,
        install_path=rf"C:\Games\{title}",
        launch_target=rf"C:\Games\{title}\{title}.exe",
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


def test_complete_scan_persists_and_later_marks_missing() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        store = LibraryStore(Path(tmp) / "library.sqlite3")
        coordinator = SourceScanCoordinator(store)
        first = _item("one", "One")
        second = _item("two", "Two")

        initial = coordinator.run(
            FakeAdapter(SourceScanResult("epic", (first, second), ()))
        )
        removed = coordinator.run(FakeAdapter(SourceScanResult("epic", (first,), ())))

        assert initial.succeeded and initial.persisted and initial.authoritative
        assert initial.snapshot is not None
        assert initial.snapshot.inserted == 2
        assert removed.succeeded
        assert removed.snapshot is not None
        assert removed.snapshot.updated == 1
        assert removed.snapshot.marked_missing == 1
        assert [record.title for record in store.list_records(source="epic")] == ["One"]
        all_records = store.list_records(source="epic", include_missing=True)
        assert next(record for record in all_records if record.title == "Two").is_present is False
        assert [run.status for run in store.list_scan_runs(source="epic")] == [
            "completed",
            "completed",
        ]


def test_partial_error_scan_never_marks_existing_items_missing() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        store = LibraryStore(Path(tmp) / "library.sqlite3")
        coordinator = SourceScanCoordinator(store)
        item = _item("one", "One")
        coordinator.run(FakeAdapter(SourceScanResult("epic", (item,), ())))

        partial = SourceScanResult(
            "epic",
            (),
            (
                SourceIssue(
                    source="epic",
                    code="invalid_manifest_json",
                    message="Broken manifest",
                    severity="error",
                ),
            ),
        )
        execution = coordinator.run(FakeAdapter(partial))

        assert execution.succeeded is False
        assert execution.persisted is False
        assert execution.authoritative is False
        record = store.get_record(item.stable_id)
        assert record is not None and record.is_present is True
        latest = store.list_scan_runs(source="epic")[0]
        assert latest.status == "failed"
        assert "partial" in latest.error.casefold()


def test_missing_source_directory_never_clears_a_snapshot() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        store = LibraryStore(Path(tmp) / "library.sqlite3")
        coordinator = SourceScanCoordinator(store)
        item = _item("one", "One")
        coordinator.run(FakeAdapter(SourceScanResult("epic", (item,), ())))

        unavailable = SourceScanResult(
            "epic",
            (),
            (
                SourceIssue(
                    source="epic",
                    code="manifest_directory_missing",
                    message="Not installed",
                    severity="info",
                ),
            ),
        )
        execution = coordinator.run(FakeAdapter(unavailable))

        assert execution.authoritative is False
        assert store.get_record(item.stable_id).is_present is True  # type: ignore[union-attr]


def test_review_warnings_still_allow_an_authoritative_snapshot() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        store = LibraryStore(Path(tmp) / "library.sqlite3")
        item = _item("one", "One")
        result = SourceScanResult(
            "epic",
            (item,),
            (
                SourceIssue(
                    source="epic",
                    code="missing_launch_executable",
                    message="Manual selection required",
                    severity="warning",
                ),
            ),
        )

        assert source_scan_is_authoritative(result) is True
        execution = SourceScanCoordinator(store).run(FakeAdapter(result))
        assert execution.succeeded and execution.persisted
        assert store.get_record(item.stable_id) is not None


def test_adapter_exception_and_source_mismatch_are_recorded_without_persistence() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        store = LibraryStore(Path(tmp) / "library.sqlite3")
        coordinator = SourceScanCoordinator(store)

        crashed = coordinator.run(FakeAdapter(error=RuntimeError("boom")))
        mismatch = coordinator.run(
            FakeAdapter(SourceScanResult("gog", (_item("one", "One"),), ()))
        )

        assert crashed.status == "failed"
        assert crashed.result.issues[0].code == "adapter_exception"
        assert "boom" in crashed.error
        assert mismatch.status == "failed"
        assert "mismatch" in mismatch.error.casefold()
        assert store.list_records(include_missing=True) == []
        assert [run.status for run in store.list_scan_runs(source="epic")] == [
            "failed",
            "failed",
        ]


if __name__ == "__main__":
    test_complete_scan_persists_and_later_marks_missing()
    test_partial_error_scan_never_marks_existing_items_missing()
    test_missing_source_directory_never_clears_a_snapshot()
    test_review_warnings_still_allow_an_authoritative_snapshot()
    test_adapter_exception_and_source_mismatch_are_recorded_without_persistence()
    print("Source scan persistence tests passed.")
