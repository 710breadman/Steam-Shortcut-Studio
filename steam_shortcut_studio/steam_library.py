from __future__ import annotations

import re
from pathlib import Path

from .models import DetectedGame, GameMetadata
from .steam_shortcuts import ShortcutRecord, unquote_path


def _parse_vdf_text(path: Path) -> dict[str, str]:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return {}
    values: dict[str, str] = {}
    for key, value in re.findall(r'"([^"]+)"\s+"([^"]*)"', text):
        values[key] = value.replace("\\\\", "\\")
    return values


def steam_library_roots(steam_path: Path) -> list[Path]:
    roots: list[Path] = []
    steamapps = steam_path / "steamapps"
    if steamapps.exists():
        roots.append(steamapps)
    libraryfolders = steamapps / "libraryfolders.vdf"
    try:
        text = libraryfolders.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return roots
    for match in re.finditer(r'"path"\s+"([^"]+)"', text):
        library_root = Path(match.group(1).replace("\\\\", "\\"))
        candidate = library_root / "steamapps"
        if candidate.exists() and candidate not in roots:
            roots.append(candidate)
    return roots


def scan_installed_steam_games(steam_path: Path) -> list[DetectedGame]:
    games: list[DetectedGame] = []
    for steamapps in steam_library_roots(steam_path):
        for manifest in steamapps.glob("appmanifest_*.acf"):
            values = _parse_vdf_text(manifest)
            appid_text = values.get("appid") or manifest.stem.removeprefix("appmanifest_")
            name = values.get("name") or f"Steam app {appid_text}"
            installdir = values.get("installdir") or ""
            try:
                appid = int(appid_text)
            except ValueError:
                continue
            install_path = steamapps / "common" / installdir if installdir else steamapps / "common" / name
            games.append(
                DetectedGame(
                    title=name,
                    root_path=install_path,
                    source_title=name,
                    selected=False,
                    metadata=GameMetadata(clean_title=name, steam_appid=appid, source="Steam library"),
                    source_type="steam",
                    source_note="Installed Steam game",
                    steam_appid=appid,
                )
            )
    games.sort(key=lambda game: game.display_title.casefold())
    return games


def games_from_nonsteam_shortcuts(records: list[ShortcutRecord]) -> list[DetectedGame]:
    games: list[DetectedGame] = []
    for record in records:
        exe_text = unquote_path(record.exe)
        exe_path = Path(exe_text) if exe_text else None
        root_path = exe_path.parent if exe_path else Path(unquote_path(record.start_dir) or ".")
        extra = {"Existing shortcut AppID": str(record.appid)}
        if record.launch_options:
            extra["Launch options"] = record.launch_options
        if record.icon:
            extra["Shortcut icon"] = record.icon
        games.append(
            DetectedGame(
                title=record.app_name,
                root_path=root_path,
                source_title=record.app_name,
                selected_exe=exe_path,
                selected=False,
                launch_options=record.launch_options,
                metadata=GameMetadata(clean_title=record.app_name, genres=list(record.tags), source="Steam shortcuts.vdf", extra=extra),
                existing_appid=record.appid,
                existing_match="shortcut",
                duplicate_action="update",
                source_type="shortcut",
                source_note="Existing non-Steam shortcut",
            )
        )
    games.sort(key=lambda game: game.display_title.casefold())
    return games
