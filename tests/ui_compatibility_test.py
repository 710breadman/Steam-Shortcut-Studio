from __future__ import annotations

import logging
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import steam_shortcut_studio.ui as ui_module  # noqa: E402
from steam_shortcut_studio.models import DetectedGame  # noqa: E402
from steam_shortcut_studio.ui import MainWindow  # noqa: E402


def _make_window() -> tuple[MainWindow, list[tuple[object, ...]]]:
    window = object.__new__(MainWindow)
    events: list[tuple[object, ...]] = []
    window.logger = logging.getLogger("SteamShortcutStudioCompatibilityTest")
    window.status_var = SimpleNamespace(set=lambda value: events.append(("status", value)))
    window.steam_path_var = SimpleNamespace(get=lambda: r"C:\Steam")
    window.collection_path_var = SimpleNamespace(get=lambda: r"D:\Games")
    window.raise_if_cancelled = lambda: None
    window.save_current_detail = lambda: events.append(("save_current_detail",))
    window.save_settings_from_ui = lambda log=False: events.append(("save_settings", log))
    window.current_profile = lambda: None
    window.merge_game_lists = lambda existing, incoming: list(existing) + list(incoming)
    window.displayed_game_indices = [0]
    window.current_game_index = None
    window.refresh_game_table = lambda select_index=None: events.append(("refresh", select_index))
    window.load_game_detail = lambda index: events.append(("detail", index))
    window.prefetch_artwork_for_games = lambda games, reason="scan": events.append(("prefetch", [game.title for game in games], reason))
    window.replace_live_scan_games = lambda games, status="", select_index=None: events.append(("replace", [game.title for game in games], status, select_index))
    window.add_live_scan_game = lambda game: events.append(("add", game.title))
    window.set_task_progress = lambda message, value=None, maximum=None: events.append(("progress", message, value, maximum))
    window.run_background = lambda label, task, done, exclusive=False, show_error=True: (events.append(("background", label)), done(task()))
    return window, events


def test_scan_wrappers_still_delegate_through_legacy_main_window() -> None:
    window, events = _make_window()
    old_combined = ui_module.run_combined_scan
    old_folder = ui_module.run_folder_scan
    old_steam = ui_module.run_steam_scan
    old_build_combined = ui_module.build_combined_scan_plan
    old_build_folder = ui_module.build_folder_scan_plan
    old_build_steam = ui_module.build_steam_scan_plan
    try:
        ui_module.build_combined_scan_plan = lambda *_args, **_kwargs: SimpleNamespace(
            has_work=True,
            steam_ready=True,
            folder_ready=True,
            steam_path=Path(r"C:\Steam"),
            collection_root=Path(r"D:\Games"),
            total_steps=5,
        )
        ui_module.build_folder_scan_plan = lambda *_args, **_kwargs: SimpleNamespace(
            has_work=True,
            collection_root=Path(r"D:\Games"),
        )
        ui_module.build_steam_scan_plan = lambda *_args, **_kwargs: SimpleNamespace(
            has_path=True,
            steam_ready=True,
            steam_path=Path(r"C:\Steam"),
        )
        ui_module.run_combined_scan = lambda *args, **kwargs: ([DetectedGame(title="Combined", root_path=Path())], 2, 1, 3)
        ui_module.run_folder_scan = lambda *args, **kwargs: [DetectedGame(title="Folder", root_path=Path())]
        ui_module.run_steam_scan = lambda *args, **kwargs: [DetectedGame(title="Steam", root_path=Path(), source_type="steam", steam_appid=123)]

        MainWindow.scan_all_libraries(window)
        MainWindow.scan_games(window)
        MainWindow.scan_steam_games(window)
    finally:
        ui_module.build_combined_scan_plan = old_build_combined
        ui_module.build_folder_scan_plan = old_build_folder
        ui_module.build_steam_scan_plan = old_build_steam
        ui_module.run_combined_scan = old_combined
        ui_module.run_folder_scan = old_folder
        ui_module.run_steam_scan = old_steam

    assert ("background", "Scanning Steam and folders") in events
    assert ("background", "Scanning games") in events
    assert ("background", "Scanning Steam library") in events
    assert ("replace", [], "Scanning Steam and folders...", None) in events
    assert ("replace", [], "Scanning games...", None) in events
    assert ("refresh", 1) in events
    assert ("detail", 0) in events
    assert ("status", "Scanned 2 Steam, 1 existing shortcut, and 3 folder game(s).") in events
    assert ("status", "Scanned 1 game folder(s).") in events
    assert ("status", "Added 1 Steam library item(s) to the list.") in events
    assert ("prefetch", ["Combined"], "combined scan") in events
    assert ("prefetch", ["Folder"], "folder scan") in events
    assert ("prefetch", ["Steam"], "Steam library scan") in events


if __name__ == "__main__":
    test_scan_wrappers_still_delegate_through_legacy_main_window()
    print("UI compatibility tests passed.")
