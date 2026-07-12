from __future__ import annotations

import json
import os
import shutil
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable, Iterable
from uuid import uuid4

from .file_transactions import default_transaction_root, sha256_path
from .image_validation import ArtworkFileInfo, validate_artwork_file


class ArtworkTransactionError(RuntimeError):
    """Raised when a grouped artwork transaction cannot safely complete."""


class ArtworkTransactionVerificationError(ArtworkTransactionError):
    def __init__(self, message: str, outcome: "ArtworkSetOutcome") -> None:
        super().__init__(message)
        self.outcome = outcome


@dataclass(frozen=True, slots=True)
class ArtworkWriteRequest:
    source_path: Path
    target_path: Path
    slot: str = ""


@dataclass(slots=True)
class ArtworkFileOperation:
    target_path: str
    action: str
    slot: str = ""
    source_path: str = ""
    staged_path: str = ""
    backup_path: str = ""
    original_exists: bool = False
    original_hash: str = ""
    staged_hash: str = ""
    written_hash: str = ""
    status: str = "prepared"
    restored: bool = False
    restore_verified: bool = False
    error: str = ""


@dataclass(slots=True)
class ArtworkSetOutcome:
    transaction_id: str
    transaction_dir: str
    manifest_path: str
    operations: list[ArtworkFileOperation] = field(default_factory=list)
    status: str = "prepared"
    restored: bool = False
    restore_verified: bool = False
    error: str = ""


WrittenHook = Callable[[int, ArtworkFileOperation], None]


def _write_manifest(outcome: ArtworkSetOutcome) -> None:
    manifest = Path(outcome.manifest_path)
    payload = asdict(outcome)
    payload["updated_at"] = datetime.now(UTC).isoformat()
    manifest.parent.mkdir(parents=True, exist_ok=True)
    temporary = manifest.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    temporary.replace(manifest)


def _resolved_unique_paths(paths: Iterable[Path]) -> list[Path]:
    result: list[Path] = []
    seen: set[Path] = set()
    for raw_path in paths:
        path = Path(raw_path).expanduser().resolve(strict=False)
        if path in seen:
            continue
        seen.add(path)
        result.append(path)
    return result


def _copy_atomic(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            delete=False,
            dir=target.parent,
            suffix=".sss-artwork.tmp",
        ) as handle:
            temporary = Path(handle.name)
            with source.open("rb") as source_handle:
                shutil.copyfileobj(source_handle, handle)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(target)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _restore_operation(operation: ArtworkFileOperation) -> None:
    target = Path(operation.target_path)
    if operation.original_exists:
        backup = Path(operation.backup_path)
        if not backup.is_file():
            raise ArtworkTransactionError(f"Rollback backup is missing for {target}")
        _copy_atomic(backup, target)
        operation.restored = True
        operation.restore_verified = sha256_path(target) == operation.original_hash
        if not operation.restore_verified:
            raise ArtworkTransactionError(
                f"Restored artwork hash does not match the original for {target}"
            )
    else:
        target.unlink(missing_ok=True)
        operation.restored = True
        operation.restore_verified = not target.exists()
        if not operation.restore_verified:
            raise ArtworkTransactionError(f"Could not remove newly created artwork {target}")
    operation.status = "restored"


def _rollback_all(outcome: ArtworkSetOutcome) -> None:
    failures: list[str] = []
    for operation in reversed(outcome.operations):
        try:
            _restore_operation(operation)
        except Exception as exc:
            operation.error = str(exc)
            operation.status = "rollback_failed"
            failures.append(str(exc))
    outcome.restored = bool(outcome.operations) and all(
        operation.restored for operation in outcome.operations
    )
    outcome.restore_verified = bool(outcome.operations) and all(
        operation.restore_verified for operation in outcome.operations
    )
    if failures:
        raise ArtworkTransactionError("; ".join(failures))


