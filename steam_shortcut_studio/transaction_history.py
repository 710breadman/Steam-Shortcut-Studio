from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Iterable

from .file_transactions import default_transaction_root


TERMINAL_STATUSES = {"committed", "rolled_back", "rollback_failed"}
SAFE_RETENTION_STATUSES = {"committed", "rolled_back"}


@dataclass(frozen=True, slots=True)
class TransactionHistoryEntry:
    transaction_id: str
    manifest_path: Path
    transaction_dir: Path
    target_path: Path
    staged_path: Path | None
    backup_path: Path | None
    status: str
    updated_at: datetime
    original_exists: bool = False
    original_hash: str = ""
    staged_hash: str = ""
    written_hash: str = ""
    restored: bool = False
    restore_verified: bool = False
    error: str = ""

    @property
    def is_terminal(self) -> bool:
        return self.status in TERMINAL_STATUSES

    @property
    def restore_available(self) -> bool:
        return bool(
            self.original_exists
            and self.backup_path is not None
            and self.backup_path.is_file()
        )

    @property
    def target_exists(self) -> bool:
        return self.target_path.exists()

    @property
    def display_target(self) -> str:
        return self.target_path.name or str(self.target_path)


def _parse_datetime(value: object, *, fallback_path: Path) -> datetime:
    text = str(value or "").strip()
    if text:
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            return parsed.astimezone(UTC)
        except ValueError:
            pass
    try:
        return datetime.fromtimestamp(fallback_path.stat().st_mtime, tz=UTC)
    except OSError:
        return datetime.fromtimestamp(0, tz=UTC)


def _optional_path(value: object) -> Path | None:
    text = str(value or "").strip()
    return Path(text) if text else None


def load_transaction_entry(manifest_path: Path) -> TransactionHistoryEntry:
    manifest = manifest_path.expanduser().resolve(strict=False)
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Transaction manifest root must be a JSON object.")

    transaction_id = str(payload.get("transaction_id") or manifest.parent.name).strip()
    target_text = str(payload.get("target_path") or "").strip()
    if not transaction_id:
        raise ValueError("Transaction manifest has no transaction ID.")
    if not target_text:
        raise ValueError("Transaction manifest has no target path.")

    transaction_dir = Path(
        str(payload.get("transaction_dir") or manifest.parent)
    ).expanduser().resolve(strict=False)

    return TransactionHistoryEntry(
        transaction_id=transaction_id,
        manifest_path=manifest,
        transaction_dir=transaction_dir,
        target_path=Path(target_text).expanduser().resolve(strict=False),
        staged_path=_optional_path(payload.get("staged_path")),
        backup_path=_optional_path(payload.get("backup_path")),
        status=str(payload.get("status") or "unknown").strip() or "unknown",
        updated_at=_parse_datetime(payload.get("updated_at"), fallback_path=manifest),
        original_exists=bool(payload.get("original_exists", False)),
        original_hash=str(payload.get("original_hash") or ""),
        staged_hash=str(payload.get("staged_hash") or ""),
        written_hash=str(payload.get("written_hash") or ""),
        restored=bool(payload.get("restored", False)),
        restore_verified=bool(payload.get("restore_verified", False)),
        error=str(payload.get("error") or ""),
    )


def list_transaction_history(
    root: Path | None = None,
    *,
    include_invalid: bool = False,
) -> list[TransactionHistoryEntry] | tuple[list[TransactionHistoryEntry], list[Path]]:
    history_root = (root or default_transaction_root()).expanduser().resolve(strict=False)
    entries: list[TransactionHistoryEntry] = []
    invalid: list[Path] = []

    if history_root.exists():
        for manifest in history_root.glob("*/manifest.json"):
            try:
                entries.append(load_transaction_entry(manifest))
            except (OSError, ValueError, json.JSONDecodeError):
                invalid.append(manifest)

    entries.sort(key=lambda entry: (entry.updated_at, entry.transaction_id), reverse=True)
    if include_invalid:
        return entries, invalid
    return entries


def history_status_counts(entries: Iterable[TransactionHistoryEntry]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for entry in entries:
        counts[entry.status] = counts.get(entry.status, 0) + 1
    return dict(sorted(counts.items()))


def retention_candidates(
    entries: Iterable[TransactionHistoryEntry],
    *,
    keep_latest: int = 50,
    older_than_days: int | None = None,
    now: datetime | None = None,
) -> list[TransactionHistoryEntry]:
    """Return history entries eligible for manual cleanup.

    This function never deletes anything. Failed or non-terminal transactions are
    retained automatically because they may be needed for diagnosis or recovery.
    """

    ordered = sorted(
        entries,
        key=lambda entry: (entry.updated_at, entry.transaction_id),
        reverse=True,
    )
    keep_count = max(0, int(keep_latest))
    cutoff: datetime | None = None
    if older_than_days is not None:
        current = now or datetime.now(UTC)
        if current.tzinfo is None:
            current = current.replace(tzinfo=UTC)
        cutoff = current.astimezone(UTC) - timedelta(days=max(0, older_than_days))

    candidates: list[TransactionHistoryEntry] = []
    for index, entry in enumerate(ordered):
        if index < keep_count:
            continue
        if entry.status not in SAFE_RETENTION_STATUSES:
            continue
        if cutoff is not None and entry.updated_at >= cutoff:
            continue
        candidates.append(entry)
    return candidates
