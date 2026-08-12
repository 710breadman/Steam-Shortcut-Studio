from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from steam_shortcut_studio.library_controller import LibraryRow, LibrarySnapshot  # noqa: E402
from steam_shortcut_studio.library_store import ArtworkLock  # noqa: E402
from steam_shortcut_studio.steam_shortcuts import generate_appid, shortcut_from_game  # noqa: E402
from steam_shortcut_studio.ui_library_adapter import (  # noqa: E402
    LIBRARY_ITEM_ID_META,
    LIBRARY_PLATFORM_META,
    LIBRARY_SIZE_META,
    apply_library_selection_to_games,
    apply_locked_artwork,
    artwork_copy_skip_reason,
    build_library_display_update,
    game_from_library_row,
    library_item_ids_between,
    library_item_ids_for_games,
    library_games_by_item_id,
    library_platform_for_game,
    native_steam_artwork_game_from_library_row,
    persistent_library_notes_text,
    persistent_library_reason_text,
    library_size_for_game,
    library_source_for_game,
    library_status_for_game,
    games_from_library_snapshot,
    is_persistent_library_game,
    library_loaded_status,
    library_launch_target_for_game,
    selected_visible_library_item_ids,
    selected_visible_library_games,
    source_scan_adapters,
    source_scan_event_summary,
    source_scan_progress_summary,
    writable_game_from_library_row,
    writable_game_skip_reason,
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
    assert persistent_library_notes_text(game) == (
        "Persistent Folder library row - Ready.\n\n"
        "This legacy view is read-only for stored library rows. "
        "Use source scans to refresh library data; Steam writes remain disabled for these rows."
    )
    assert persistent_library_reason_text(game) == (
        "Persistent library row.\n"
        "Source: folder\n"
        "Status: ready\n"
        r"Install folder: C:\Games\Example Game"
        "\n"
        r"Launch target: C:\Games\Example\Example.exe"
        "\n"
        "Read-only in the legacy view; no Steam writes are enabled for this row."
    )


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


def test_writable_game_from_library_row_accepts_an_existing_launch_target() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        exe_path = Path(tmp) / "Example.exe"
        exe_path.write_bytes(b"MZ")
        row = _row("folder:one", "Example Game", launch_target=str(exe_path))

        assert writable_game_skip_reason(row) == ""
        game = writable_game_from_library_row(row)

        assert game is not None
        assert game.selected is True
        assert game.selected_exe == exe_path
        assert game.steam_appid is None
        assert game.is_native_steam_game is False
        assert game.is_managed_non_steam is True


def test_writable_game_from_library_row_rejects_native_steam_rows() -> None:
    row = _row(
        "steam:424242",
        "Native Example",
        source="steam",
        external_id="424242",
        launch_target="steam://rungameid/424242",
    )

    assert writable_game_skip_reason(row) == "native Steam game (already known to Steam)"
    assert writable_game_from_library_row(row) is None


def test_writable_game_from_library_row_rejects_empty_launch_target() -> None:
    row = _row("folder:two", "No Target", launch_target="")

    assert writable_game_skip_reason(row) == "no launch target set"
    assert writable_game_from_library_row(row) is None


def test_writable_game_from_library_row_rejects_missing_launch_target() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        missing_path = Path(tmp) / "Ghost.exe"
        row = _row("folder:three", "Missing Target", launch_target=str(missing_path))

        assert writable_game_skip_reason(row) == "launch target missing on disk"
        assert writable_game_from_library_row(row) is None


def test_artwork_copy_skip_reason_requires_a_lock_with_an_existing_file() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        exe_path = Path(tmp) / "Game.exe"
        exe_path.write_bytes(b"MZ")
        row = _row("folder:art1", "Art Game", launch_target=str(exe_path))
        assert artwork_copy_skip_reason(row, []) == "no artwork locked"

        stale_lock = ArtworkLock(item_id=row.item_id, slot="grid", local_path=str(Path(tmp) / "gone.png"))
        assert artwork_copy_skip_reason(row, [stale_lock]) == "no artwork locked"

        real_file = Path(tmp) / "real.png"
        real_file.write_bytes(b"fake-png-bytes")
        good_lock = ArtworkLock(item_id=row.item_id, slot="grid", local_path=str(real_file))
        assert artwork_copy_skip_reason(row, [good_lock]) == ""


def test_artwork_copy_skip_reason_native_steam_appid() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        real_file = Path(tmp) / "real.png"
        real_file.write_bytes(b"fake-png-bytes")
        good_lock = ArtworkLock(item_id="steam:x", slot="grid", local_path=str(real_file))

        valid_row = _row("steam:424242", "Native Example", source="steam", external_id="424242")
        assert artwork_copy_skip_reason(valid_row, [good_lock]) == ""

        bad_appid_row = _row("steam:bad", "Bad AppID", source="steam", external_id="not-a-number")
        assert artwork_copy_skip_reason(bad_appid_row, [good_lock]) == "native Steam appid missing"


def test_artwork_copy_skip_reason_reuses_shortcut_rules_for_non_steam_rows() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        real_file = Path(tmp) / "real.png"
        real_file.write_bytes(b"fake-png-bytes")
        good_lock = ArtworkLock(item_id="folder:x", slot="grid", local_path=str(real_file))

        row = _row("folder:noexe", "No Exe", launch_target="")
        assert artwork_copy_skip_reason(row, [good_lock]) == "no launch target set"


def test_native_steam_artwork_game_from_library_row_is_artwork_eligible() -> None:
    row = _row("steam:424242", "Native Example", source="steam", external_id="424242")

    game = native_steam_artwork_game_from_library_row(row)

    assert game is not None
    assert game.selected is True
    assert game.steam_appid == 424242
    assert game.is_native_steam_game is True
    assert game.is_managed_non_steam is False

    assert native_steam_artwork_game_from_library_row(_row("folder:one", "Folder Game")) is None
    assert native_steam_artwork_game_from_library_row(
        _row("steam:bad", "Bad AppID", source="steam", external_id="nope")
    ) is None


def test_apply_locked_artwork_populates_selection_and_skips_stale_files() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        grid_file = Path(tmp) / "grid.png"
        grid_file.write_bytes(b"fake-png-bytes")
        missing_file = Path(tmp) / "missing.png"

        game = native_steam_artwork_game_from_library_row(
            _row("steam:424242", "Native Example", source="steam", external_id="424242")
        )
        assert game is not None

        locks = [
            ArtworkLock(item_id=game.metadata.extra[LIBRARY_ITEM_ID_META], slot="grid",
                        candidate_id="c1", source="steamgriddb", local_path=str(grid_file)),
            ArtworkLock(item_id=game.metadata.extra[LIBRARY_ITEM_ID_META], slot="hero",
                        candidate_id="c2", source="steamgriddb", local_path=str(missing_file)),
        ]
        apply_locked_artwork(game, locks)

        assert game.artwork.grid is not None
        assert game.artwork.grid.local_path == grid_file
        assert game.artwork.grid.asset_id == "c1"
        assert game.artwork.hero is None, "a lock whose file no longer exists must not be applied"


def test_artwork_copy_uses_the_same_appid_as_the_shortcut_write() -> None:
    """Artwork and its shortcut must land under the identical computed AppID,
    or Steam won't associate the grid image with the non-Steam shortcut entry."""
    with tempfile.TemporaryDirectory() as tmp:
        exe_path = Path(tmp) / "Game.exe"
        exe_path.write_bytes(b"MZ")
        grid_file = Path(tmp) / "grid.png"
        grid_file.write_bytes(b"fake-png-bytes")
        row = _row("folder:appid", "AppID Consistency", launch_target=str(exe_path))

        shortcut_game = writable_game_from_library_row(row)
        assert shortcut_game is not None
        expected_appid = shortcut_from_game(shortcut_game).appid

        artwork_game = writable_game_from_library_row(row)
        assert artwork_game is not None
        apply_locked_artwork(
            artwork_game,
            [ArtworkLock(item_id=row.item_id, slot="grid", candidate_id="c1", local_path=str(grid_file))],
        )
        actual_appid = generate_appid(artwork_game.selected_exe.resolve(), artwork_game.display_title)
        assert actual_appid == expected_appid


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


def test_library_display_update_contains_games_and_status() -> None:
    snapshot = LibrarySnapshot(
        rows=(_row("one", "One"), _row("two", "Two")),
        active_item_id=None,
        selected_ids=frozenset({"one"}),
    )

    update = build_library_display_update(snapshot)

    assert [game.display_title for game in update.games] == ["One", "Two"]
    assert [game.selected for game in update.games] == [True, False]
    assert update.status == "Loaded 2 stored library item(s)."
    assert library_loaded_status(0) == "Loaded 0 stored library item(s)."


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


def test_library_games_by_item_id_ignores_nonpersistent_rows() -> None:
    first = game_from_library_row(_row("one", "One"))
    second = game_from_library_row(_row("two", "Two"))
    loose = _row("loose", "Loose")
    loose_game = game_from_library_row(loose)
    loose_game.metadata.extra.pop(LIBRARY_ITEM_ID_META)

    by_id = library_games_by_item_id([first, loose_game, second])

    assert list(by_id) == ["one", "two"]
    assert by_id["one"] is first
    assert by_id["two"] is second


def test_selected_visible_library_item_ids_intersects_display_and_selection_order() -> None:
    first = game_from_library_row(_row("one", "One"))
    second = game_from_library_row(_row("two", "Two"))
    third = game_from_library_row(_row("three", "Three"))

    assert selected_visible_library_item_ids(
        [first, second, third],
        [2, 0],
        frozenset({"one", "two", "three"}),
    ) == ("three", "one")


def test_selected_visible_library_games_follow_display_order() -> None:
    first = game_from_library_row(_row("one", "One"))
    second = game_from_library_row(_row("two", "Two"))
    third = game_from_library_row(_row("three", "Three"))

    assert [game.display_title for game in selected_visible_library_games(
        [first, second, third],
        [2, 0],
        frozenset({"one", "three"}),
    )] == ["Three", "One"]


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
    test_writable_game_from_library_row_accepts_an_existing_launch_target()
    test_writable_game_from_library_row_rejects_native_steam_rows()
    test_writable_game_from_library_row_rejects_empty_launch_target()
    test_writable_game_from_library_row_rejects_missing_launch_target()
    test_artwork_copy_skip_reason_requires_a_lock_with_an_existing_file()
    test_artwork_copy_skip_reason_native_steam_appid()
    test_artwork_copy_skip_reason_reuses_shortcut_rules_for_non_steam_rows()
    test_native_steam_artwork_game_from_library_row_is_artwork_eligible()
    test_apply_locked_artwork_populates_selection_and_skips_stale_files()
    test_artwork_copy_uses_the_same_appid_as_the_shortcut_write()
    test_snapshot_selection_is_preserved()
    test_library_display_update_contains_games_and_status()
    test_source_scan_adapters_cover_controller_backed_sources()
    test_library_selection_helpers_use_stable_ids()
    test_library_games_by_item_id_ignores_nonpersistent_rows()
    test_selected_visible_library_item_ids_intersects_display_and_selection_order()
    test_source_scan_event_summary_surfaces_review_codes()
    test_source_scan_progress_summary_formats_sources()
    print("UI library adapter tests passed.")