def apply_artwork_set_transaction(
    writes: Iterable[ArtworkWriteRequest],
    *,
    remove_paths: Iterable[Path] = (),
    transaction_root: Path | None = None,
    transaction_id: str | None = None,
    written_hook: WrittenHook | None = None,
) -> ArtworkSetOutcome:
    """Apply a complete artwork set as one verified, reversible transaction.

    Every source image is decoded before any target changes. Every affected target,
    including stale alternate-extension files marked for removal, is backed up
    before the first write. Any failure restores all targets to their exact prior
    state and removes files that did not exist before the transaction.
    """

    write_requests = list(writes)
    removal_requests = list(remove_paths)
    if not write_requests and not removal_requests:
        raise ValueError("Artwork transactions require at least one write or removal.")

    resolved_writes: list[tuple[ArtworkWriteRequest, Path, Path, ArtworkFileInfo]] = []
    target_set: set[Path] = set()
    for request in write_requests:
        source = Path(request.source_path).expanduser().resolve(strict=True)
        target = Path(request.target_path).expanduser().resolve(strict=False)
        if target in target_set:
            raise ValueError(f"Duplicate artwork target: {target}")
        target_set.add(target)
        info = validate_artwork_file(source)
        resolved_writes.append((request, source, target, info))

    removals = _resolved_unique_paths(Path(path) for path in removal_requests)
    for target in removals:
        if target in target_set:
            raise ValueError(f"Artwork target cannot be both written and removed: {target}")
        target_set.add(target)

    tx_id = transaction_id or uuid4().hex
    tx_dir = (transaction_root or default_transaction_root()).expanduser().resolve(
        strict=False
    ) / tx_id
    staged_dir = tx_dir / "staged"
    backup_dir = tx_dir / "backups"
    staged_dir.mkdir(parents=True, exist_ok=False)
    backup_dir.mkdir(parents=True, exist_ok=True)
    manifest = tx_dir / "artwork-manifest.json"
    outcome = ArtworkSetOutcome(
        transaction_id=tx_id,
        transaction_dir=str(tx_dir),
        manifest_path=str(manifest),
    )
    apply_started = False

    try:
        for index, (request, source, target, info) in enumerate(resolved_writes):
            staged = staged_dir / f"{index:03d}-{target.name}"
            shutil.copy2(source, staged)
            staged_info = validate_artwork_file(staged)
            if staged_info.sha256 != info.sha256:
                raise ArtworkTransactionError(
                    f"Staged artwork hash changed unexpectedly for {source}"
                )
            outcome.operations.append(
                ArtworkFileOperation(
                    target_path=str(target),
                    action="write",
                    slot=request.slot,
                    source_path=str(source),
                    staged_path=str(staged),
                    staged_hash=staged_info.sha256,
                )
            )

        for target in removals:
            outcome.operations.append(
                ArtworkFileOperation(
                    target_path=str(target),
                    action="remove",
                )
            )

        for index, operation in enumerate(outcome.operations):
            target = Path(operation.target_path)
            operation.original_exists = target.is_file()
            if operation.original_exists:
                operation.original_hash = sha256_path(target)
                backup = backup_dir / f"{index:03d}-{target.name}"
                shutil.copy2(target, backup)
                if sha256_path(backup) != operation.original_hash:
                    raise ArtworkTransactionError(
                        f"Artwork backup hash does not match original for {target}"
                    )
                operation.backup_path = str(backup)

        _write_manifest(outcome)
        apply_started = True

        for index, operation in enumerate(outcome.operations):
            target = Path(operation.target_path)
            if operation.action == "write":
                staged = Path(operation.staged_path)
                _copy_atomic(staged, target)
                written = validate_artwork_file(target)
                operation.written_hash = written.sha256
                if operation.written_hash != operation.staged_hash:
                    raise ArtworkTransactionError(
                        f"Written artwork hash does not match staged file for {target}"
                    )
            elif operation.action == "remove":
                target.unlink(missing_ok=True)
                if target.exists():
                    raise ArtworkTransactionError(f"Stale artwork could not be removed: {target}")
            else:
                raise ArtworkTransactionError(
                    f"Unsupported artwork operation: {operation.action}"
                )
            operation.status = "committed"
            if written_hook is not None:
                written_hook(index, operation)

        outcome.status = "committed"
        _write_manifest(outcome)
        return outcome
    except Exception as exc:
        outcome.error = str(exc)
        if not apply_started:
            outcome.status = "aborted"
            _write_manifest(outcome)
            if isinstance(exc, ArtworkTransactionError):
                raise
            raise ArtworkTransactionError(f"Artwork transaction preflight failed: {exc}") from exc

        outcome.status = "verification_failed"
        try:
            _rollback_all(outcome)
            outcome.status = "rolled_back"
        except Exception as rollback_exc:
            outcome.status = "rollback_failed"
            outcome.error = f"{exc}; rollback failed: {rollback_exc}"
        finally:
            _write_manifest(outcome)
        raise ArtworkTransactionVerificationError(outcome.error, outcome) from exc
