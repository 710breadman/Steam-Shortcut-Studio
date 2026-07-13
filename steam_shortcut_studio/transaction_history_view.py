from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .transaction_history import (
    TransactionHistoryEntry,
    history_status_counts,
    list_transaction_history,
)


@dataclass(frozen=True, slots=True)
class TransactionHistoryViewRow:
    transaction_id: str
    status: str
    updated_at: str
    target: str
    restore_state: str
    backup_path: str
    manifest_path: str
    error: str = ""


@dataclass(frozen=True, slots=True)
class TransactionHistoryView:
    rows: tuple[TransactionHistoryViewRow, ...]
    status_counts: dict[str, int]
    invalid_manifests: tuple[str, ...]

    @property
    def summary(self) -> str:
        total = len(self.rows)
        invalid = len(self.invalid_manifests)
        counts = ", ".join(f"{status}: {count}" for status, count in self.status_counts.items())
        if not counts:
            counts = "none"
        suffix = f"; {invalid} invalid manifest(s)" if invalid else ""
        return f"Transactions: {total} ({counts}){suffix}"


def transaction_history_row(entry: TransactionHistoryEntry) -> TransactionHistoryViewRow:
    if entry.restore_available:
        restore_state = "Restore available"
    elif entry.original_exists:
        restore_state = "Backup missing"
    else:
        restore_state = "No prior file"
    return TransactionHistoryViewRow(
        transaction_id=entry.transaction_id,
        status=entry.status,
        updated_at=entry.updated_at.astimezone().strftime("%Y-%m-%d %H:%M:%S %Z"),
        target=entry.display_target,
        restore_state=restore_state,
        backup_path=str(entry.backup_path or ""),
        manifest_path=str(entry.manifest_path),
        error=entry.error,
    )


def transaction_history_detail_text(row: TransactionHistoryViewRow) -> str:
    return (
        f"Backup: {row.backup_path or 'none'}\n"
        f"Manifest: {row.manifest_path}"
    )


def build_transaction_history_view(root: Path | None = None) -> TransactionHistoryView:
    entries, invalid_paths = list_transaction_history(root, include_invalid=True)
    return TransactionHistoryView(
        rows=tuple(transaction_history_row(entry) for entry in entries),
        status_counts=history_status_counts(entries),
        invalid_manifests=tuple(str(path) for path in invalid_paths),
    )
