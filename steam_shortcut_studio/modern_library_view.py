from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .library_store import LibraryStore, default_library_database
from .models import DetectedGame
from .ui_library_adapter import (
    LIBRARY_LAUNCH_TARGET_META,
    LIBRARY_SIZE_META,
    is_persistent_library_game,
    library_item_id_for_game,
    library_launch_target_for_game,
    library_platform_for_game,
    library_source_for_game,
    library_status_for_game,
)


@dataclass(frozen=True, slots=True)
class ModernLibraryRow:
    item_id: str
    title: str
    source: str
    platform: str
    last_played: str
    size: str
    status: str

    @property
    def platform_size_label(self) -> str:
        if self.size and self.size != "\u2014":
            return f"{self.platform} / {self.size}"
        return self.platform


@dataclass(frozen=True, slots=True)
class ModernLibraryTableRow:
    checkbox: str
    title: str
    source: str
    platform: str
    status: str
    executable: str
    artwork: str
    existing: str

    @property
    def values(self) -> tuple[str, str, str, str, str, str, str, str]:
        return (
            self.checkbox,
            self.title,
            self.source,
            self.platform,
            self.status,
            self.executable,
            self.artwork,
            self.existing,
        )


def format_size(size_bytes: int) -> str:
    value = max(0, int(size_bytes))
    if value == 0:
        return "\u2014"
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


def status_for_record(store: LibraryStore, item_id: str) -> str:
    resolved = store.resolve_item(item_id)
    if resolved is None:
        return "Review"
    record = resolved.record
    if not record.is_present:
        return "Missing"
    if not resolved.launch_target or record.launch_target_exists is False:
        return "Review"
    if resolved.overridden_fields or store.list_artwork_locks(item_id):
        return "Customized"
    return "Ready"


def load_modern_library_rows(
    database: Path | str | None = None,
    *,
    include_missing: bool = False,
) -> list[ModernLibraryRow]:
    store = LibraryStore(database or default_library_database())
    rows: list[ModernLibraryRow] = []
    for record in store.list_records(include_missing=include_missing):
        resolved = store.resolve_item(record.stable_id)
        if resolved is None:
            continue
        rows.append(
            ModernLibraryRow(
                item_id=record.stable_id,
                title=resolved.display_title,
                source=record.source.replace("_", " ").title(),
                platform=record.platform.title() if record.platform else "PC",
                last_played="\u2014",
                size=format_size(record.size_bytes),
                status=status_for_record(store, record.stable_id),
            )
        )
    rows.sort(key=lambda row: (row.title.casefold(), row.item_id))
    return rows


def modern_library_row_for_game(game: DetectedGame) -> ModernLibraryRow:
    try:
        size = format_size(int(game.metadata.extra.get(LIBRARY_SIZE_META) or "0"))
    except ValueError:
        size = "\u2014"
    return ModernLibraryRow(
        item_id=library_item_id_for_game(game),
        title=game.display_title,
        source=library_source_for_game(game),
        platform=library_platform_for_game(game),
        last_played="\u2014",
        size=size,
        status=library_status_for_game(game),
    )


def existing_status_label(game: DetectedGame, *, source: str, status: str) -> str:
    if is_persistent_library_game(game):
        return f"Stored {source} ({status})"
    if game.is_native_steam_game:
        label = "Installed Steam"
        if game.existing_appid is not None:
            label += f" + non-Steam ({game.existing_match or 'title'})"
        return label
    if game.existing_appid is not None:
        label = "Existing non-Steam"
        if game.existing_match:
            label += f" ({game.existing_match})"
        return label
    return "New non-Steam"


def modern_library_table_row_for_game(
    game: DetectedGame,
    *,
    artwork_status: str | None = None,
) -> ModernLibraryTableRow:
    executable = str(game.selected_exe or "")
    source = game.source_type.replace("_", " ").title() if game.source_type else "Folder"
    platform = "PC"
    status = "Selected" if game.selected else "Ready"
    if is_persistent_library_game(game):
        row = modern_library_row_for_game(game)
        executable = library_launch_target_for_game(game) or executable
        source = row.source
        platform = row.platform_size_label
        status = row.status
    if game.is_native_steam_game:
        executable = f"Steam AppID {game.steam_appid}"
        source = "Steam"
        platform = "PC"
        status = "Installed"
    return ModernLibraryTableRow(
        checkbox="[x]" if game.selected else "[ ]",
        title=game.display_title,
        source=source,
        platform=platform,
        status=status,
        executable=executable,
        artwork=artwork_status or game.artwork_status,
        existing=existing_status_label(game, source=source, status=status),
    )


