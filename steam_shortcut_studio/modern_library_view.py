from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .library_store import LibraryStore, default_library_database
from .models import DetectedGame
from .ui_library_adapter import (
    LIBRARY_SIZE_META,
    library_item_id_for_game,
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
