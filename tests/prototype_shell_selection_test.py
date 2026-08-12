from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from steam_shortcut_studio.library_controller import LibraryController  # noqa: E402
from steam_shortcut_studio.library_store import LibraryStore  # noqa: E402
from steam_shortcut_studio.modern_library_view import initial_active_item_id  # noqa: E402
from steam_shortcut_studio.selection import SelectionState  # noqa: E402
from steam_shortcut_studio.sources.base import SourceLibraryItem, stable_source_item_id  # noqa: E402


def _item(external_id: str, title: str) -> SourceLibraryItem:
    return SourceLibraryItem(
        stable_id=stable_source_item_id("epic", external_id=external_id),
        source="epic",
        external_id=external_id,
        title=title,
        install_path=rf"C:\Games\{title}",
        launch_target=rf"C:\Games\{title}\{title}.exe",
        platform="windows",
        size_bytes=1024,
        launch_target_exists=True,
    )


def test_initial_active_item_id_picks_first_row() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        store = LibraryStore(Path(tmp) / "library.sqlite3")
        store.replace_source_snapshot("epic", [_item("one", "One"), _item("two", "Two")])
        controller = LibraryController(store)
        controller.refresh()
        snapshot = controller.snapshot()

        assert snapshot.active_item_id is None
        assert initial_active_item_id(snapshot.rows, snapshot.active_item_id) == snapshot.rows[0].item_id


def test_initial_active_item_id_keeps_an_existing_active_row() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        store = LibraryStore(Path(tmp) / "library.sqlite3")
        store.replace_source_snapshot("epic", [_item("one", "One"), _item("two", "Two")])
        controller = LibraryController(store)
        controller.refresh()
        second = controller.snapshot().rows[1].item_id
        snapshot = controller.set_active(second)

        assert isinstance(controller.selection, SelectionState)
        assert initial_active_item_id(snapshot.rows, snapshot.active_item_id) == second


def test_initial_active_item_id_handles_empty_library() -> None:
    assert initial_active_item_id((), None) is None
    assert initial_active_item_id((), "stale-id") is None


if __name__ == "__main__":
    test_initial_active_item_id_picks_first_row()
    test_initial_active_item_id_keeps_an_existing_active_row()
    test_initial_active_item_id_handles_empty_library()
    print("Prototype shell selection tests passed.")
