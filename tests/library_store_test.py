from __future__ import annotations

import sqlite3
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from steam_shortcut_studio.library_store import (  # noqa: E402
    ArtworkLock,
    LibraryStore,
    ManualOverrides,
    RejectedMatch,
    SCHEMA_VERSION,
)
from steam_shortcut_studio.sources.base import SourceLibraryItem, stable_source_item_id  # noqa: E402


def _item(
    external_id: str,
    title: str,
    *,
    launch_target: str = r"C:\Games\Example\Example.exe",
) -> SourceLibraryItem:
    install_path = rf"C:\Games\{title}"
    return SourceLibraryItem(
        stable_id=stable_source_item_id("epic", external_id=external_id),
        source="epic",
        external_id=external_id,
        title=title,
        install_path=install_path,
        launch_target=launch_target,
        launch_arguments="-windowed",
        working_directory=str(Path(launch_target).parent),
        platform="windows",
        version="1.0",
        size_bytes=1234,
        source_record_path=rf"C:\ProgramData\Epic\{external_id}.item",
        launch_target_exists=True,
        evidence=("Epic manifest", "Catalog ID"),
        metadata={"nested": {"value": 1}, "tags": ["en"]},
    )


def test_snapshot_persists_and_reopens() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        database = Path(tmp) / "library.sqlite3"
        store = LibraryStore(database)
        first = _item("namespace:item-1", "Example One")
        second = _item("namespace:item-2", "Example Two")
        scan_id = store.start_scan("epic")

        result = store.replace_source_snapshot("epic", [first, second], scan_id=scan_id)
        store.finish_scan(scan_id, item_count=2, issue_count=1)

        assert result.inserted == 2
        assert result.updated == 0
        assert result.marked_missing == 0
        assert [record.title for record in store.list_records(source="epic")] == [
            "Example One",
            "Example Two",
        ]

        reopened = LibraryStore(database)
        record = reopened.get_record(first.stable_id)
        assert record is not None
        assert record.external_id == "namespace:item-1"
        assert record.evidence == ("Epic manifest", "Catalog ID")
        assert record.metadata["nested"] == {"value": 1}
        runs = reopened.list_scan_runs(source="epic")
        assert len(runs) == 1
        assert runs[0].status == "completed"
        assert runs[0].item_count == 2
        assert runs[0].issue_count == 1


def test_rescan_preserves_manual_overrides_locks_and_rejections() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        database = Path(tmp) / "library.sqlite3"
        store = LibraryStore(database)
        original = _item("namespace:item", "Original Title")
        store.replace_source_snapshot("epic", [original])

        store.save_overrides(
            ManualOverrides(
                item_id=original.stable_id,
                display_title="My Preferred Title",
                launch_target=r"D:\Overrides\Preferred.exe",
                notes="Keep this personal note.",
            )
        )
        store.set_artwork_lock(
            ArtworkLock(
                item_id=original.stable_id,
                slot="grid",
                candidate_id="manual-grid",
                source="local",
                local_path=r"D:\Art\grid.png",
            )
        )
        store.reject_match(
            RejectedMatch(
                item_id=original.stable_id,
                provider="steamgriddb",
                slot="hero",
                candidate_id="wrong-edition",
                reason="Wrong edition",
            )
        )

        refreshed = _item(
            "namespace:item",
            "Launcher Renamed Title",
            launch_target=r"C:\Games\Renamed\NewLauncher.exe",
        )
        result = store.replace_source_snapshot("epic", [refreshed])

        assert result.inserted == 0
        assert result.updated == 1
        resolved = store.resolve_item(original.stable_id)
        assert resolved is not None
        assert resolved.record.title == "Launcher Renamed Title"
        assert resolved.record.launch_target.endswith("NewLauncher.exe")
        assert resolved.display_title == "My Preferred Title"
        assert resolved.launch_target == r"D:\Overrides\Preferred.exe"
        assert resolved.notes == "Keep this personal note."
        assert resolved.overridden_fields == frozenset(
            {"display_title", "launch_target", "notes"}
        )
        locks = store.list_artwork_locks(original.stable_id)
        assert len(locks) == 1
        assert locks[0].candidate_id == "manual-grid"
        assert store.is_match_rejected(
            original.stable_id,
            "steamgriddb",
            "hero",
            "wrong-edition",
        )

        reopened = LibraryStore(database)
        reopened_resolved = reopened.resolve_item(original.stable_id)
        assert reopened_resolved is not None
        assert reopened_resolved.display_title == "My Preferred Title"
        assert reopened.list_artwork_locks(original.stable_id)[0].slot == "grid"
        assert reopened.list_rejected_matches(original.stable_id)[0].reason == "Wrong edition"


