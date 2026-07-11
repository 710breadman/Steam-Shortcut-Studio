from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable
from uuid import uuid4

from .settings_store import _appdata_dir

PathValidator = Callable[[Path], None]


class FileTransactionError(RuntimeError):
    """Raised when a staged file transaction cannot safely complete."""


class FileTransactionVerificationError(FileTransactionError):
    """Raised after a write fails verification and rollback is attempted."""

    def __init__(self, message: str, outcome: "FileTransactionOutcome") -> None:
        super().__init__(message)
        self.outcome = outcome


@dataclass(slots=True)
class FileTransactionOutcome:
    transaction_id: str
    target_path: str
    transaction_dir: str
    manifest_path: str
    staged_path: str
    backup_path: str = ""
    original_exists: bool = False
    original_hash: str = ""
    staged_hash: str = ""
    written_hash: str = ""
    status: str = "prepared"
    restored: bool = False
    restore_verified: bool = False
    error: str = ""


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def default_transaction_root() -> Path:
    return _appdata_dir() / "transactions"


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    temporary.replace(path)


def _manifest_payload(outcome: FileTransactionOutcome) -> dict[str, object]:
    payload = asdict(outcome)
    payload["updated_at"] = datetime.now(UTC).isoformat()
    return payload


def _persist(outcome: FileTransactionOutcome) -> None:
    _write_json(Path(outcome.manifest_path), _manifest_payload(outcome))


def _rollback(outcome: FileTransactionOutcome) -> None:
    target = Path(outcome.target_path)
    backup = Path(outcome.backup_path) if outcome.backup_path else None

    if outcome.original_exists:
        if backup is None or not backup.exists():
            raise FileTransactionError("Rollback backup is missing.")
        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(delete=False, dir=target.parent, suffix=".restore.tmp") as handle:
            restore_temp = Path(handle.name)
        try:
            shutil.copy2(backup, restore_temp)
            restore_temp.replace(target)
        finally:
            if restore_temp.exists():
                restore_temp.unlink(missing_ok=True)
        outcome.restored = True
        outcome.restore_verified = sha256_path(target) == outcome.original_hash
        if not outcome.restore_verified:
            raise FileTransactionError("Rollback completed but restored hash does not match the original.")
    else:
        target.unlink(missing_ok=True)
        outcome.restored = True
        outcome.restore_verified = not target.exists()
        if not outcome.restore_verified:
            raise FileTransactionError("Rollback could not remove the newly created target.")


def apply_verified_file_transaction(
    target_path: Path,
    data: bytes,
    *,
    stage_validator: PathValidator | None = None,
    written_verifier: PathValidator | None = None,
    transaction_root: Path | None = None,
    transaction_id: str | None = None,
) -> FileTransactionOutcome:
    """Stage, back up, atomically replace, verify, and roll back one file.

    The caller supplies format-specific validation. No target file is changed until
    staging validation and backup creation have both succeeded.
    """

    target = target_path.expanduser().resolve(strict=False)
    tx_id = transaction_id or uuid4().hex
    tx_dir = (transaction_root or default_transaction_root()).expanduser().resolve(strict=False) / tx_id
    staged_dir = tx_dir / "staged"
    backup_dir = tx_dir / "backups"
    staged_dir.mkdir(parents=True, exist_ok=False)
    backup_dir.mkdir(parents=True, exist_ok=True)

    staged = staged_dir / target.name
    staged.write_bytes(data)
    if stage_validator is not None:
        try:
            stage_validator(staged)
        except Exception as exc:
            shutil.rmtree(tx_dir, ignore_errors=True)
            raise FileTransactionError(f"Staged file validation failed: {exc}") from exc

    original_exists = target.exists()
    backup = backup_dir / target.name if original_exists else None
    original_hash = ""
    if original_exists:
        try:
            original_hash = sha256_path(target)
            shutil.copy2(target, backup)
            if sha256_path(backup) != original_hash:
                raise FileTransactionError("Backup hash does not match the original file.")
        except Exception as exc:
            shutil.rmtree(tx_dir, ignore_errors=True)
            if isinstance(exc, FileTransactionError):
                raise
            raise FileTransactionError(f"Could not create transaction backup: {exc}") from exc

    manifest = tx_dir / "manifest.json"
    outcome = FileTransactionOutcome(
        transaction_id=tx_id,
        target_path=str(target),
        transaction_dir=str(tx_dir),
        manifest_path=str(manifest),
        staged_path=str(staged),
        backup_path=str(backup) if backup is not None else "",
        original_exists=original_exists,
        original_hash=original_hash,
        staged_hash=sha256_path(staged),
    )
    _persist(outcome)

    target.parent.mkdir(parents=True, exist_ok=True)
    write_temp: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, dir=target.parent, suffix=".sss-write.tmp") as handle:
            write_temp = Path(handle.name)
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        write_temp.replace(target)
        write_temp = None

        if written_verifier is not None:
            written_verifier(target)
        outcome.written_hash = sha256_path(target)
        if outcome.written_hash != outcome.staged_hash:
            raise FileTransactionError("Written file hash does not match the staged file.")

        outcome.status = "committed"
        _persist(outcome)
        return outcome
    except Exception as exc:
        outcome.status = "verification_failed"
        outcome.error = str(exc)
        try:
            _rollback(outcome)
            outcome.status = "rolled_back"
        except Exception as rollback_exc:
            outcome.status = "rollback_failed"
            outcome.error = f"{exc}; rollback failed: {rollback_exc}"
        finally:
            _persist(outcome)
        raise FileTransactionVerificationError(outcome.error, outcome) from exc
    finally:
        if write_temp is not None and write_temp.exists():
            write_temp.unlink(missing_ok=True)
