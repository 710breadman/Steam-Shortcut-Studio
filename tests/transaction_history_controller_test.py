from __future__ import annotations

import json
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from steam_shortcut_studio.transaction_history_controller import TransactionHistoryController  # noqa: E402


def _write_manifest(root: Path, transaction_id: str, *, original_exists: bool = True) -> Path:
    tx_dir = root / transaction_id
    backup = tx_dir / "backups" / "shortcuts.vdf"
    backup.parent.mkdir(parents=True, exist_ok=True)
    backup.write_bytes(b"backup")
    manifest = tx_dir / "manifest.json"
    payload = {
        "transaction_id": transaction_id,
        "target_path": str(root / "active" / "shortcuts.vdf"),
        "transaction_dir": str(tx_dir),
        "manifest_path": str(manifest),
        "backup_path": str(backup) if original_exists else "",
        "original_exists": original_exists,
        "status": "committed",
        "updated_at": datetime(2026, 7, 13, 2, 0, tzinfo=UTC).isoformat(),
    }
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    return manifest


def test_transaction_history_controller_loads_view_and_open_targets() -> None:
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        manifest = _write_manifest(root, "tx-one")
        controller = TransactionHistoryController(root)

        view = controller.history_view()
        row = view.rows[0]
        backup_target = controller.backup_folder_target(row)
        manifest_target = controller.manifest_target(row)

        assert backup_target is not None
        assert backup_target.kind == "backup_folder"
        assert backup_target.path == root / "tx-one" / "backups"
        assert manifest_target.kind == "manifest"
        assert manifest_target.path == manifest


def test_transaction_history_controller_has_no_backup_target_for_new_files() -> None:
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        _write_manifest(root, "tx-new-file", original_exists=False)
        controller = TransactionHistoryController(root)

        row = controller.history_view().rows[0]

        assert controller.backup_folder_target(row) is None


if __name__ == "__main__":
    test_transaction_history_controller_loads_view_and_open_targets()
    test_transaction_history_controller_has_no_backup_target_for_new_files()
    print("Transaction history controller tests passed.")
