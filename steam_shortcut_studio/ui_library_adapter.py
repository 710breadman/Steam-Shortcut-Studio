from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping

from .library_controller import LibraryRow, LibrarySnapshot
from .library_store import ArtworkLock
from .models import ArtworkAsset, DetectedGame, GameMetadata
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


@dataclass(frozen=True, slots=True)
class LibraryDisplayUpdate:
    games: tuple[DetectedGame, ...]
    status: str


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


def writable_game_skip_reason(row: LibraryRow) -> str:
    """Return why `row` cannot produce a Steam shortcut, or "" if it can.

    Native Steam rows are already known to Steam and need no shortcut entry.
    Everything else needs a launch target that actually resolves to a file
    right now (checked live, not cached) before it is safe to write.
    """
    if row.source.casefold() == "steam":
        return "native Steam game (already known to Steam)"
    if not row.launch_target.strip():
        return "no launch target set"
    if not Path(row.launch_target).is_file():
        return "launch target missing on disk"
    return ""


def writable_game_from_library_row(row: LibraryRow) -> DetectedGame | None:
    """Build a real, write-eligible `DetectedGame` for the Apply Changes flow.

    Unlike `game_from_library_row` (always `selected_exe=None`; the legacy
    UI's read-only Persistent Library display bridge), this is the write-path
    counterpart used to actually stage a Steam shortcut. Returns None for
    anything `writable_game_skip_reason` flags as ineligible.
    """
    if writable_game_skip_reason(row):
        return None
    exe_path = Path(row.launch_target)
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
    return DetectedGame(
        title=row.title,
        root_path=Path(row.install_path) if row.install_path else exe_path.parent,
        source_title=row.title,
        selected=True,
        launch_options=row.launch_arguments,
        metadata=metadata,
        selected_exe=exe_path,
        source_type="library",
        source_note=f"Persistent library: {row.source} / {row.status}",
        steam_appid=None,
    )


def artwork_copy_skip_reason(row: LibraryRow, locks: list[ArtworkLock]) -> str:
    """Return why `row` has nothing to copy into Steam's grid folder, or "" if it does.

    A lock only counts if its cached file still exists on disk right now —
    a cache that was cleared since the slot was matched must not silently
    attempt a copy of a file that is no longer there.
    """
    valid_locks = [lock for lock in locks if lock.local_path and Path(lock.local_path).is_file()]
    if not valid_locks:
        return "no artwork locked"
    if row.source.casefold() == "steam":
        return "native Steam appid missing" if _steam_appid(row) is None else ""
    return writable_game_skip_reason(row)


def native_steam_artwork_game_from_library_row(row: LibraryRow) -> DetectedGame | None:
    """Build a `DetectedGame` eligible for an artwork-only copy to Steam.

    `writable_game_from_library_row` correctly excludes native Steam rows
    (they never need a shortcut entry). This is the artwork-purpose
    counterpart for that same row: sets `source_type="steam"` so
    `DetectedGame.is_native_steam_game` is True, which is what
    `copy_all_artwork_to_steam` checks for eligibility instead of
    `is_managed_non_steam`. Returns None for non-Steam rows or an
    unparseable AppID.
    """
    steam_appid = _steam_appid(row)
    if row.source.casefold() != "steam" or steam_appid is None:
        return None
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
    return DetectedGame(
        title=row.title,
        root_path=Path(row.install_path) if row.install_path else Path(),
        source_title=row.title,
        selected=True,
        metadata=metadata,
        selected_exe=None,
        source_type="steam",
        source_note=f"Persistent library: {row.source} / {row.status}",
        steam_appid=steam_appid,
    )


def apply_locked_artwork(game: DetectedGame, locks: Iterable[ArtworkLock]) -> None:
    """Populate `game.artwork` from `LibraryStore.list_artwork_locks(...)` rows.

    Only locks whose cached file still exists on disk are applied. This is
    the bridge `copy_all_artwork_to_steam` needs — nothing else in the repo
    converts a persisted `ArtworkLock` back into the in-memory `ArtworkAsset`
    shape the copy pipeline reads.
    """
    for lock in locks:
        if not lock.local_path or not Path(lock.local_path).is_file():
            continue
        setattr(
            game.artwork,
            lock.slot,
            ArtworkAsset(
                kind=lock.slot,
                asset_id=lock.candidate_id,
                url="",
                local_path=Path(lock.local_path),
                raw={"source": lock.source} if lock.source else {},
            ),
        )


def games_from_library_snapshot(snapshot: LibrarySnapshot) -> list[DetectedGame]:
    selected_ids = snapshot.selected_ids
    return [
        game_from_library_row(row, selected=row.item_id in selected_ids)
        for row in snapshot.rows
    ]


def library_loaded_status(row_count: int) -> str:
    return f"Loaded {row_count} stored library item(s)."


def build_library_display_update(snapshot: LibrarySnapshot) -> LibraryDisplayUpdate:
    games = tuple(games_from_library_snapshot(snapshot))
    return LibraryDisplayUpdate(games=games, status=library_loaded_status(len(games)))


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


def library_game_index_for_item_id(games: list[DetectedGame], item_id: str) -> int | None:
    if not item_id:
        return None
    for index, game in enumerate(games):
        if library_item_id_for_game(game) == item_id:
            return index
    return None


def selected_visible_library_item_ids(
    games: list[DetectedGame],
    displayed_indices: list[int],
    selected_ids: frozenset[str] | set[str],
) -> tuple[str, ...]:
    visible = library_item_ids_for_games(games, displayed_indices)
    selected = set(selected_ids)
    return tuple(item_id for item_id in visible if item_id in selected)


def selected_visible_library_games(
    games: list[DetectedGame],
    displayed_indices: list[int],
    selected_ids: frozenset[str] | set[str],
) -> list[DetectedGame]:
    visible_ids = selected_visible_library_item_ids(games, displayed_indices, selected_ids)
    games_by_id = library_games_by_item_id(games)
    return [games_by_id[item_id] for item_id in visible_ids if item_id in games_by_id]


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


def persistent_library_notes_text(game: DetectedGame) -> str:
    source = library_source_for_game(game)
    status = library_status_for_game(game)
    return (
        f"Persistent {source} library row - {status}.\n\n"
        "This legacy view is read-only for stored library rows. "
        "Use source scans to refresh library data; Steam writes remain disabled for these rows."
    )


def persistent_library_reason_text(game: DetectedGame) -> str:
    lines = [
        "Persistent library row.",
        f"Source: {game.metadata.extra.get(LIBRARY_SOURCE_META, 'library')}",
        f"Status: {game.metadata.extra.get(LIBRARY_STATUS_META, 'stored')}",
        f"Install folder: {game.root_path}",
    ]
    launch_target = library_launch_target_for_game(game)
    if launch_target:
        lines.append(f"Launch target: {launch_target}")
    lines.append("Read-only in the legacy view; no Steam writes are enabled for this row.")
    return "\n".join(lines)


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
