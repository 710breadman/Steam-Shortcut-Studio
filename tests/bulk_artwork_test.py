from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from steam_shortcut_studio.artwork_policy import ArtworkEvidence  # noqa: E402
from steam_shortcut_studio.bulk_artwork import (  # noqa: E402
    ArtworkSearchMode,
    ArtworkSearchOutcome,
    BulkArtworkCoordinator,
    BulkArtworkItem,
    build_artwork_search_plan,
)
from steam_shortcut_studio.job_queue import BackgroundJobQueue  # noqa: E402
from steam_shortcut_studio.jobs import JobState  # noqa: E402
from steam_shortcut_studio.selection import SelectionState  # noqa: E402


def _strong_outcome(requested_slots: tuple[str, ...]) -> ArtworkSearchOutcome:
    return ArtworkSearchOutcome(
        evidence=ArtworkEvidence(
            identity_score=98,
            set_coherence_score=95,
            source="fixture",
        ),
        found_slots=frozenset(requested_slots),
        provider="fixture",
        candidate_ids={slot: f"candidate-{slot}" for slot in requested_slots},
    )


def test_search_plans_preserve_existing_and_locked_slots() -> None:
    item = BulkArtworkItem(
        item_id="game-1",
        title="Example",
        existing_slots=frozenset({"grid", "wide"}),
        locked_slots=frozenset({"grid", "logo"}),
    )

    missing = build_artwork_search_plan(item, ArtworkSearchMode.MISSING_ONLY)
    unlocked = build_artwork_search_plan(item, ArtworkSearchMode.ALL_UNLOCKED)
    complete = build_artwork_search_plan(item, ArtworkSearchMode.COMPLETE_SET)

    assert missing.requested_slots == ("hero", "icon")
    assert missing.preserved_locked_slots == ("grid", "logo")
    assert missing.preserved_existing_slots == ("grid", "wide", "logo")
    assert unlocked.requested_slots == ("wide", "hero", "icon")
    assert complete.requested_slots == unlocked.requested_slots


def test_submit_selected_dispatches_only_selected_available_ids_in_display_order() -> None:
    selection = SelectionState(selected_ids={"game-3", "game-1", "missing"})
    ordered = ["game-1", "game-2", "missing", "game-3"]
    items = {
        "game-1": BulkArtworkItem("game-1", "One"),
        "game-2": BulkArtworkItem("game-2", "Two"),
        "game-3": BulkArtworkItem("game-3", "Three"),
    }
    searched: list[str] = []

    def searcher(item, requested_slots, token, report_progress):
        searched.append(item.item_id)
        return _strong_outcome(requested_slots)

    with BackgroundJobQueue(max_workers=1) as jobs:
        submission = BulkArtworkCoordinator(jobs).submit_selected(
            selection,
            ordered,
            items,
            searcher,
            mode=ArtworkSearchMode.COMPLETE_SET,
        )
        assert jobs.wait_for_idle(timeout=3.0)

    assert [job.item_id for job in submission.jobs] == ["game-1", "game-3"]
    assert searched == ["game-1", "game-3"]
    assert submission.missing_item_ids == ("missing",)
    assert all(job.state is JobState.SUCCEEDED for job in submission.jobs)


def test_strong_matches_auto_accept_and_weak_matches_route_to_review() -> None:
    items = {
        "strong": BulkArtworkItem("strong", "Strong"),
        "weak": BulkArtworkItem("weak", "Weak"),
    }
    selection = SelectionState(selected_ids=set(items))

    def searcher(item, requested_slots, token, report_progress):
        if item.item_id == "strong":
            return _strong_outcome(requested_slots)
        return ArtworkSearchOutcome(
            evidence=ArtworkEvidence(
                identity_score=78,
                set_coherence_score=92,
                source="fixture",
            ),
            found_slots=frozenset(requested_slots),
            provider="fixture",
        )

    with BackgroundJobQueue(max_workers=2) as jobs:
        submission = BulkArtworkCoordinator(jobs).submit_selected(
            selection,
            ["strong", "weak"],
            items,
            searcher,
            mode=ArtworkSearchMode.COMPLETE_SET,
        )
        assert jobs.wait_for_idle(timeout=3.0)

    by_id = {job.item_id: job for job in submission.jobs}
    assert by_id["strong"].state is JobState.SUCCEEDED
    assert by_id["strong"].result["decision"] == "auto_accept"
    assert by_id["weak"].state is JobState.NEEDS_REVIEW
    assert by_id["weak"].result["decision"] == "review"


def test_invalid_or_empty_results_never_auto_apply() -> None:
    items = {
        "invalid": BulkArtworkItem("invalid", "Invalid"),
        "empty": BulkArtworkItem("empty", "Empty"),
    }
    selection = SelectionState(selected_ids=set(items))

    def searcher(item, requested_slots, token, report_progress):
        if item.item_id == "empty":
            return ArtworkSearchOutcome(
                evidence=ArtworkEvidence(identity_score=99, set_coherence_score=99),
                found_slots=frozenset(),
            )
        return ArtworkSearchOutcome(
            evidence=ArtworkEvidence(
                identity_score=99,
                set_coherence_score=99,
                valid_image=False,
            ),
            found_slots=frozenset(requested_slots),
        )

    with BackgroundJobQueue(max_workers=2) as jobs:
        submission = BulkArtworkCoordinator(jobs).submit_selected(
            selection,
            ["invalid", "empty"],
            items,
            searcher,
            mode=ArtworkSearchMode.COMPLETE_SET,
        )
        assert jobs.wait_for_idle(timeout=3.0)

    by_id = {job.item_id: job for job in submission.jobs}
    assert by_id["invalid"].state is JobState.SKIPPED
    assert by_id["invalid"].result["decision"] == "reject"
    assert by_id["empty"].state is JobState.SKIPPED
    assert by_id["empty"].result["found_slots"] == []


def test_fully_locked_item_skips_without_calling_searcher() -> None:
    item = BulkArtworkItem(
        item_id="locked",
        title="Locked",
        locked_slots=frozenset({"grid", "wide", "hero", "logo", "icon"}),
    )
    selection = SelectionState(selected_ids={"locked"})
    called = False

    def searcher(item, requested_slots, token, report_progress):
        nonlocal called
        called = True
        return _strong_outcome(requested_slots)

    with BackgroundJobQueue(max_workers=1) as jobs:
        submission = BulkArtworkCoordinator(jobs).submit_selected(
            selection,
            ["locked"],
            {"locked": item},
            searcher,
            mode=ArtworkSearchMode.ALL_UNLOCKED,
        )
        assert jobs.wait_for_idle(timeout=3.0)

    assert called is False
    assert submission.jobs[0].state is JobState.SKIPPED
    assert submission.jobs[0].result["preserved_locked_slots"] == [
        "grid",
        "wide",
        "hero",
        "logo",
        "icon",
    ]


if __name__ == "__main__":
    test_search_plans_preserve_existing_and_locked_slots()
    test_submit_selected_dispatches_only_selected_available_ids_in_display_order()
    test_strong_matches_auto_accept_and_weak_matches_route_to_review()
    test_invalid_or_empty_results_never_auto_apply()
    test_fully_locked_item_skips_without_calling_searcher()
    print("Bulk artwork coordinator tests passed.")
