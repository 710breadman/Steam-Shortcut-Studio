from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from steam_shortcut_studio.transactions import (
    ChangeAction,
    ChangeKind,
    PlannedChange,
    RiskLevel,
    TransactionPlan,
    TransactionResult,
    VerificationResult,
)


class TransactionPlanTests(unittest.TestCase):
    def test_only_approved_changes_enter_apply_scope(self) -> None:
        artwork = PlannedChange.create(
            item_id="game-1",
            kind=ChangeKind.ARTWORK,
            action=ChangeAction.UPDATE,
            target_path="grid/1p.png",
            description="Replace portrait artwork",
            risk=RiskLevel.SAFE,
        )
        launch = PlannedChange.create(
            item_id="game-1",
            kind=ChangeKind.SHORTCUTS,
            action=ChangeAction.UPDATE,
            target_path="shortcuts.vdf",
            description="Change launch target",
            risk=RiskLevel.ADVANCED,
            requires_steam_closed=True,
        )
        plan = TransactionPlan.build(
            profile_id="123",
            item_ids=["game-1"],
            changes=[artwork, launch],
        )

        approved = plan.approve_safe_changes()

        self.assertEqual(approved, {artwork.change_id})
        self.assertEqual(plan.approved_changes, [artwork])
        self.assertFalse(plan.requires_steam_closed)
        self.assertFalse(plan.has_advanced_changes)

    def test_advanced_approval_exposes_steam_close_requirement(self) -> None:
        change = PlannedChange.create(
            item_id="game-1",
            kind=ChangeKind.COMPATIBILITY,
            action=ChangeAction.UPDATE,
            target_path="config.vdf",
            description="Change compatibility tool",
            risk=RiskLevel.ADVANCED,
            requires_steam_closed=True,
        )
        plan = TransactionPlan.build(
            profile_id="123",
            item_ids=["game-1"],
            changes=[change],
        )
        plan.approve([change.change_id])
        plan.validate_for_apply()

        self.assertTrue(plan.requires_steam_closed)
        self.assertTrue(plan.has_advanced_changes)
        self.assertEqual(plan.affected_paths, ["config.vdf"])

    def test_plan_rejects_change_for_unknown_item(self) -> None:
        change = PlannedChange.create(
            item_id="other-game",
            kind=ChangeKind.ARTWORK,
            action=ChangeAction.CREATE,
            target_path="grid/2p.png",
            description="Add artwork",
        )
        with self.assertRaises(ValueError):
            TransactionPlan.build(
                profile_id="123",
                item_ids=["game-1"],
                changes=[change],
            )

    def test_apply_validation_requires_approval(self) -> None:
        change = PlannedChange.create(
            item_id="game-1",
            kind=ChangeKind.ARTWORK,
            action=ChangeAction.UPDATE,
            target_path="grid/1p.png",
            description="Replace artwork",
            risk=RiskLevel.SAFE,
        )
        plan = TransactionPlan.build(
            profile_id="123",
            item_ids=["game-1"],
            changes=[change],
        )
        with self.assertRaises(ValueError):
            plan.validate_for_apply()

    def test_transaction_result_requires_verification_for_success(self) -> None:
        result = TransactionResult(transaction_id="tx-1", applied=True)
        self.assertFalse(result.successful)
        result.verification.append(
            VerificationResult(change_id="change-1", success=True)
        )
        self.assertTrue(result.successful)


if __name__ == "__main__":
    unittest.main()
