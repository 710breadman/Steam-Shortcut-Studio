from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from prototypes.modern_library import format_size, load_library_games  # noqa: E402
from steam_shortcut_studio.library_store import (  # noqa: E402
    ArtworkLock,
    LibraryStore,
    ManualOverrides,
)
from steam_shortcut_studio.sources.base import SourceLibraryItem, stable_source_item_id  # noqa: E402


def _item(external_id: str, title: str, *, exists: bool = True) -> SourceLibraryItem:
    return SourceLibraryItem(
        stable_id=stable_source_item_id("epic", external_id=external_id),
        source="epic",
        external_id=external_id,
        title=title,
        install_path=rf"C:\Games\{title}",
        launch_target=rf"C:\Games\{title}\{title}.exe",
        platform="windows",
        size_bytes=5 * 1024 * 1024 * 1024,
        launch_target_exists=exists,
    )


def test_persistent_library_maps_to_modern_shell_rows() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        database = Path(tmp) / "library.sqlite3"
        store = LibraryStore(database)
        ready = _item("ready", "Ready Game")
        customized = _item("customized", "Source Title")
        review = _item("review", "Review Game", exists=False)
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

        games = load_library_games(database)
        by_title = {game.title: game for game in games}

        assert list(by_title) == ["My Custom Title", "Ready Game", "Review Game"]
        assert by_title["Ready Game"].source == "Epic"
        assert by_title["Ready Game"].platform == "Windows"
        assert by_title["Ready Game"].size == "5.0 GB"
        assert by_title["Ready Game"].status == "Ready"
        assert by_title["My Custom Title"].status == "Customized"
        assert by_title["Review Game"].status == "Review"


def test_missing_items_are_hidden_by_default_and_optional() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        database = Path(tmp) / "library.sqlite3"
        store = LibraryStore(database)
        present = _item("present", "Present")
        missing = _item("missing", "Missing")
        store.replace_source_snapshot("epic", [present, missing])
        store.replace_source_snapshot("epic", [present])

        visible = load_library_games(database)
        all_games = load_library_games(database, include_missing=True)

        assert [game.title for game in visible] == ["Present"]
        assert {game.title for game in all_games} == {"Present", "Missing"}
        missing_game = next(game for game in all_games if game.title == "Missing")
        assert missing_game.status == "Missing"


def test_size_formatting_is_stable() -> None:
    assert format_size(0) == "—"
    assert format_size(512) == "512 B"
    assert format_size(1024) == "1 KB"
    assert format_size(1536 * 1024) == "1.5 MB"


if __name__ == "__main__":
    test_persistent_library_maps_to_modern_shell_rows()
    test_missing_items_are_hidden_by_default_and_optional()
    test_size_formatting_is_stable()
    print("Persistent library prototype tests passed.")
