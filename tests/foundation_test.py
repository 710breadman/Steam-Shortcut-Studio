from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from steam_shortcut_studio.artwork_policy import (
    ArtworkDecision,
    ArtworkEvidence,
    ArtworkMatchPolicy,
)
from steam_shortcut_studio.jobs import BatchSummary, JobKind, JobRecord, JobState
from steam_shortcut_studio.selection import SelectionState


class SelectionStateTests(unittest.TestCase):
    def test_active_item_is_separate_from_bulk_selection(self) -> None:
        state = SelectionState()
        state.set_active("game-b")
        state.replace(["game-a", "game-c"])

        self.assertEqual(state.active_id, "game-b")
        self.assertEqual(state.selected_in_order(["game-a", "game-b", "game-c"]), ["game-a", "game-c"])

    def test_range_selection_preserves_display_order(self) -> None:
        order = ["a", "b", "c", "d", "e"]
        state = SelectionState()
        state.add("b")

        selected = state.select_range(order, "d")

        self.assertEqual(selected, ["b", "c", "d"])
        self.assertEqual(state.selected_in_order(order), ["b", "c", "d"])

    def test_range_selection_falls_back_to_target_when_anchor_is_missing(self) -> None:
        order = ["a", "b", "c", "d"]
        state = SelectionState(anchor_id="z")

        selected = state.select_range(order, "c")

        self.assertEqual(selected, ["c"])
        self.assertEqual(state.selected_ids, {"c"})
        self.assertEqual(state.anchor_id, "c")

    def test_filtering_does_not_silently_remove_selected_items(self) -> None:
        state = SelectionState()
        state.replace(["visible", "hidden-by-filter"])

        visible_selection = state.selected_in_order(["visible"])

        self.assertEqual(visible_selection, ["visible"])
        self.assertEqual(state.count, 2)

    def test_deleted_items_can_be_removed_explicitly(self) -> None:
        state = SelectionState(selected_ids={"keep", "delete"}, active_id="delete", anchor_id="delete")

        removed = state.retain_available(["keep"])

        self.assertEqual(removed, {"delete"})
        self.assertEqual(state.selected_ids, {"keep"})
        self.assertIsNone(state.active_id)
        self.assertIsNone(state.anchor_id)


class JobModelTests(unittest.TestCase):
    def test_job_lifecycle_and_batch_summary(self) -> None:
        first = JobRecord("job-1", "game-1", JobKind.ARTWORK)
        second = JobRecord("job-2", "game-2", JobKind.ARTWORK)

        first.transition(JobState.RUNNING)
        first.update_progress(0.5, message="Searching providers")
        first.transition(JobState.SUCCEEDED)
        second.transition(JobState.RUNNING)
        second.transition(JobState.NEEDS_REVIEW, message="Edition conflict")

        summary = BatchSummary.from_jobs([first, second])
        self.assertTrue(summary.complete)
        self.assertEqual(summary.succeeded, 1)
        self.assertEqual(summary.needs_review, 1)
        self.assertEqual(summary.finished, 2)

    def test_failed_job_can_be_retried_without_touching_successes(self) -> None:
        failed = JobRecord("job-1", "game-1", JobKind.METADATA)
        succeeded = JobRecord("job-2", "game-2", JobKind.METADATA)
        failed.transition(JobState.RUNNING)
        failed.fail("Provider unavailable")
        succeeded.transition(JobState.RUNNING)
        succeeded.transition(JobState.SUCCEEDED)

        failed.retry()

        self.assertEqual(failed.state, JobState.QUEUED)
        self.assertEqual(failed.attempts, 1)
        self.assertEqual(succeeded.state, JobState.SUCCEEDED)

    def test_invalid_transition_is_rejected(self) -> None:
        job = JobRecord("job-1", "game-1", JobKind.SCAN)
        with self.assertRaises(ValueError):
            job.transition(JobState.SUCCEEDED)


class ArtworkPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = ArtworkMatchPolicy()

    def test_strong_complete_match_is_automatic(self) -> None:
        result = self.policy.evaluate(
            ArtworkEvidence(
                identity_score=98,
                set_coherence_score=95,
                complete_set=True,
                source="SteamGridDB",
            )
        )
        self.assertEqual(result.decision, ArtworkDecision.AUTO_ACCEPT)

    def test_weak_or_incomplete_match_requires_review(self) -> None:
        weak = self.policy.evaluate(
            ArtworkEvidence(identity_score=80, set_coherence_score=90, complete_set=True)
        )
        incomplete = self.policy.evaluate(
            ArtworkEvidence(identity_score=98, set_coherence_score=95, complete_set=False)
        )
        self.assertEqual(weak.decision, ArtworkDecision.REVIEW)
        self.assertEqual(incomplete.decision, ArtworkDecision.REVIEW)

    def test_invalid_image_is_rejected(self) -> None:
        result = self.policy.evaluate(
            ArtworkEvidence(
                identity_score=100,
                set_coherence_score=100,
                complete_set=True,
                valid_image=False,
            )
        )
        self.assertEqual(result.decision, ArtworkDecision.REJECT)

    def test_manual_lock_never_auto_applies(self) -> None:
        result = self.policy.evaluate(
            ArtworkEvidence(
                identity_score=100,
                set_coherence_score=100,
                complete_set=True,
                manually_locked=True,
            )
        )
        self.assertEqual(result.decision, ArtworkDecision.REVIEW)


if __name__ == "__main__":
    unittest.main()
