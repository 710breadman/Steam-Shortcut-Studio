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
