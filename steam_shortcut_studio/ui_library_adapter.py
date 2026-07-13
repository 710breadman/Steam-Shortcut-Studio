from __future__ import annotations

from pathlib import Path
from typing import Mapping

from .library_controller import LibraryRow, LibrarySnapshot
from .models import DetectedGame, GameMetadata
from .sources.base import SourceAdapter
from .sources.epic import EpicManifestAdapter
from .sources.local import FolderScannerAdapter
from .sources.steam import SteamLibraryAdapter


LIBRARY_ITEM_ID_META = "library_item_id"
LIBRARY_SOURCE_META = "library_source"
LIBRARY_STATUS_META = "library_status"
LIBRARY_LAUNCH_TARGET_META = "library_launch_target"
LIBRARY_PLATFORM_META = "library_platform"
LIBRARY_SIZE_META = "library_size_bytes"


def library_item_id_for_game(game: DetectedGame) -> str:
    return str(game.metadata.extra.get(LIBRARY_ITEM_ID_META) or "")


def is_persistent_library_game(game: DetectedGame) -> bool:
    return bool(library_item_id_for_game(game))


def library_launch_target_for_game(game: DetectedGame) -> str:
    return str(game.metadata.extra.get(LIBRARY_LAUNCH_TARGET_META) or "")


def _steam_appid(row: LibraryRow) -> int | None:
    if row.source.casefold() != "steam" or not row.external_id.isdigit():
        return None
    return int(row.external_id)


def game_from_library_row(row: LibraryRow, *, selected: bool = False) -> DetectedGame:
    steam_appid = _steam_appid(row)
    metadata = GameMetadata(
        clean_title=row.title,
        title_locked=True,
        extra={
            LIBRARY_ITEM_ID_META: row.item_id,
            LIBRARY_SOURCE_META: row.source,
            LIBRARY_STATUS_META: row.status,
            LIBRARY_LAUNCH_TARGET_META: row.launch_target,
            LIBRARY_PLATFORM_META: row.platform,
            LIBRARY_SIZE_META: str(row.size_bytes),
        },
    )
    game = DetectedGame(
        title=row.title,
        root_path=Path(row.install_path) if row.install_path else Path(),
        source_title=row.title,
        selected=False,
        launch_options=row.launch_arguments,
        metadata=metadata,
        selected_exe=None,
        source_type="library",
        source_note=f"Persistent library: {row.source} / {row.status}",
        steam_appid=steam_appid,
    )
    game.selected = selected
    return game


def games_from_library_snapshot(snapshot: LibrarySnapshot) -> list[DetectedGame]:
    selected_ids = snapshot.selected_ids
    return [
        game_from_library_row(row, selected=row.item_id in selected_ids)
        for row in snapshot.rows
    ]


def library_item_ids_for_games(
    games: list[DetectedGame],
    indices: list[int] | range | None = None,
) -> tuple[str, ...]:
    selected_indices = indices if indices is not None else range(len(games))
    ids: list[str] = []
    for index in selected_indices:
        if 0 <= index < len(games):
            item_id = library_item_id_for_game(games[index])
            if item_id:
                ids.append(item_id)
    return tuple(ids)


def library_games_by_item_id(games: list[DetectedGame]) -> dict[str, DetectedGame]:
    return {
        item_id: game
        for game in games
        if (item_id := library_item_id_for_game(game))
    }


def selected_visible_library_item_ids(
    games: list[DetectedGame],
    displayed_indices: list[int],
    selected_ids: frozenset[str] | set[str],
) -> tuple[str, ...]:
    visible = library_item_ids_for_games(games, displayed_indices)
    selected = set(selected_ids)
    return tuple(item_id for item_id in visible if item_id in selected)


def library_item_ids_between(
    games: list[DetectedGame],
    ordered_indices: list[int],
    anchor_id: str,
    target_id: str,
) -> tuple[str, ...]:
    positions: dict[str, int] = {}
    ids: list[str] = []
    for position, index in enumerate(ordered_indices):
        if 0 <= index < len(games):
            item_id = library_item_id_for_game(games[index])
            if item_id:
                positions.setdefault(item_id, position)
                ids.append(item_id)
    if anchor_id not in positions or target_id not in positions:
        return (target_id,) if target_id else ()
    start = min(positions[anchor_id], positions[target_id])
    end = max(positions[anchor_id], positions[target_id])
    return tuple(ids[start : end + 1])


