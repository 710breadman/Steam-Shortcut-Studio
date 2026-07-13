from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class CombinedScanPlan:
    steam_path: Path | None
    collection_root: Path | None
    steam_ready: bool
    folder_ready: bool

    @property
    def has_work(self) -> bool:
        return self.steam_ready or self.folder_ready

    @property
    def total_steps(self) -> int:
        return (2 if self.steam_ready else 0) + (2 if self.folder_ready else 0) + 1


@dataclass(frozen=True, slots=True)
class CombinedScanCounts:
    steam: int = 0
    shortcuts: int = 0
    folders: int = 0


@dataclass(frozen=True, slots=True)
class FolderScanPlan:
    collection_root: Path | None

    @property
    def has_work(self) -> bool:
        return self.collection_root is not None


@dataclass(frozen=True, slots=True)
class SteamScanPlan:
    steam_path: Path | None
    steam_ready: bool

    @property
    def has_path(self) -> bool:
        return self.steam_path is not None


def combined_scan_initial_message() -> str:
    return "Scanning Steam and folders..."


def combined_scan_missing_sources_message() -> str:
    return "Choose a valid Steam folder, a game collection folder, or both before scanning."


def combined_scan_steam_start_message() -> str:
    return "Reading Steam shelves and installed-game manifests..."


def combined_scan_steam_found_message(steam_count: int) -> str:
    return f"Found {steam_count} installed Steam game(s); checking existing shortcuts and art..."


def combined_scan_folder_start_message() -> str:
    return "Opening the folder shelves and ranking executables..."


def combined_scan_folder_cross_check_message(folder_count: int) -> str:
    return f"Cross-checking {folder_count} folder game(s) with Steam shortcuts and existing art..."


def combined_scan_ready_message(counts: CombinedScanCounts) -> str:
    return f"Scan ready: {counts.steam} Steam, {counts.shortcuts} existing shortcut, {counts.folders} folder game(s)."


def combined_scan_done_message(counts: CombinedScanCounts) -> str:
    return f"Scanned {counts.steam} Steam, {counts.shortcuts} existing shortcut, and {counts.folders} folder game(s)."


def folder_scan_initial_message() -> str:
    return "Scanning games..."


def folder_scan_missing_source_message() -> str:
    return "Choose a game collection folder first."


def folder_scan_start_message() -> str:
    return "Opening the folder shelves..."


def folder_scan_cross_check_message(folder_count: int) -> str:
    return f"Cross-checking {folder_count} folder game(s) with Steam shortcuts..."


def folder_scan_ready_message(folder_count: int) -> str:
    return f"Folder scan ready: {folder_count} game(s) found."


def folder_scan_done_message(folder_count: int) -> str:
    return f"Scanned {folder_count} game folder(s)."


def steam_scan_start_message() -> str:
    return "Reading Steam's installed game shelves..."


def steam_scan_missing_path_message() -> str:
    return "Detect or choose your Steam folder first."


def steam_scan_invalid_path_message() -> str:
    return "The Steam folder does not look valid yet."


def steam_scan_found_message(steam_count: int) -> str:
    return f"Found {steam_count} installed Steam game(s); checking shortcuts and existing art..."


def steam_scan_live_found_message(steam_count: int) -> str:
    return f"Found {steam_count} installed Steam game(s)."


def steam_scan_ready_message() -> str:
    return "Steam library scan ready for artwork editing."


def steam_scan_done_message(added_count: int) -> str:
    return f"Added {added_count} Steam library item(s) to the list."


def build_folder_scan_plan(collection_root_text: str) -> FolderScanPlan:
    collection_root = Path(collection_root_text.strip()) if collection_root_text.strip() else None
    return FolderScanPlan(collection_root=collection_root)


def build_steam_scan_plan(
    steam_text: str,
    *,
    is_valid_steam_path: Callable[[Path], bool],
) -> SteamScanPlan:
    steam_path = Path(steam_text.strip()) if steam_text.strip() else None
    return SteamScanPlan(
        steam_path=steam_path,
        steam_ready=bool(steam_path and is_valid_steam_path(steam_path)),
    )


def build_combined_scan_plan(
    steam_text: str,
    collection_root_text: str,
    *,
    is_valid_steam_path: Callable[[Path], bool],
) -> CombinedScanPlan:
    steam_path = Path(steam_text.strip()) if steam_text.strip() else None
    collection_root = Path(collection_root_text.strip()) if collection_root_text.strip() else None
    steam_ready = bool(steam_path and is_valid_steam_path(steam_path))
    folder_ready = bool(collection_root and collection_root.exists())
    return CombinedScanPlan(
        steam_path=steam_path,
        collection_root=collection_root,
        steam_ready=steam_ready,
        folder_ready=folder_ready,
    )
