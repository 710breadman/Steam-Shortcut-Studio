"""Steam Shortcut Studio entry point.

Launches the modern shell by default. The classic window remains available:

    SteamShortcutStudio --classic

If the modern shell cannot start because its GUI dependency is unavailable in
this build, the classic window is used instead rather than failing outright --
a packaging mistake should degrade the interface, never leave a user with no
app at all.
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Sequence

LOGGER = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="SteamShortcutStudio")
    parser.add_argument(
        "--classic",
        action="store_true",
        help="Open the original window instead of the modern shell.",
    )
    parser.add_argument(
        "--database",
        type=Path,
        default=None,
        help="Persistent library database to open (modern shell only).",
    )
    parser.add_argument(
        "--include-missing",
        action="store_true",
        help="Show games that disappeared in the latest authoritative scan.",
    )
    return parser


def run_classic() -> int:
    from steam_shortcut_studio.app import main as classic_main

    classic_main()
    return 0


def run_modern(database: Path | None, include_missing: bool) -> int:
    import customtkinter as ctk

    from steam_shortcut_studio.modern_shell import ModernShell

    ctk.set_appearance_mode("dark")
    app = ModernShell(database, include_missing=include_missing)
    app.mainloop()
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.classic:
        return run_classic()
    try:
        return run_modern(args.database, args.include_missing)
    except ImportError:
        LOGGER.warning(
            "The modern shell is unavailable in this build; opening the classic "
            "interface instead.",
            exc_info=True,
        )
        return run_classic()


if __name__ == "__main__":
    sys.exit(main())
