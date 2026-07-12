from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import customtkinter as ctk  # noqa: E402

from steam_shortcut_studio.library_store import (  # noqa: E402
    LibraryStore,
    default_library_database,
)
from prototypes import modern_shell  # noqa: E402


def format_size(size_bytes: int) -> str:
    value = max(0, int(size_bytes))
    if value == 0:
        return "—"
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


def load_library_games(
    database: Path | str | None = None,
    *,
    include_missing: bool = False,
) -> list[modern_shell.MockGame]:
    store = LibraryStore(database or default_library_database())
    games: list[modern_shell.MockGame] = []
    for record in store.list_records(include_missing=include_missing):
        resolved = store.resolve_item(record.stable_id)
        if resolved is None:
            continue
        source = record.source.replace("_", " ").title()
        platform = record.platform.title() if record.platform else "PC"
        games.append(
            modern_shell.MockGame(
                game_id=record.stable_id,
                title=resolved.display_title,
                source=source,
                platform=platform,
                last_played="—",
                size=format_size(record.size_bytes),
                status=status_for_record(store, record.stable_id),
            )
        )
    games.sort(key=lambda game: (game.title.casefold(), game.game_id))
    return games


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Open the read-only modern UI prototype with persistent library data."
    )
    parser.add_argument(
        "--database",
        type=Path,
        default=default_library_database(),
        help="Persistent Steam Shortcut Studio library database.",
    )
    parser.add_argument(
        "--include-missing",
        action="store_true",
        help="Include launcher games that disappeared in the latest authoritative scan.",
    )
    parser.add_argument(
        "--empty",
        action="store_true",
        help="Show an empty library instead of falling back to mock games.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    games = load_library_games(
        args.database,
        include_missing=args.include_missing,
    )
    if games:
        modern_shell.GAMES = games
    elif args.empty:
        modern_shell.GAMES = []

    ctk.set_appearance_mode("dark")
    app = modern_shell.ModernShell()
    app.title("Steam Shortcut Studio — Persistent Library Prototype")
    if games:
        first = games[0]
        app.selected_ids = {first.game_id}
        app.active_id = first.game_id
        app._activate(first.game_id)
        app._set_status(
            f"Read-only persistent library — {len(games)} stored game"
            f"{'s' if len(games) != 1 else ''}"
        )
    elif args.empty:
        app.selected_ids.clear()
        app._refresh_selection_ui()
        app._set_status("Read-only persistent library — no stored games")
    else:
        app._set_status(
            "Read-only prototype — no stored games; showing design mock data"
        )
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
