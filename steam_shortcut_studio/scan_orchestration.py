from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from .artwork import load_existing_artwork_for_games
from .game_merge import compare_games_with_shortcuts, merge_detected_game_lists
from .models import DetectedGame, SteamProfile
from .scanner import GameScanner
from .steam_library import scan_installed_steam_games
from .steam_shortcuts import load_shortcuts
from .scan_plan import (
    CombinedScanPlan,
    FolderScanPlan,
    SteamScanPlan,
    combined_scan_folder_cross_check_message,
    combined_scan_folder_start_message,
    combined_scan_ready_message,
    combined_scan_steam_found_message,
    combined_scan_steam_start_message,
    folder_scan_cross_check_message,
    folder_scan_ready_message,
    folder_scan_start_message,
    steam_scan_found_message,
    steam_scan_ready_message,
    steam_scan_start_message,
    CombinedScanCounts,
)


def run_combined_scan(
    plan: CombinedScanPlan,
    profile: SteamProfile | None,
    logger: Any,
    set_task_progress: Callable[[str, int | None, int | None], None],
    raise_if_cancelled: Callable[[], None],
    replace_live_scan_games: Callable[[list[DetectedGame], str], None],
    add_live_scan_game: Callable[[DetectedGame], None],
) -> tuple[list[DetectedGame], int, int, int]:
    games: list[DetectedGame] = []
    steam_count = 0
    shortcut_count = 0
    folder_count = 0
    total_steps = plan.total_steps
    step = 0
    records = None
    if plan.steam_ready and plan.steam_path is not None:
        set_task_progress(combined_scan_steam_start_message(), step, total_steps)
        raise_if_cancelled()
        steam_games = scan_installed_steam_games(plan.steam_path)
        steam_count = len(steam_games)
        step += 1
        set_task_progress(combined_scan_steam_found_message(steam_count), step, total_steps)
        if profile:
            try:
                records = load_shortcuts(profile.shortcuts_path)
                comparison = compare_games_with_shortcuts(steam_games, records, include_nonsteam_games=True)
                steam_games = comparison.games
                shortcut_count = comparison.shortcut_count
                loaded = load_existing_artwork_for_games(steam_games, profile)
                if loaded:
                    logger.info("Loaded %s existing Steam artwork file(s) while scanning Steam.", loaded)
            except Exception as exc:
                logger.warning("Could not read existing shortcuts/artwork while scanning Steam: %s", exc)
        games = merge_detected_game_lists(games, steam_games)
        replace_live_scan_games(list(games), steam_scan_found_message(steam_count))

    if plan.folder_ready and plan.collection_root is not None:
        set_task_progress(combined_scan_folder_start_message(), step, total_steps)
        scanner = GameScanner(
            logger,
            cancel_check=raise_if_cancelled,
            progress_callback=lambda message: set_task_progress(message),
            game_callback=add_live_scan_game,
        )
        folder_games = scanner.scan(plan.collection_root)
        folder_count = len(folder_games)
        raise_if_cancelled()
        step += 1
        set_task_progress(combined_scan_folder_cross_check_message(folder_count), step, total_steps)
        if profile:
            try:
                if records is None:
                    records = load_shortcuts(profile.shortcuts_path)
                folder_games = compare_games_with_shortcuts(folder_games, records).games
                loaded = load_existing_artwork_for_games(folder_games, profile)
                if loaded:
                    logger.info("Loaded %s existing Steam artwork file(s) for folder games.", loaded)
            except Exception as exc:
                logger.warning("Could not read existing shortcuts for folder duplicate detection: %s", exc)
        games = merge_detected_game_lists(games, folder_games)
        step += 1

    counts = CombinedScanCounts(steam=steam_count, shortcuts=shortcut_count, folders=folder_count)
    set_task_progress(combined_scan_ready_message(counts), total_steps, total_steps)
    return games, steam_count, shortcut_count, folder_count


def run_folder_scan(
    plan: FolderScanPlan,
    profile: SteamProfile | None,
    logger: Any,
    set_task_progress: Callable[[str, int | None, int | None], None],
    raise_if_cancelled: Callable[[], None],
    add_live_scan_game: Callable[[DetectedGame], None],
) -> list[DetectedGame]:
    assert plan.collection_root is not None
    set_task_progress(folder_scan_start_message(), 0, 2)
    scanner = GameScanner(
        logger,
        cancel_check=raise_if_cancelled,
        progress_callback=lambda message: set_task_progress(message),
        game_callback=add_live_scan_game,
    )
    games = scanner.scan(plan.collection_root)
    raise_if_cancelled()
    set_task_progress(folder_scan_cross_check_message(len(games)), 1, 2)
    if profile:
        try:
            records = load_shortcuts(profile.shortcuts_path)
            games = compare_games_with_shortcuts(games, records).games
            loaded = load_existing_artwork_for_games(games, profile)
            if loaded:
                logger.info("Loaded %s existing Steam artwork file(s) for folder games.", loaded)
        except Exception as exc:
            logger.warning("Could not read existing shortcuts for duplicate detection: %s", exc)
    set_task_progress(folder_scan_ready_message(len(games)), 2, 2)
    return games


def run_steam_scan(
    plan: SteamScanPlan,
    profile: SteamProfile | None,
    logger: Any,
    set_task_progress: Callable[[str, int | None, int | None], None],
    raise_if_cancelled: Callable[[], None],
    replace_live_scan_games: Callable[[list[DetectedGame], str], None],
) -> list[DetectedGame]:
    assert plan.steam_path is not None
    set_task_progress(steam_scan_start_message(), 0, 3)
    raise_if_cancelled()
    games = scan_installed_steam_games(plan.steam_path)
    replace_live_scan_games(list(games), steam_scan_found_message(len(games)))
    raise_if_cancelled()
    set_task_progress(steam_scan_found_message(len(games)), 1, 3)
    if profile:
        try:
            records = load_shortcuts(profile.shortcuts_path)
            games = compare_games_with_shortcuts(games, records, include_nonsteam_games=True).games
            loaded = load_existing_artwork_for_games(games, profile)
            if loaded:
                logger.info("Loaded %s existing Steam artwork file(s) while scanning Steam library.", loaded)
        except Exception as exc:
            logger.warning("Could not read existing shortcuts for Steam library comparison: %s", exc)
    set_task_progress(steam_scan_ready_message(), 3, 3)
    return games