def modern_library_table_row_tags(game: DetectedGame) -> tuple[str, ...]:
    return () if game.selected else ("unselected",)


def normalized_table_column_order(
    configured_order: list[str],
    all_columns: tuple[str, ...],
) -> list[str]:
    order = [column for column in configured_order if column in all_columns]
    order.extend(column for column in all_columns if column not in order)
    return order


def normalized_visible_table_columns(
    configured_visible: list[str],
    all_columns: tuple[str, ...],
    *,
    fallback: tuple[str, ...] = ("add", "title", "exe"),
) -> list[str]:
    visible = [column for column in configured_visible if column in all_columns]
    if not visible:
        visible = [column for column in fallback if column in all_columns]
    return visible


def selected_column_id_for_label(
    label: str,
    column_labels: dict[str, str],
    *,
    fallback: str = "title",
) -> str:
    for column, column_label in column_labels.items():
        if column_label == label:
            return column
    return fallback


def display_columns_for_table(
    order: list[str],
    visible: list[str],
    *,
    fallback: str = "title",
) -> list[str]:
    visible_set = set(visible)
    display = [column for column in order if column in visible_set]
    if not display:
        display = [fallback]
    return display


def game_matches_view_filter(game: DetectedGame, selected_filter: str) -> bool:
    if selected_filter == "Checked":
        return game.selected
    if selected_filter == "Needs artwork":
        return game.artwork.selected_count() < len(game.artwork.slot_names())
    if selected_filter == "New non-Steam":
        return not game.is_native_steam_game and game.existing_appid is None
    if selected_filter == "Existing non-Steam":
        return not game.is_native_steam_game and game.existing_appid is not None
    if selected_filter == "Installed Steam":
        return game.is_native_steam_game
    if selected_filter == "Stored Library":
        return is_persistent_library_game(game)
    if selected_filter == "Needs review":
        return is_persistent_library_game(game) and modern_library_row_for_game(game).status == "Review"
    if selected_filter == "Missing":
        return is_persistent_library_game(game) and modern_library_row_for_game(game).status == "Missing"
    if selected_filter == "Skipped":
        return not game.selected
    return True


def visible_library_indices(games: list[DetectedGame], selected_filter: str) -> list[int]:
    return [index for index, game in enumerate(games) if game_matches_view_filter(game, selected_filter)]


def view_filter_status_message(visible_count: int, total_count: int) -> str:
    return f"Showing {visible_count}/{total_count} game row(s)."


def library_sort_key(game: DetectedGame, column: str) -> Any:
    if column == "add":
        return (not game.selected, game.display_title.casefold())
    if column == "title":
        return game.display_title.casefold()
    if column == "source":
        if is_persistent_library_game(game):
            row = modern_library_row_for_game(game)
            return (0, row.source.casefold(), row.title.casefold())
        return (1, game.source_type.casefold(), game.display_title.casefold())
    if column == "platform":
        if is_persistent_library_game(game):
            row = modern_library_row_for_game(game)
            return (row.platform.casefold(), row.title.casefold())
        return ("pc", game.display_title.casefold())
    if column == "status":
        if is_persistent_library_game(game):
            row = modern_library_row_for_game(game)
            return (row.status.casefold(), row.title.casefold())
        return ("", game.display_title.casefold())
    if column == "exe":
        if is_persistent_library_game(game):
            return str(game.metadata.extra.get(LIBRARY_LAUNCH_TARGET_META) or "").casefold()
        return str(game.selected_exe or "").casefold()
    if column == "artwork":
        return game.artwork.selected_count()
    if column == "existing":
        source_rank = 0 if game.is_native_steam_game else 1
        shortcut_rank = 0 if game.existing_appid is not None else 1
        return (source_rank, shortcut_rank, game.display_title.casefold())
    return game.display_title.casefold()


def library_sort_preset_key(game: DetectedGame, preset: str) -> Any:
    if preset == "Library status":
        return library_sort_key(game, "status")
    if preset == "Source":
        return library_sort_key(game, "source")
    if preset == "Selected first":
        return (not game.selected, game.display_title.casefold())
    if preset == "Needs artwork":
        return (game.artwork.selected_count(), game.display_title.casefold())
    if preset == "Steam status":
        return library_sort_key(game, "existing")
    if preset == "Installed Steam first":
        return (not game.is_native_steam_game, game.display_title.casefold())
    if preset == "New shortcuts first":
        return (game.is_native_steam_game, game.existing_appid is not None, game.display_title.casefold())
    return game.display_title.casefold()