def apply_library_selection_to_games(
    games: list[DetectedGame],
    selected_ids: frozenset[str],
) -> None:
    for game in games:
        item_id = library_item_id_for_game(game)
        if item_id:
            game.selected = item_id in selected_ids


def source_scan_event_summary(
    *,
    source: str,
    state: str,
    result: Mapping[str, object],
    error: str = "",
) -> str:
    label = display_label(source, fallback="Source")
    detail = f"{label} scan {state.replace('_', ' ')}"
    detected = result.get("detected_items")
    issue_count = result.get("issue_count")
    if detected is not None:
        detail += f": {detected} item(s)"
    try:
        issue_total = int(issue_count or 0)
    except (TypeError, ValueError):
        issue_total = 0
    issues = result.get("issues")
    codes: list[str] = []
    if isinstance(issues, list):
        for issue in issues:
            if isinstance(issue, dict):
                code = str(issue.get("code") or "").strip()
                if code and code not in codes:
                    codes.append(code)
    if issue_total:
        detail += f", {issue_total} issue(s)"
    if codes:
        shown = ", ".join(codes[:3])
        if len(codes) > 3:
            shown += ", ..."
        detail += f" [{shown}]"
    if error:
        detail += f" - {error}"
    return detail


def source_scan_progress_summary(progress: Mapping[str, Mapping[str, object]]) -> str:
    entries: list[str] = []
    for item in progress.values():
        source = display_label(str(item.get("source") or ""), fallback="Source")
        state = str(item.get("state") or "queued").replace("_", " ")
        try:
            percent = int(round(float(item.get("progress") or 0.0) * 100))
        except (TypeError, ValueError):
            percent = 0
        percent = max(0, min(100, percent))
        entries.append(f"{source} {state} {percent}%")
    return "Source refresh: " + "; ".join(entries) if entries else "Source refresh: idle"


def format_library_size(size_bytes: int) -> str:
    value = max(0, int(size_bytes))
    if value == 0:
        return ""
    units = ("B", "KB", "MB", "GB", "TB")
    amount = float(value)
    unit = units[0]
    for candidate in units:
        unit = candidate
        if amount < 1024.0 or candidate == units[-1]:
            break
        amount /= 1024.0
    precision = 0 if unit in {"B", "KB"} else 1
    return f"{amount:.{precision}f} {unit}"


def display_label(value: str, *, fallback: str = "") -> str:
    text = str(value or "").replace("_", " ").strip()
    return text.title() if text else fallback


def library_source_for_game(game: DetectedGame) -> str:
    return display_label(str(game.metadata.extra.get(LIBRARY_SOURCE_META) or ""), fallback="Library")


def library_status_for_game(game: DetectedGame) -> str:
    return display_label(str(game.metadata.extra.get(LIBRARY_STATUS_META) or ""), fallback="Stored")


def library_platform_for_game(game: DetectedGame) -> str:
    return display_label(str(game.metadata.extra.get(LIBRARY_PLATFORM_META) or ""), fallback="PC")


def library_size_for_game(game: DetectedGame) -> str:
    try:
        return format_library_size(int(game.metadata.extra.get(LIBRARY_SIZE_META) or "0"))
    except ValueError:
        return ""


def source_scan_adapters(
    *,
    steam_path: Path | str | None = None,
    collection_root: Path | str | None = None,
    include_epic: bool = True,
    sources: set[str] | frozenset[str] | None = None,
) -> tuple[SourceAdapter, ...]:
    allowed = {source.casefold() for source in sources} if sources is not None else None

    def enabled(source_name: str) -> bool:
        return allowed is None or source_name.casefold() in allowed

    adapters: list[SourceAdapter] = []
    if include_epic and enabled("epic"):
        adapters.append(EpicManifestAdapter())
    if steam_path and enabled("steam"):
        adapters.append(SteamLibraryAdapter(steam_path))
    if collection_root and enabled("folder"):
        adapters.append(FolderScannerAdapter(collection_root))
    return tuple(adapters)
