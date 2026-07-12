from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Sequence

from .library_store import LibraryStore, default_library_database
from .source_scans import PersistedSourceScan, SourceScanCoordinator
from .sources.local import FolderScannerAdapter
from .sources.steam import SteamLibraryAdapter


def _payload(execution: PersistedSourceScan, store: LibraryStore) -> dict[str, object]:
    snapshot = execution.snapshot
    return {
        "scan_id": execution.scan_id,
        "source": execution.result.source,
        "status": execution.status,
        "authoritative": execution.authoritative,
        "persisted": execution.persisted,
        "detected_items": execution.result.item_count,
        "issues": [asdict(issue) for issue in execution.result.issues],
        "snapshot": (
            {
                "inserted": snapshot.inserted,
                "updated": snapshot.updated,
                "marked_missing": snapshot.marked_missing,
            }
            if snapshot is not None
            else None
        ),
        "error": execution.error,
        "database": str(store.database_path.resolve(strict=False)),
    }


def _print_result(label: str, payload: dict[str, object], *, json_output: bool) -> None:
    if json_output:
        print(json.dumps(payload, indent=2, sort_keys=True, default=str))
        return

    status = "COMPLETED" if payload["status"] == "completed" else "BLOCKED"
    print(f"{label} scan: {status}")
    print(f"Database: {payload['database']}")
    print(f"Detected: {payload['detected_items']}")
    snapshot = payload["snapshot"]
    if isinstance(snapshot, dict):
        print(
            "Stored: "
            f"{snapshot['inserted']} added, "
            f"{snapshot['updated']} updated, "
            f"{snapshot['marked_missing']} marked missing"
        )
    else:
        print("Stored library presence was not changed.")

    issues = payload["issues"]
    if isinstance(issues, list) and issues:
        print("Issues:")
        for issue in issues:
            if isinstance(issue, dict):
                print(
                    f"  [{str(issue.get('severity', 'warning')).upper()}] "
                    f"{issue.get('code', 'issue')}: {issue.get('message', '')}"
                )
    if payload["error"]:
        print(f"Reason: {payload['error']}")


def _run(adapter, args: argparse.Namespace, label: str) -> int:
    store = LibraryStore(args.database)
    execution = SourceScanCoordinator(store).run(adapter)
    payload = _payload(execution, store)
    _print_result(label, payload, json_output=args.json_output)
    return 0 if execution.succeeded else 2


def _scan_steam(args: argparse.Namespace) -> int:
    return _run(SteamLibraryAdapter(args.steam_root), args, "Steam")


def _scan_folder(args: argparse.Namespace) -> int:
    return _run(FolderScannerAdapter(args.root), args, "Folder")


def _add_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--database",
        type=Path,
        default=default_library_database(),
        help="Persistent Steam Shortcut Studio library database.",
    )
    parser.add_argument("--json", dest="json_output", action="store_true")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="steam-shortcut-studio-sources",
        description="Persist native Steam or loose-folder games without writing Steam.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    steam = subparsers.add_parser(
        "scan-steam",
        help="Read installed native Steam games into the persistent library.",
    )
    steam.add_argument("--steam-root", type=Path, required=True)
    _add_common_arguments(steam)
    steam.set_defaults(handler=_scan_steam)

    folder = subparsers.add_parser(
        "scan-folder",
        help="Run the existing loose/local game scanner into the persistent library.",
    )
    folder.add_argument("--root", type=Path, required=True)
    _add_common_arguments(folder)
    folder.set_defaults(handler=_scan_folder)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return int(args.handler(args))
    except (OSError, ValueError, RuntimeError, KeyError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
