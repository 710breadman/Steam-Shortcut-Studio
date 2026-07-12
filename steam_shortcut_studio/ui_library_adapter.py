from __future__ import annotations

from pathlib import Path

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
) -> tuple[SourceAdapter, ...]:
    adapters: list[SourceAdapter] = []
    if include_epic:
        adapters.append(EpicManifestAdapter())
    if steam_path:
        adapters.append(SteamLibraryAdapter(steam_path))
    if collection_root:
        adapters.append(FolderScannerAdapter(collection_root))
    return tuple(adapters)
