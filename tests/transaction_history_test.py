from __future__ import annotations

import json
import sys
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from steam_shortcut_studio.transaction_history import (  # noqa: E402
    history_status_counts,
    list_transaction_history,
    retention_candidates,
)


def _write_manifest(
    root: Path,
    transaction_id: str,
    *,
    status: str,
    updated_at: datetime,
    original_exists: bool = True,
    backup_exists: bool = True,
) -> Path:
    transaction_dir = root / transaction_id
    backup = transaction_dir / "backups" / "shortcuts.vdf"
    if backup_exists:
        backup.parent.mkdir(parents=True, exist_ok=True)
        backup.write_bytes(b"backup")
    else:
        transaction_dir.mkdir(parents=True, exist_ok=True)

    target = root / "active" / f"{transaction_id}.vdf"
    payload = {
        "transaction_id": transaction_id,
        "target_path": str(target),
        "transaction_dir": str(transaction_dir),
        "manifest_path": str(transaction_dir / "manifest.json"),
        "staged_path": str(transaction_dir / "staged" / "shortcuts.vdf"),
        "backup_path": str(backup) if original_exists else "",
        "original_exists": original_exists,
        "original_hash": "old",
        "staged_hash": "new",
        "written_hash": "new" if status == "committed" else "",
        "status": status,
        "restored": status == "rolled_back",
        "restore_verified": status == "rolled_back",
        "error": "failure" if "failed" in status else "",
        "updated_at": updated_at.isoformat(),
    }
    manifest = transaction_dir / "manifest.json"
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    return manifest


def test_history_lists_newest_first_and_reports_invalid_manifests() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        now = datetime(2026, 7, 11, 20, 0, tzinfo=UTC)
        _write_manifest(root, "older", status="committed", updated_at=now - timedelta(days=2))
        _write_manifest(root, "newer", status="rolled_back", updated_at=now)
        invalid = root / "invalid" / "manifest.json"
        invalid.parent.mkdir(parents=True)
        invalid.write_text("not json", encoding="utf-8")

        entries, invalid_paths = list_transaction_history(root, include_invalid=True)

        assert [entry.transaction_id for entry in entries] == ["newer", "older"]
        assert invalid_paths == [invalid.resolve()]
        assert entries[0].restore_available is True
        assert history_status_counts(entries) == {"committed": 1, "rolled_back": 1}


def test_retention_candidates_never_include_failed_or_recent_entries() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        now = datetime(2026, 7, 11, 20, 0, tzinfo=UTC)
        _write_manifest(root, "recent", status="committed", updated_at=now)
        _write_manifest(root, "old-committed", status="committed", updated_at=now - timedelta(days=90))
        _write_manifest(root, "old-rolled-back", status="rolled_back", updated_at=now - timedelta(days=80))
        _write_manifest(root, "old-failed", status="rollback_failed", updated_at=now - timedelta(days=100))
        entries = list_transaction_history(root)
        assert isinstance(entries, list)

        candidates = retention_candidates(
            entries,
            keep_latest=1,
            older_than_days=30,
            now=now,
        )

        assert {entry.transaction_id for entry in candidates} == {
            "old-committed",
            "old-rolled-back",
        }
        assert "old-failed" not in {entry.transaction_id for entry in candidates}


def test_new_file_transaction_has_no_restore_backup() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_manifest(
            root,
            "new-file",
            status="committed",
            updated_at=datetime.now(UTC),
            original_exists=False,
            backup_exists=False,
        )
        entries = list_transaction_history(root)
        assert isinstance(entries, list)
        assert len(entries) == 1
        assert entries[0].restore_available is False


if __name__ == "__main__":
    test_history_lists_newest_first_and_reports_invalid_manifests()
    test_retention_candidates_never_include_failed_or_recent_entries()
    test_new_file_transaction_has_no_restore_backup()
    print("Transaction history tests passed.")
