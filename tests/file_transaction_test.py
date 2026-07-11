from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from steam_shortcut_studio.file_transactions import (
    FileTransactionError,
    FileTransactionVerificationError,
    apply_verified_file_transaction,
    sha256_path,
)


class FileTransactionTests(unittest.TestCase):
    def test_new_file_is_staged_written_and_recorded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "target" / "example.bin"
            outcome = apply_verified_file_transaction(
                target,
                b"new data",
                stage_validator=lambda path: self.assertEqual(path.read_bytes(), b"new data"),
                written_verifier=lambda path: self.assertEqual(path.read_bytes(), b"new data"),
                transaction_root=root / "transactions",
            )

            self.assertEqual(target.read_bytes(), b"new data")
            self.assertEqual(outcome.status, "committed")
            self.assertFalse(outcome.original_exists)
            self.assertEqual(outcome.written_hash, sha256_path(target))
            manifest = json.loads(Path(outcome.manifest_path).read_text(encoding="utf-8"))
            self.assertEqual(manifest["status"], "committed")
            self.assertEqual(manifest["staged_hash"], manifest["written_hash"])

    def test_existing_file_gets_grouped_backup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "target.bin"
            target.write_bytes(b"original")

            outcome = apply_verified_file_transaction(
                target,
                b"replacement",
                transaction_root=root / "transactions",
            )

            backup = Path(outcome.backup_path)
            self.assertTrue(backup.exists())
            self.assertEqual(backup.read_bytes(), b"original")
            self.assertEqual(outcome.original_hash, sha256_path(backup))
            self.assertEqual(target.read_bytes(), b"replacement")

    def test_stage_failure_leaves_original_untouched(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "target.bin"
            target.write_bytes(b"original")

            def reject(_path: Path) -> None:
                raise ValueError("bad staged format")

            with self.assertRaises(FileTransactionError):
                apply_verified_file_transaction(
                    target,
                    b"replacement",
                    stage_validator=reject,
                    transaction_root=root / "transactions",
                )

            self.assertEqual(target.read_bytes(), b"original")
            self.assertEqual(list((root / "transactions").glob("*")), [])

    def test_verification_failure_restores_existing_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "target.bin"
            target.write_bytes(b"original")

            def fail_verification(_path: Path) -> None:
                raise ValueError("readback mismatch")

            with self.assertRaises(FileTransactionVerificationError) as raised:
                apply_verified_file_transaction(
                    target,
                    b"replacement",
                    written_verifier=fail_verification,
                    transaction_root=root / "transactions",
                )

            outcome = raised.exception.outcome
            self.assertEqual(target.read_bytes(), b"original")
            self.assertEqual(outcome.status, "rolled_back")
            self.assertTrue(outcome.restored)
            self.assertTrue(outcome.restore_verified)
            manifest = json.loads(Path(outcome.manifest_path).read_text(encoding="utf-8"))
            self.assertEqual(manifest["status"], "rolled_back")

    def test_verification_failure_removes_new_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "target.bin"

            with self.assertRaises(FileTransactionVerificationError) as raised:
                apply_verified_file_transaction(
                    target,
                    b"new data",
                    written_verifier=lambda _path: (_ for _ in ()).throw(ValueError("reject")),
                    transaction_root=root / "transactions",
                )

            self.assertFalse(target.exists())
            self.assertTrue(raised.exception.outcome.restore_verified)


if __name__ == "__main__":
    unittest.main()
