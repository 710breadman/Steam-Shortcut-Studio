from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from steam_shortcut_studio.library_controller import LibraryRow, LibrarySnapshot  # noqa: E402
from steam_shortcut_studio.ui_library_adapter import (  # noqa: E402
    LIBRARY_ITEM_ID_META,
    LIBRARY_PLATFORM_META,
    LIBRARY_SIZE_META,
    apply_library_selection_to_games,
    game_from_library_row,
    library_item_ids_between,
    library_item_ids_for_games,
    library_platform_for_game,
    library_size_for_game,
    library_source_for_game,
    library_status_for_game,
    games_from_library_snapshot,
    is_persistent_library_game,
    library_launch_target_for_game,
    source_scan_adapters,
    source_scan_event_summary,
    source_scan_progress_summary,
)


def _row(
    item_id: str,
    title: str,
    *,
    source: str = "folder",
    external_id: str = "",
    launch_target: str = r"C:\Games\Example\Example.exe",
) -> LibraryRow:
    return LibraryRow(
        item_id=item_id,
        title=title,
        source=source,
        external_id=external_id,
        platform="windows",
        install_path=rf"C:\Games\{title}",
        launch_target=launch_target,
        launch_arguments="-windowed",
        working_directory=rf"C:\Games\{title}",
        size_bytes=1024,
        version="",
        is_present=True,
        launch_target_exists=True,
        status="ready",
        overridden_fields=frozenset(),
        locked_slots=frozenset(),
    )


def test_library_row_maps_to_read_only_legacy_game() -> None:
    row = _row("folder:one", "Example Game")

    game = game_from_library_row(row, selected=True)

    assert game.display_title == "Example Game"
    assert game.source_type == "library"
    assert game.selected is True
    assert game.selected_exe is None
    assert not game.is_managed_non_steam
    assert game.metadata.extra[LIBRARY_ITEM_ID_META] == "folder:one"
    assert game.metadata.extra[LIBRARY_PLATFORM_META] == "windows"
    assert game.metadata.extra[LIBRARY_SIZE_META] == "1024"
    assert library_launch_target_for_game(game).endswith("Example.exe")
    assert library_source_for_game(game) == "Folder"
    assert library_platform_for_game(game) == "Windows"
    assert library_status_for_game(game) == "Ready"
    assert library_size_for_game(game) == "1 KB"
    assert is_persistent_library_game(game)


def test_native_steam_library_row_does_not_become_writable_native_game() -> None:
    row = _row(
        "steam:424242",
        "Native Example",
        source="steam",
        external_id="424242",
        launch_target="steam://rungameid/424242",
    )

    game = game_from_library_row(row)

    assert game.steam_appid == 424242
    assert game.source_type == "library"
    assert not game.is_native_steam_game
    assert not game.is_managed_non_steam


def test_snapshot_selection_is_preserved() -> None:
    first = _row("one", "One")
    second = _row("two", "Two")
    snapshot = LibrarySnapshot(
        rows=(first, second),
        active_item_id="two",
        selected_ids=frozenset({"two"}),
    )

    games = games_from_library_snapshot(snapshot)

    assert [game.display_title for game in games] == ["One", "Two"]
    assert [game.selected for game in games] == [False, True]


def test_source_scan_adapters_cover_controller_backed_sources() -> None:
    adapters = source_scan_adapters(
        steam_path=Path(r"C:\Steam"),
        collection_root=Path(r"D:\Games"),
    )

    assert [adapter.source_name for adapter in adapters] == ["epic", "steam", "folder"]

    selected = source_scan_adapters(
        steam_path=Path(r"C:\Steam"),
        collection_root=Path(r"D:\Games"),
        sources={"steam", "folder"},
    )

    assert [adapter.source_name for adapter in selected] == ["steam", "folder"]


def test_library_selection_helpers_use_stable_ids() -> None:
    first = game_from_library_row(_row("one", "One"))
    second = game_from_library_row(_row("two", "Two"))
    third = game_from_library_row(_row("three", "Three"))

    games = [first, second, third]
    assert library_item_ids_for_games(games, range(1)) == ("one",)
    assert library_item_ids_between(games, [0, 1, 2], "one", "three") == (
        "one",
        "two",
        "three",
    )
    assert library_item_ids_between(games, [2, 1, 0], "three", "one") == (
        "three",
        "two",
        "one",
    )

    apply_library_selection_to_games(games, frozenset({"two"}))

    assert [first.selected, second.selected, third.selected] == [False, True, False]


def test_source_scan_event_summary_surfaces_review_codes() -> None:
    summary = source_scan_event_summary(
        source="epic",
        state="needs_review",
        result={
            "detected_items": 0,
            "issue_count": 2,
            "issues": [
                {"code": "manifest_directory_missing"},
                {"code": "programdata_unavailable"},
            ],
        },
    )

    assert summary == "Epic scan needs review: 0 item(s), 2 issue(s) [manifest_directory_missing, programdata_unavailable]"


def test_source_scan_progress_summary_formats_sources() -> None:
    summary = source_scan_progress_summary(
        {
            "job-1": {"source": "epic", "state": "running", "progress": 0.25},
            "job-2": {"source": "folder", "state": "queued", "progress": 0},
        }
    )

    assert summary == "Source refresh: Epic running 25%; Folder queued 0%"


if __name__ == "__main__":
    test_library_row_maps_to_read_only_legacy_game()
    test_native_steam_library_row_does_not_become_writable_native_game()
    test_snapshot_selection_is_preserved()
    test_source_scan_adapters_cover_controller_backed_sources()
    test_library_selection_helpers_use_stable_ids()
    test_source_scan_event_summary_surfaces_review_codes()
    test_source_scan_progress_summary_formats_sources()
    print("UI library adapter tests passed.")
