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

# Steam installs runtimes and compatibility tools into steamapps alongside real
# games, so a plain manifest scan picks them up as library entries. They have no
# launch target a person would ever use and no artwork worth matching -- one of
# them ("Steamworks Common Redistributables", 228980) was reaching the artwork
# pipeline and being scored like a game.
STEAM_RUNTIME_APPIDS: frozenset[int] = frozenset({
    228980,   # Steamworks Common Redistributables
    1070560,  # Steam Linux Runtime 1.0 (scout)
    1391110,  # Steam Linux Runtime 2.0 (soldier)
    1628350,  # Steam Linux Runtime 3.0 (sniper)
    1493710,  # Proton Experimental
    1161040,  # Proton BattlEye Runtime
    1826330,  # Proton EasyAntiCheat Runtime
})

# Proton builds are published as a new AppID per release, so an ID list would go
# stale. Their manifests are consistently named, unlike real games.
STEAM_RUNTIME_TITLE_PREFIXES: tuple[str, ...] = (
    "proton ",
    "steam linux runtime",
    "steamworks common",
)


def is_steam_runtime_app(appid: int, title: str) -> bool:
    """True when an installed Steam entry is a runtime or tool, not a game."""
    if appid in STEAM_RUNTIME_APPIDS:
        return True
    name = " ".join(str(title or "").split()).casefold()
    return any(name.startswith(prefix) for prefix in STEAM_RUNTIME_TITLE_PREFIXES)


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
            title_text = game.display_title or game.title or ""
            if is_steam_runtime_app(appid, title_text):
                issues.append(
                    SourceIssue(
                        source=self.source_name,
                        code="steam_runtime_app_skipped",
                        message="Installed Steam entry is a runtime or compatibility tool, not a game.",
                        record_path=str(game.root_path),
                        item_external_id=str(appid),
                        severity="info",
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
                    size_bytes=game.size_bytes,
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
