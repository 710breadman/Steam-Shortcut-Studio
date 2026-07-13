from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .transaction_history_view import (
    TransactionHistoryView,
    TransactionHistoryViewRow,
    build_transaction_history_view,
)


@dataclass(frozen=True, slots=True)
class TransactionOpenTarget:
    path: Path
    kind: str


class TransactionHistoryController:
    """Tk-free transaction/history boundary for production backup views."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = root

    def history_view(self) -> TransactionHistoryView:
        return build_transaction_history_view(self.root)

    def backup_folder_target(self, row: TransactionHistoryViewRow) -> TransactionOpenTarget | None:
        if not row.backup_path:
            return None
        return TransactionOpenTarget(path=Path(row.backup_path).parent, kind="backup_folder")

    def manifest_target(self, row: TransactionHistoryViewRow) -> TransactionOpenTarget:
        return TransactionOpenTarget(path=Path(row.manifest_path), kind="manifest")
