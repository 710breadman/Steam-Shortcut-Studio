from __future__ import annotations

import os
from pathlib import Path
from typing import Callable

from ..models import DetectedGame
from ..steam_library import scan_installed_steam_games
from .base import (
    SourceIssue,
    SourceLibraryItem,
    SourceScanResult,
    stable_source_item_id,
)


STEAM_SOURCE = "steam"
SteamScanFunction = Callable[[Path], list[DetectedGame]]


class SteamLibraryAdapter:
    """Normalize installed native Steam games into persistent library records."""

    source_name = STEAM_SOURCE

    def __init__(
        self,
        steam_root: Path | str,
        *,
        scan_function: SteamScanFunction = scan_installed_steam_games,
    ) -> None:
        self.steam_root = Path(steam_root).expanduser()
        self.scan_function = scan_function

    def scan(self) -> SourceScanResult:
        if not self.steam_root.is_dir():
            return SourceScanResult(
                source=self.source_name,
                issues=(
                    SourceIssue(
                        source=self.source_name,
                        code="steam_root_missing",
                        message="Steam installation folder does not exist.",
                        record_path=str(self.steam_root),
                        severity="info",
                    ),
                ),
            )

        try:
            games = self.scan_function(self.steam_root)
        except Exception as exc:
            return SourceScanResult(
                source=self.source_name,
                issues=(
                    SourceIssue(
                        source=self.source_name,
                        code="steam_scan_failed",
                        message=f"Steam library scan failed: {type(exc).__name__}: {exc}",
                        record_path=str(self.steam_root),
                        severity="error",
                    ),
                ),
            )

        items: list[SourceLibraryItem] = []
        issues: list[SourceIssue] = []
        seen_appids: set[int] = set()
        platform = "windows" if os.name == "nt" else "linux"

        for game in games:
            appid = int(game.steam_appid or 0)
            if appid <= 0:
                issues.append(
                    SourceIssue(
                        source=self.source_name,
                        code="missing_steam_appid",
                        message="Installed Steam game has no valid AppID and was skipped.",
                        record_path=str(game.root_path),
                        severity="error",
                    )
                )
                continue
            if appid in seen_appids:
                issues.append(
                    SourceIssue(
                        source=self.source_name,
                        code="duplicate_steam_appid",
                        message="Multiple Steam installations resolved to the same AppID.",
                        record_path=str(game.root_path),
                        item_external_id=str(appid),
                    )
                )
                continue
            seen_appids.add(appid)

            install_path = str(game.root_path)
            install_exists: bool | None
            try:
                install_exists = game.root_path.is_dir()
            except OSError:
                install_exists = False
            if install_exists is False:
                issues.append(
                    SourceIssue(
                        source=self.source_name,
                        code="steam_install_path_missing",
                        message="Steam manifest references an install folder that does not exist.",
                        record_path=install_path,
                        item_external_id=str(appid),
                    )
                )

            stable_id = stable_source_item_id(
                self.source_name,
                external_id=str(appid),
            )
            title = game.display_title or game.title or f"Steam App {appid}"
            items.append(
                SourceLibraryItem(
                    stable_id=stable_id,
                    source=self.source_name,
                    external_id=str(appid),
                    title=title,
                    install_path=install_path,
                    launch_target=f"steam://rungameid/{appid}",
                    working_directory=install_path,
                    platform=platform,
                    source_record_path=str(
                        self.steam_root / "steamapps" / f"appmanifest_{appid}.acf"
                    ),
                    launch_target_exists=install_exists,
                    evidence=(
                        "Steam appmanifest",
                        "Steam AppID",
                        "Steam install directory",
                    ),
                    metadata={
                        "steam_appid": appid,
                        "source_type": game.source_type,
                        "source_title": game.source_title,
                        "is_native_steam_game": game.is_native_steam_game,
                    },
                )
            )

        items.sort(key=lambda item: (item.title.casefold(), item.external_id))
        return SourceScanResult(self.source_name, tuple(items), tuple(issues))
