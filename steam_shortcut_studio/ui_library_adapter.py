from __future__ import annotations

from pathlib import Path

from .library_controller import LibraryRow, LibrarySnapshot
from .models import DetectedGame, GameMetadata


LIBRARY_ITEM_ID_META = "library_item_id"
LIBRARY_SOURCE_META = "library_source"
LIBRARY_STATUS_META = "library_status"
LIBRARY_LAUNCH_TARGET_META = "library_launch_target"


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
