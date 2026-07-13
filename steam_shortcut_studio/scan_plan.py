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


def combined_scan_initial_message() -> str:
    return "Scanning Steam and folders..."


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
