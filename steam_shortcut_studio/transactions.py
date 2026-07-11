from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Iterable
from uuid import uuid4


class ChangeKind(StrEnum):
    SHORTCUTS = "shortcuts"
    ARTWORK = "artwork"
    NOTES = "notes"
    COMPATIBILITY = "compatibility"
    SETTINGS = "settings"


class ChangeAction(StrEnum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    RESTORE = "restore"


class RiskLevel(StrEnum):
    SAFE = "safe"
    REVIEW = "review"
    ADVANCED = "advanced"


@dataclass(frozen=True, slots=True)
class PlannedChange:
    change_id: str
    item_id: str
    kind: ChangeKind
    action: ChangeAction
    target_path: str
    description: str
    risk: RiskLevel = RiskLevel.REVIEW
    requires_steam_closed: bool = False
    original_exists: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        *,
        item_id: str,
        kind: ChangeKind,
        action: ChangeAction,
        target_path: str | Path,
        description: str,
        risk: RiskLevel = RiskLevel.REVIEW,
        requires_steam_closed: bool = False,
        original_exists: bool = False,
        metadata: dict[str, Any] | None = None,
    ) -> "PlannedChange":
        return cls(
            change_id=uuid4().hex,
            item_id=item_id,
            kind=kind,
            action=action,
            target_path=str(target_path),
            description=description,
            risk=risk,
            requires_steam_closed=requires_steam_closed,
            original_exists=original_exists,
            metadata=dict(metadata or {}),
        )


@dataclass(slots=True)
class TransactionPlan:
    profile_id: str
    item_ids: list[str]
    changes: list[PlannedChange]
    transaction_id: str = field(default_factory=lambda: uuid4().hex)
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    approved_change_ids: set[str] = field(default_factory=set)

    @classmethod
    def build(
        cls,
        *,
        profile_id: str,
        item_ids: Iterable[str],
        changes: Iterable[PlannedChange],
    ) -> "TransactionPlan":
        ordered_item_ids = list(dict.fromkeys(item_id for item_id in item_ids if item_id))
        change_list = list(changes)
        unknown_items = {change.item_id for change in change_list} - set(ordered_item_ids)
        if unknown_items:
            raise ValueError(
                "Every change must reference an item in the transaction plan: "
                + ", ".join(sorted(unknown_items))
            )
        return cls(profile_id=profile_id, item_ids=ordered_item_ids, changes=change_list)

    def approve(self, change_ids: Iterable[str]) -> None:
        known = {change.change_id for change in self.changes}
        requested = set(change_ids)
        unknown = requested - known
        if unknown:
            raise ValueError("Unknown change IDs: " + ", ".join(sorted(unknown)))
        self.approved_change_ids.update(requested)

    def approve_safe_changes(self) -> set[str]:
        safe_ids = {
            change.change_id
            for change in self.changes
            if change.risk is RiskLevel.SAFE
        }
        self.approved_change_ids.update(safe_ids)
        return safe_ids

    def revoke(self, change_ids: Iterable[str]) -> None:
        self.approved_change_ids.difference_update(change_ids)

    @property
    def approved_changes(self) -> list[PlannedChange]:
        return [
            change
            for change in self.changes
            if change.change_id in self.approved_change_ids
        ]

    @property
    def pending_changes(self) -> list[PlannedChange]:
        return [
            change
            for change in self.changes
            if change.change_id not in self.approved_change_ids
        ]

    @property
    def requires_steam_closed(self) -> bool:
        return any(change.requires_steam_closed for change in self.approved_changes)

    @property
    def has_advanced_changes(self) -> bool:
        return any(change.risk is RiskLevel.ADVANCED for change in self.approved_changes)

    @property
    def affected_paths(self) -> list[str]:
        return list(dict.fromkeys(change.target_path for change in self.approved_changes))

    def validate_for_apply(self) -> None:
        if not self.changes:
            raise ValueError("Transaction plan contains no changes.")
        if not self.approved_change_ids:
            raise ValueError("Transaction plan contains no approved changes.")
        known = {change.change_id for change in self.changes}
        unknown = self.approved_change_ids - known
        if unknown:
            raise ValueError("Approved changes are not present in the plan.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "transaction_id": self.transaction_id,
            "created_at": self.created_at,
            "profile_id": self.profile_id,
            "item_ids": list(self.item_ids),
            "approved_change_ids": sorted(self.approved_change_ids),
            "changes": [asdict(change) for change in self.changes],
        }


@dataclass(frozen=True, slots=True)
class VerificationResult:
    change_id: str
    success: bool
    message: str = ""
    original_hash: str = ""
    written_hash: str = ""


@dataclass(slots=True)
class TransactionResult:
    transaction_id: str
    applied: bool = False
    rolled_back: bool = False
    backup_paths: list[str] = field(default_factory=list)
    verification: list[VerificationResult] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def verified(self) -> bool:
        return bool(self.verification) and all(result.success for result in self.verification)

    @property
    def successful(self) -> bool:
        return self.applied and self.verified and not self.errors and not self.rolled_back
