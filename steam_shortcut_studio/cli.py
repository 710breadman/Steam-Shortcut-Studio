from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Sequence

from .library_store import LibraryStore, default_library_database
from .source_scans import PersistedSourceScan, SourceScanCoordinator
from .sources.epic import EpicManifestAdapter
from .transaction_history import history_status_counts, list_transaction_history


def _json_text(value: object) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True, default=str)


def _scan_payload(execution: PersistedSourceScan, store: LibraryStore) -> dict[str, object]:
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


def _command_scan_epic(args: argparse.Namespace) -> int:
    store = LibraryStore(args.database)
    adapter = EpicManifestAdapter(args.manifest_dir)
    execution = SourceScanCoordinator(store).run(adapter)
    payload = _scan_payload(execution, store)

    if args.json_output:
        print(_json_text(payload))
    else:
        status = "COMPLETED" if execution.succeeded else "BLOCKED"
        print(f"Epic scan: {status}")
        print(f"Database: {payload['database']}")
        print(f"Detected: {execution.result.item_count}")
        if execution.snapshot is not None:
            print(
                "Stored: "
                f"{execution.snapshot.inserted} added, "
                f"{execution.snapshot.updated} updated, "
                f"{execution.snapshot.marked_missing} marked missing"
            )
        else:
            print("Stored library presence was not changed.")
        if execution.result.issues:
            print("Issues:")
            for issue in execution.result.issues:
                print(f"  [{issue.severity.upper()}] {issue.code}: {issue.message}")
        if execution.error:
            print(f"Reason: {execution.error}")

    return 0 if execution.succeeded else 2


def _resolved_payload(store: LibraryStore, item_id: str) -> dict[str, object]:
    resolved = store.resolve_item(item_id)
    if resolved is None:
        raise KeyError(item_id)
    return {
        "stable_id": resolved.record.stable_id,
        "source": resolved.record.source,
        "external_id": resolved.record.external_id,
        "source_title": resolved.record.title,
        "display_title": resolved.display_title,
        "install_path": resolved.record.install_path,
        "source_launch_target": resolved.record.launch_target,
        "launch_target": resolved.launch_target,
        "launch_arguments": resolved.launch_arguments,
        "working_directory": resolved.working_directory,
        "platform": resolved.record.platform,
        "version": resolved.record.version,
        "size_bytes": resolved.record.size_bytes,
        "is_present": resolved.record.is_present,
        "launch_target_exists": resolved.record.launch_target_exists,
        "overridden_fields": sorted(resolved.overridden_fields),
        "notes": resolved.notes,
        "evidence": list(resolved.record.evidence),
        "metadata": resolved.record.metadata,
        "artwork_locks": [asdict(lock) for lock in store.list_artwork_locks(item_id)],
        "rejected_matches": [
            asdict(rejection) for rejection in store.list_rejected_matches(item_id)
        ],
    }


def _command_list_library(args: argparse.Namespace) -> int:
    store = LibraryStore(args.database)
    records = store.list_records(
        source=args.source,
        include_missing=args.include_missing,
    )
    payload = [_resolved_payload(store, record.stable_id) for record in records]

    if args.json_output:
        print(_json_text(payload))
    elif not payload:
        print("No stored library items matched.")
    else:
        for item in payload:
            state = "present" if item["is_present"] else "missing"
            override = " [overridden]" if item["overridden_fields"] else ""
            print(
                f"{item['display_title']} | {item['source']} | {state}{override}\n"
                f"  {item['launch_target'] or '(launch target needs review)'}"
            )
        print(f"Total: {len(payload)}")
    return 0


def _command_scan_history(args: argparse.Namespace) -> int:
    store = LibraryStore(args.database)
    runs = store.list_scan_runs(source=args.source, limit=args.limit)
    payload = [asdict(run) for run in runs]
    if args.json_output:
        print(_json_text(payload))
    elif not runs:
        print("No scan history found.")
    else:
        for run in runs:
            finished = run.finished_at or "in progress"
            print(
                f"{run.source} | {run.status} | {run.item_count} items | "
                f"{run.issue_count} issues | {finished}"
            )
            if run.error:
                print(f"  {run.error}")
    return 0


def _command_transaction_history(args: argparse.Namespace) -> int:
    result = list_transaction_history(args.root, include_invalid=True)
    entries, invalid = result
    payload = {
        "entries": [asdict(entry) for entry in entries],
        "status_counts": history_status_counts(entries),
        "invalid_manifests": [str(path) for path in invalid],
    }
    if args.json_output:
        print(_json_text(payload))
    elif not entries and not invalid:
        print("No transaction history found.")
    else:
        for entry in entries:
            restore = "restore available" if entry.restore_available else "no restore backup"
            print(
                f"{entry.updated_at.isoformat()} | {entry.status} | "
                f"{entry.display_target} | {restore}"
            )
            if entry.error:
                print(f"  {entry.error}")
        if invalid:
            print(f"Invalid manifests: {len(invalid)}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="steam-shortcut-studio",
        description="Read-only library discovery and Steam Shortcut Studio diagnostics.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan_epic = subparsers.add_parser(
        "scan-epic",
        help="Read Epic .item manifests and persist an authoritative snapshot.",
    )
    scan_epic.add_argument(
        "--manifest-dir",
        type=Path,
        default=None,
        help="Override the Epic manifest directory.",
    )
    scan_epic.add_argument(
        "--database",
        type=Path,
        default=default_library_database(),
        help="Library SQLite database path.",
    )
    scan_epic.add_argument("--json", dest="json_output", action="store_true")
    scan_epic.set_defaults(handler=_command_scan_epic)

    list_library = subparsers.add_parser(
        "list-library",
        help="List persisted library records with effective manual overrides.",
    )
    list_library.add_argument(
        "--database",
        type=Path,
        default=default_library_database(),
    )
    list_library.add_argument("--source", default=None)
    list_library.add_argument("--include-missing", action="store_true")
    list_library.add_argument("--json", dest="json_output", action="store_true")
    list_library.set_defaults(handler=_command_list_library)

    scan_history = subparsers.add_parser(
        "scan-history",
        help="Show persisted launcher scan history.",
    )
    scan_history.add_argument(
        "--database",
        type=Path,
        default=default_library_database(),
    )
    scan_history.add_argument("--source", default=None)
    scan_history.add_argument("--limit", type=int, default=50)
    scan_history.add_argument("--json", dest="json_output", action="store_true")
    scan_history.set_defaults(handler=_command_scan_history)

    transaction_history = subparsers.add_parser(
        "transaction-history",
        help="Show verified file transaction and restore-point history.",
    )
    transaction_history.add_argument("--root", type=Path, default=None)
    transaction_history.add_argument("--json", dest="json_output", action="store_true")
    transaction_history.set_defaults(handler=_command_transaction_history)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.handler(args))
    except (OSError, ValueError, RuntimeError, KeyError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
