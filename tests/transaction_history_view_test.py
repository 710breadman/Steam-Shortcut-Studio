from __future__ import annotations

import json
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from steam_shortcut_studio.transaction_history_view import build_transaction_history_view  # noqa: E402


def _write_manifest(root: Path, transaction_id: str, *, original_exists: bool = True) -> None:
    tx_dir = root / transaction_id
    backup = tx_dir / "backups" / "shortcuts.vdf"
    backup.parent.mkdir(parents=True, exist_ok=True)
    backup.write_bytes(b"backup")
    payload = {
        "transaction_id": transaction_id,
        "target_path": str(root / "active" / "shortcuts.vdf"),
        "transaction_dir": str(tx_dir),
        "manifest_path": str(tx_dir / "manifest.json"),
        "staged_path": str(tx_dir / "staged" / "shortcuts.vdf"),
        "backup_path": str(backup) if original_exists else "",
        "original_exists": original_exists,
        "status": "committed",
        "updated_at": datetime(2026, 7, 13, 1, 0, tzinfo=UTC).isoformat(),
    }
    (tx_dir / "manifest.json").write_text(json.dumps(payload), encoding="utf-8")


def test_transaction_history_view_formats_rows_counts_and_invalid_manifests() -> None:
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        _write_manifest(root, "tx-one")
        _write_manifest(root, "tx-new-file", original_exists=False)
        invalid = root / "bad" / "manifest.json"
        invalid.parent.mkdir(parents=True)
        invalid.write_text("not json", encoding="utf-8")

        view = build_transaction_history_view(root)

    assert [row.transaction_id for row in view.rows] == ["tx-one", "tx-new-file"]
    assert [row.restore_state for row in view.rows] == ["Restore available", "No prior file"]
    assert view.status_counts == {"committed": 2}
    assert len(view.invalid_manifests) == 1
    assert "Transactions: 2 (committed: 2); 1 invalid manifest(s)" == view.summary


if __name__ == "__main__":
    test_transaction_history_view_formats_rows_counts_and_invalid_manifests()
    print("Transaction history view tests passed.")
