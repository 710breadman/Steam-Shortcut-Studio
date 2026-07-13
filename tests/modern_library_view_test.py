from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from steam_shortcut_studio.library_store import ArtworkLock, LibraryStore, ManualOverrides  # noqa: E402
from steam_shortcut_studio.models import ArtworkAsset, ArtworkSelection, DetectedGame, GameMetadata  # noqa: E402
from steam_shortcut_studio.modern_library_view import (  # noqa: E402
    format_size,
    game_matches_view_filter,
    load_modern_library_rows,
    modern_library_row_for_game,
    view_filter_status_message,
    visible_library_indices,
)
from steam_shortcut_studio.sources.base import SourceLibraryItem, stable_source_item_id  # noqa: E402
from steam_shortcut_studio.ui_library_adapter import (  # noqa: E402
    LIBRARY_ITEM_ID_META,
    LIBRARY_LAUNCH_TARGET_META,
    LIBRARY_PLATFORM_META,
    LIBRARY_SIZE_META,
    LIBRARY_SOURCE_META,
    LIBRARY_STATUS_META,
)


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


def test_persistent_library_maps_to_modern_library_rows() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        database = Path(tmp) / "library.sqlite3"
        store = LibraryStore(database)
        ready = _item("ready", "Ready Game")
        customized = _item("customized", "Source Title")
        review = _item("review", "Review Game", exists=False)
        store.replace_source_snapshot("epic", [ready, customized, review])
        store.save_overrides(ManualOverrides(item_id=customized.stable_id, display_title="My Custom Title"))
        store.set_artwork_lock(ArtworkLock(item_id=customized.stable_id, slot="grid"))

        rows = load_modern_library_rows(database)
        by_title = {row.title: row for row in rows}

        assert list(by_title) == ["My Custom Title", "Ready Game", "Review Game"]
        assert by_title["Ready Game"].source == "Epic"
        assert by_title["Ready Game"].platform == "Windows"
        assert by_title["Ready Game"].last_played == "\u2014"
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

        visible = load_modern_library_rows(database)
        all_rows = load_modern_library_rows(database, include_missing=True)

        assert [row.title for row in visible] == ["Present"]
        assert {row.title for row in all_rows} == {"Present", "Missing"}
        missing_row = next(row for row in all_rows if row.title == "Missing")
        assert missing_row.status == "Missing"


def test_size_formatting_is_stable() -> None:
    assert format_size(0) == "\u2014"
    assert format_size(512) == "512 B"
    assert format_size(1024) == "1 KB"
    assert format_size(1536 * 1024) == "1.5 MB"


def test_modern_library_row_for_game_matches_production_table_fields() -> None:
    game = DetectedGame(
        title="Ready Game",
        root_path=Path(r"C:\Games\Ready Game"),
        metadata=GameMetadata(
            clean_title="Ready Game",
            extra={
                LIBRARY_ITEM_ID_META: "item-ready",
                LIBRARY_SOURCE_META: "epic",
                LIBRARY_STATUS_META: "ready",
                LIBRARY_LAUNCH_TARGET_META: r"C:\Games\Ready Game\Ready Game.exe",
                LIBRARY_PLATFORM_META: "windows",
                LIBRARY_SIZE_META: str(5 * 1024 * 1024 * 1024),
            },
        ),
        source_type="library",
    )

    row = modern_library_row_for_game(game)

    assert row.item_id == "item-ready"
    assert row.title == "Ready Game"
    assert row.source == "Epic"
    assert row.platform == "Windows"
    assert row.platform_size_label == "Windows / 5.0 GB"
    assert row.status == "Ready"


def test_view_filter_model_matches_production_table_filters() -> None:
    complete_art = ArtworkSelection(
        grid=ArtworkAsset(kind="grid", asset_id="grid", url=""),
        wide=ArtworkAsset(kind="wide", asset_id="wide", url=""),
        hero=ArtworkAsset(kind="hero", asset_id="hero", url=""),
        logo=ArtworkAsset(kind="logo", asset_id="logo", url=""),
        icon=ArtworkAsset(kind="icon", asset_id="icon", url=""),
    )
    checked = DetectedGame(title="Checked", root_path=Path(r"C:\Games\Checked"), selected=True)
    existing = DetectedGame(title="Existing", root_path=Path(r"C:\Games\Existing"), existing_appid=123)
    steam = DetectedGame(title="Steam", root_path=Path(), source_type="steam", steam_appid=456)
    stored_review = DetectedGame(
        title="Review",
        root_path=Path(),
        metadata=GameMetadata(
            extra={
                LIBRARY_ITEM_ID_META: "item-review",
                LIBRARY_STATUS_META: "review",
                LIBRARY_SOURCE_META: "epic",
            }
        ),
        source_type="library",
    )
    ready_art = DetectedGame(title="Ready Art", root_path=Path(r"C:\Games\Ready Art"), artwork=complete_art)
    games = [checked, existing, steam, stored_review, ready_art]

    assert game_matches_view_filter(checked, "Checked") is True
    assert game_matches_view_filter(existing, "Existing non-Steam") is True
    assert game_matches_view_filter(steam, "Installed Steam") is True
    assert game_matches_view_filter(stored_review, "Stored Library") is True
    assert game_matches_view_filter(stored_review, "Needs review") is True
    assert game_matches_view_filter(ready_art, "Needs artwork") is False
    assert visible_library_indices(games, "New non-Steam") == [0, 3, 4]
    assert visible_library_indices(games, "Needs review") == [3]
    assert view_filter_status_message(2, 5) == "Showing 2/5 game row(s)."


if __name__ == "__main__":
    test_persistent_library_maps_to_modern_library_rows()
    test_missing_items_are_hidden_by_default_and_optional()
    test_size_formatting_is_stable()
    test_modern_library_row_for_game_matches_production_table_fields()
    test_view_filter_model_matches_production_table_filters()
    print("Modern library view tests passed.")
