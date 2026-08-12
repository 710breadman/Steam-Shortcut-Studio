"""Developer entry point for the modern shell.

The shell itself now lives in `steam_shortcut_studio/modern_shell.py` -- it is
production code and ships in packaged builds through `main.py`. This file stays
as the convenience launcher that `run.bat` / `run.ps1` and the docs point at.
"""
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
from steam_shortcut_studio.modern_shell import ModernShell  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Open the modern UI shell against the persistent library database."
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
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    ctk.set_appearance_mode("dark")
    app = ModernShell(args.database, include_missing=args.include_missing)
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
