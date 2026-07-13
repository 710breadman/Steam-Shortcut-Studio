from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import customtkinter as ctk  # noqa: E402

from steam_shortcut_studio.library_store import default_library_database  # noqa: E402
from steam_shortcut_studio.modern_library_view import (  # noqa: E402
    format_size,
    load_modern_library_rows,
)
from prototypes import modern_shell  # noqa: E402


def load_library_games(
    database: Path | str | None = None,
    *,
    include_missing: bool = False,
) -> list[modern_shell.MockGame]:
    return [
        modern_shell.MockGame(
            game_id=row.item_id,
            title=row.title,
            source=row.source,
            platform=row.platform,
            last_played=row.last_played,
            size=row.size,
            status=row.status,
        )
        for row in load_modern_library_rows(database, include_missing=include_missing)
    ]


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
