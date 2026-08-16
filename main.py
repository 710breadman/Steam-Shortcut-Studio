"""Steam Shortcut Studio entry point.

The modern shell is the only interface. If its GUI dependency is missing the
app fails loudly with an actionable message rather than quietly opening a
different, older window -- a silent downgrade is harder to diagnose than a
clear error.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

MISSING_GUI_MESSAGE = (
    "Steam Shortcut Studio needs the 'customtkinter' package to draw its "
    "interface.\nInstall it with:\n\n    python -m pip install -r requirements.txt\n"
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="SteamShortcutStudio")
    parser.add_argument(
        "--database",
        type=Path,
        default=None,
        help="Persistent library database to open.",
    )
    parser.add_argument(
        "--include-missing",
        action="store_true",
        help="Show games that disappeared in the latest authoritative scan.",
    )
    return parser


def run_modern(database: Path | None, include_missing: bool) -> int:
    import customtkinter as ctk

    from steam_shortcut_studio.modern_shell import ModernShell

    ctk.set_appearance_mode("dark")
    app = ModernShell(database, include_missing=include_missing)
    app.mainloop()
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return run_modern(args.database, args.include_missing)
    except ImportError:
        print(MISSING_GUI_MESSAGE, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