def test_snapshot_marks_missing_without_deleting_manual_state() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        store = LibraryStore(Path(tmp) / "library.sqlite3")
        first = _item("namespace:first", "First")
        second = _item("namespace:second", "Second")
        store.replace_source_snapshot("epic", [first, second])
        store.save_overrides(
            ManualOverrides(item_id=second.stable_id, display_title="Second Custom")
        )

        result = store.replace_source_snapshot("epic", [first])

        assert result.marked_missing == 1
        assert [record.stable_id for record in store.list_records(source="epic")] == [
            first.stable_id
        ]
        all_records = store.list_records(source="epic", include_missing=True)
        missing = next(record for record in all_records if record.stable_id == second.stable_id)
        assert missing.is_present is False
        resolved = store.resolve_item(second.stable_id)
        assert resolved is not None
        assert resolved.display_title == "Second Custom"

        restored = store.replace_source_snapshot("epic", [first, second])
        assert restored.updated == 2
        assert store.get_record(second.stable_id).is_present is True  # type: ignore[union-attr]
        assert store.resolve_item(second.stable_id).display_title == "Second Custom"  # type: ignore[union-attr]


def test_overrides_and_artwork_decisions_can_be_cleared() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        store = LibraryStore(Path(tmp) / "library.sqlite3")
        item = _item("namespace:item", "Example")
        store.replace_source_snapshot("epic", [item])
        store.save_overrides(ManualOverrides(item_id=item.stable_id, display_title="Custom"))
        store.set_artwork_lock(ArtworkLock(item_id=item.stable_id, slot="logo"))
        rejection = RejectedMatch(
            item_id=item.stable_id,
            provider="fixture",
            slot="logo",
            candidate_id="candidate",
        )
        store.reject_match(rejection)

        assert store.clear_overrides(item.stable_id)
        assert store.clear_artwork_lock(item.stable_id, "logo")
        assert store.clear_rejected_match(
            item.stable_id,
            "fixture",
            "logo",
            "candidate",
        )
        assert store.get_overrides(item.stable_id) is None
        assert store.list_artwork_locks(item.stable_id) == []
        assert store.list_rejected_matches(item.stable_id) == []
        assert store.resolve_item(item.stable_id).display_title == "Example"  # type: ignore[union-attr]


def test_unknown_items_and_future_schemas_fail_safely() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        database = Path(tmp) / "library.sqlite3"
        store = LibraryStore(database)
        try:
            store.save_overrides(ManualOverrides(item_id="missing", display_title="No"))
        except KeyError:
            pass
        else:
            raise AssertionError("Unknown item override was accepted")

        future = Path(tmp) / "future.sqlite3"
        connection = sqlite3.connect(future)
        connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION + 1}")
        connection.close()
        try:
            LibraryStore(future)
        except RuntimeError as exc:
            assert "newer than supported" in str(exc)
        else:
            raise AssertionError("Future library schema was opened without an error")


if __name__ == "__main__":
    test_snapshot_persists_and_reopens()
    test_rescan_preserves_manual_overrides_locks_and_rejections()
    test_snapshot_marks_missing_without_deleting_manual_state()
    test_overrides_and_artwork_decisions_can_be_cleared()
    test_unknown_items_and_future_schemas_fail_safely()
    print("Library store tests passed.")
