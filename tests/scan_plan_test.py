from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from steam_shortcut_studio.scan_plan import (  # noqa: E402
    CombinedScanCounts,
    build_combined_scan_plan,
    build_folder_scan_plan,
    build_steam_scan_plan,
    combined_scan_done_message,
    combined_scan_folder_cross_check_message,
    combined_scan_folder_start_message,
    combined_scan_initial_message,
    combined_scan_missing_sources_message,
    combined_scan_ready_message,
    combined_scan_steam_found_message,
    combined_scan_steam_start_message,
    folder_scan_cross_check_message,
    folder_scan_done_message,
    folder_scan_initial_message,
    folder_scan_missing_source_message,
    folder_scan_ready_message,
    folder_scan_start_message,
    steam_scan_done_message,
    steam_scan_found_message,
    steam_scan_invalid_path_message,
    steam_scan_live_found_message,
    steam_scan_missing_path_message,
    steam_scan_ready_message,
    steam_scan_start_message,
)


def test_combined_scan_plan_counts_enabled_sources() -> None:
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        plan = build_combined_scan_plan(
            r"C:\Steam",
            str(root),
            is_valid_steam_path=lambda path: str(path) == r"C:\Steam",
        )

    assert plan.has_work is True
    assert plan.steam_ready is True
    assert plan.folder_ready is True
    assert plan.total_steps == 5


def test_combined_scan_plan_rejects_missing_sources() -> None:
    plan = build_combined_scan_plan(
        "",
        r"Z:\missing-games",
        is_valid_steam_path=lambda _path: False,
    )

    assert plan.has_work is False
    assert plan.steam_path is None
    assert plan.folder_ready is False
    assert plan.total_steps == 1


def test_combined_scan_messages_match_scan_counts() -> None:
    counts = CombinedScanCounts(steam=2, shortcuts=3, folders=4)

    assert combined_scan_initial_message() == "Scanning Steam and folders..."
    assert combined_scan_missing_sources_message() == "Choose a valid Steam folder, a game collection folder, or both before scanning."
    assert combined_scan_steam_start_message() == "Reading Steam shelves and installed-game manifests..."
    assert combined_scan_steam_found_message(2) == "Found 2 installed Steam game(s); checking existing shortcuts and art..."
    assert combined_scan_folder_start_message() == "Opening the folder shelves and ranking executables..."
    assert combined_scan_folder_cross_check_message(4) == "Cross-checking 4 folder game(s) with Steam shortcuts and existing art..."
    assert combined_scan_ready_message(counts) == "Scan ready: 2 Steam, 3 existing shortcut, 4 folder game(s)."
    assert combined_scan_done_message(counts) == "Scanned 2 Steam, 3 existing shortcut, and 4 folder game(s)."


def test_folder_scan_plan_and_messages() -> None:
    plan = build_folder_scan_plan(r"D:\Games")

    assert plan.has_work is True
    assert str(plan.collection_root) == r"D:\Games"
    assert build_folder_scan_plan("").has_work is False
    assert folder_scan_initial_message() == "Scanning games..."
    assert folder_scan_missing_source_message() == "Choose a game collection folder first."
    assert folder_scan_start_message() == "Opening the folder shelves..."
    assert folder_scan_cross_check_message(6) == "Cross-checking 6 folder game(s) with Steam shortcuts..."
    assert folder_scan_ready_message(6) == "Folder scan ready: 6 game(s) found."
    assert folder_scan_done_message(6) == "Scanned 6 game folder(s)."


def test_steam_scan_plan_and_messages() -> None:
    plan = build_steam_scan_plan(
        r"C:\Steam",
        is_valid_steam_path=lambda path: str(path) == r"C:\Steam",
    )
    invalid = build_steam_scan_plan(
        r"C:\BadSteam",
        is_valid_steam_path=lambda _path: False,
    )

    assert plan.has_path is True
    assert plan.steam_ready is True
    assert invalid.has_path is True
    assert invalid.steam_ready is False
    assert build_steam_scan_plan("", is_valid_steam_path=lambda _path: False).has_path is False
    assert steam_scan_missing_path_message() == "Detect or choose your Steam folder first."
    assert steam_scan_invalid_path_message() == "The Steam folder does not look valid yet."
    assert steam_scan_start_message() == "Reading Steam's installed game shelves..."
    assert steam_scan_found_message(9) == "Found 9 installed Steam game(s); checking shortcuts and existing art..."
    assert steam_scan_live_found_message(9) == "Found 9 installed Steam game(s)."
    assert steam_scan_ready_message() == "Steam library scan ready for artwork editing."
    assert steam_scan_done_message(4) == "Added 4 Steam library item(s) to the list."


if __name__ == "__main__":
    test_combined_scan_plan_counts_enabled_sources()
    test_combined_scan_plan_rejects_missing_sources()
    test_combined_scan_messages_match_scan_counts()
    test_folder_scan_plan_and_messages()
    test_steam_scan_plan_and_messages()
    print("Combined scan plan tests passed.")
