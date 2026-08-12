from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from steam_shortcut_studio.artwork_policy import ArtworkEvidence  # noqa: E402
from steam_shortcut_studio.artwork_review_workspace import (  # noqa: E402
    ArtworkReviewQueue,
    ArtworkReviewRow,
    artwork_queue_progress_text,
    artwork_rejection_clear_message,
    artwork_review_action_message,
    artwork_review_detail_text,
    artwork_review_empty_message,
    artwork_review_header_text,
    artwork_review_no_pending_message,
    artwork_review_selection_required_message,
    artwork_review_status_text,
    build_artwork_review_rows,
    build_artwork_review_summary,
    pending_review_item_ids,
    review_result_slot_count,
    selected_artwork_review_results,
    source_review_clear_message,
)
from steam_shortcut_studio.bulk_artwork import (  # noqa: E402
    ArtworkSearchMode,
    ArtworkSearchOutcome,
    BulkArtworkCoordinator,
    BulkArtworkItem,
)
from steam_shortcut_studio.job_queue import BackgroundJobQueue, JobEvent  # noqa: E402
from steam_shortcut_studio.jobs import JobState  # noqa: E402
from steam_shortcut_studio.library_controller import LibraryController  # noqa: E402
from steam_shortcut_studio.library_store import LibraryStore  # noqa: E402
from steam_shortcut_studio.selection import SelectionState  # noqa: E402
from steam_shortcut_studio.sources.base import (  # noqa: E402
    SourceLibraryItem,
    stable_source_item_id,
)


def test_build_artwork_review_rows_preserves_item_order_and_slot_metadata() -> None:
    rows = build_artwork_review_rows(
        ("item-two", "item-one"),
        {"item-one": "One", "item-two": "Two"},
        {
            "item-one": {
                "provider": "fixture",
                "identity_score": 90,
                "set_coherence_score": 80,
                "reasons": ["Needs manual review."],
                "candidate_ids": {"grid": "grid-one"},
                "details": {
                    "validated_files": {
                        "grid": {
                            "path": r"C:\cache\grid-one.png",
                            "width": 600,
                            "height": 900,
                        }
                    }
                },
            },
            "item-two": {
                "provider": "fixture",
                "candidate_ids": {"logo": "logo-two", "hero": "hero-two"},
                "details": {"validated_files": {"hero": {"path": r"C:\cache\hero-two.png"}}},
            },
        },
    )

    assert [(row.title, row.slot, row.candidate_id) for row in rows] == [
        ("Two", "hero", "hero-two"),
        ("Two", "logo", "logo-two"),
        ("One", "grid", "grid-one"),
    ]
    assert rows[0].path == r"C:\cache\hero-two.png"
    assert rows[0].dimensions_label == ""
    assert rows[2].dimensions_label == "600x900"
    assert rows[2].identity_score == 90
    assert rows[2].reasons == ("Needs manual review.",)


def test_review_result_slot_count_only_counts_known_slots() -> None:
    assert review_result_slot_count(
        {
            "candidate_ids": {
                "grid": "grid-one",
                "wide": "wide-one",
                "unknown": "ignored",
            }
        }
    ) == 2


def test_artwork_review_action_messages() -> None:
    assert artwork_review_action_message("accept", 2) == "Accepted 2 artwork candidate(s)."
    assert artwork_review_action_message("reject", 3) == "Rejected 3 artwork candidate(s)."
    assert artwork_review_action_message("skip", 4) == "Skipped 4 artwork candidate(s)."


def test_artwork_review_dialog_text_helpers() -> None:
    row = ArtworkReviewRow(
        item_id="item-one",
        title="One",
        slot="grid",
        candidate_id="grid-one",
        path=r"C:\cache\grid-one.png",
        provider="fixture",
        identity_score=91,
        set_coherence_score=82,
        reasons=("Strong title match.", "Valid dimensions."),
    )

    assert (
        artwork_review_header_text(
            selected_item_count=4,
            locked_slots=2,
            rejected_matches=3,
            pending_slot_count=5,
        )
        == "Selected rows: 4    Accepted/locked slots: 2    Rejected candidates: 3    Pending review slots: 5"
    )
    assert (
        artwork_review_status_text(locked_slots=2, rejected_matches=3, pending_slot_count=5)
        == "Artwork decisions: 2 accepted/locked, 3 rejected, 5 pending slot(s)."
    )
    assert artwork_review_empty_message() == "No pending artwork review candidates for selected rows."
    assert artwork_review_selection_required_message("review") == "Select stored library rows before reviewing artwork decisions."
    assert (
        artwork_review_selection_required_message("clear_rejections")
        == "Select stored library rows before clearing artwork rejections."
    )
    assert artwork_review_no_pending_message() == "No selected rows have pending artwork review results."
    assert artwork_review_no_pending_message(retry=True) == "No selected rows have pending artwork review results to retry."
    assert artwork_review_detail_text(row) == (
        "One\n"
        "grid / fixture / grid-one\n"
        "Identity 91    Set 82\n"
        r"C:\cache\grid-one.png"
        "\n"
        "Strong title match.; Valid dimensions."
    )


def test_review_clear_messages() -> None:
    assert source_review_clear_message(0) == "No source review jobs to clear."
    assert source_review_clear_message(2) == "Cleared 2 source review job(s)."
    assert artwork_rejection_clear_message(5) == "Cleared 5 rejected artwork candidate(s)."


def test_pending_review_item_ids_preserves_selected_order() -> None:
    assert pending_review_item_ids(
        ("missing", "second", "first"),
        {
            "first": {"candidate_ids": {"grid": "grid-1"}},
            "second": {"candidate_ids": {"grid": "grid-2"}},
        },
    ) == ("second", "first")


def test_selected_artwork_review_results_preserves_selected_order() -> None:
    first = {"item_id": "first", "candidate_ids": {"grid": "grid-1"}}
    second = {"item_id": "second", "candidate_ids": {"logo": "logo-2"}}

    assert selected_artwork_review_results(
        ("missing", "second", "first"),
        {
            "first": first,
            "second": second,
        },
    ) == (second, first)


def test_build_artwork_review_summary_counts_items_and_slots() -> None:
    summary = build_artwork_review_summary(
        ("missing", "second", "first"),
        {
            "first": {"candidate_ids": {"grid": "grid-1", "hero": "hero-1"}},
            "second": {"candidate_ids": {"logo": "logo-2", "bogus": "ignored"}},
        },
    )

    assert summary.selected_item_count == 3
    assert summary.pending_item_ids == ("second", "first")
    assert summary.pending_item_count == 2
    assert summary.pending_slot_count == 3


def _event(
    job_id: str,
    state: JobState,
    *,
    result: dict | None = None,
    message: str = "",
    error: str = "",
) -> JobEvent:
    return JobEvent(
        job_id=job_id,
        item_id="ignored-the-queue-uses-its-own-mapping",
        state=state,
        progress=0.0,
        message=message,
        error=error,
        result=result or {},
    )


def test_review_queue_ignores_events_for_jobs_it_does_not_own() -> None:
    queue = ArtworkReviewQueue()
    queue.track("job-1", "item-1")

    assert queue.tracks("job-1") is True
    assert queue.tracks("job-other") is False
    assert queue.handle_event(_event("job-other", JobState.SUCCEEDED)) is None


def test_review_queue_reports_running_progress_without_finishing_the_job() -> None:
    queue = ArtworkReviewQueue()
    queue.track("job-1", "item-1")

    update = queue.handle_event(_event("job-1", JobState.RUNNING, message="Searching providers"))

    assert update is not None
    assert (update.item_id, update.terminal, update.needs_review) == ("item-1", False, False)
    assert update.status == "Searching providers"
    assert queue.active_job_count == 1


def test_review_queue_holds_needs_review_results_for_a_human_decision() -> None:
    queue = ArtworkReviewQueue()
    queue.track("job-1", "item-1")
    result = {
        "item_id": "item-1",
        "decision": "review",
        "requested_slots": ["grid", "hero"],
        "candidate_ids": {"grid": "grid-1", "hero": "hero-1"},
    }

    update = queue.handle_event(_event("job-1", JobState.NEEDS_REVIEW, result=result))

    assert update is not None
    assert (update.terminal, update.needs_review) == (True, True)
    assert update.status == "Artwork review (grid, hero)"
    assert queue.pending_item_ids == ("item-1",)
    assert queue.pending_slot_count == 2
    assert queue.result_for("item-1") == result
    # The job is finished, so it no longer counts as in flight.
    assert queue.active_job_count == 0


def test_review_queue_does_not_hold_decisions_that_persisted_themselves() -> None:
    queue = ArtworkReviewQueue()
    queue.track("accepted", "item-1")
    queue.track("rejected", "item-2")

    accepted = queue.handle_event(
        _event(
            "accepted",
            JobState.SUCCEEDED,
            result={"item_id": "item-1", "decision": "auto_accept", "requested_slots": ["grid"]},
        ),
        accepted=1,
    )
    rejected = queue.handle_event(
        _event(
            "rejected",
            JobState.SKIPPED,
            result={"item_id": "item-2", "decision": "reject", "requested_slots": ["grid"]},
        ),
        rejected=1,
    )

    assert accepted is not None and rejected is not None
    assert accepted.needs_review is False
    assert rejected.needs_review is False
    assert accepted.status == "Artwork auto_accept (grid); saved 1 accepted/0 rejected"
    assert rejected.status == "Artwork reject (grid); saved 0 accepted/1 rejected"
    assert queue.pending_item_ids == ()


def test_review_queue_surfaces_failures_instead_of_queueing_them_for_review() -> None:
    queue = ArtworkReviewQueue()
    queue.track("job-1", "item-1")

    update = queue.handle_event(_event("job-1", JobState.FAILED, error="provider timeout"))

    assert update is not None
    assert update.terminal is True
    assert update.needs_review is False
    assert update.status == "Artwork search failed: provider timeout"
    assert queue.pending_item_ids == ()


def test_review_queue_discard_and_clear_release_pending_items() -> None:
    queue = ArtworkReviewQueue()
    for index in (1, 2):
        queue.track(f"job-{index}", f"item-{index}")
        queue.handle_event(
            _event(
                f"job-{index}",
                JobState.NEEDS_REVIEW,
                result={"item_id": f"item-{index}", "decision": "review", "candidate_ids": {"grid": "g"}},
            )
        )

    assert len(queue.results_for(("item-1", "item-2"))) == 2
    assert queue.discard("item-1") is True
    assert queue.discard("item-1") is False
    assert queue.pending_item_ids == ("item-2",)
    assert queue.clear() == 1
    assert queue.pending_item_ids == ()


def test_artwork_queue_progress_text_distinguishes_running_from_finished() -> None:
    assert artwork_queue_progress_text(2, 1) == "Artwork search: 2 job(s) running, 1 awaiting review."
    assert artwork_queue_progress_text(0, 3) == "Artwork search finished. 3 game(s) awaiting review."
    assert artwork_queue_progress_text(0, 0) == "Artwork search finished. Nothing is awaiting review."


def test_real_coordinator_results_land_in_the_review_queue() -> None:
    """End-to-end: the policy routes a plausible match to review, not to disk."""
    queue = ArtworkReviewQueue()
    item = BulkArtworkItem("item-1", "Example")
    outcome = ArtworkSearchOutcome(
        # Scored below ArtworkMatchPolicy's automatic thresholds, as a
        # name-resolved match from a mid-trust provider would be.
        evidence=ArtworkEvidence(
            identity_score=78,
            set_coherence_score=90,
            source="real-providers",
        ),
        found_slots=frozenset({"grid"}),
        provider="real-providers",
        candidate_ids={"grid": "grid-1"},
    )
    selection = SelectionState(selected_ids={"item-1"})

    with BackgroundJobQueue(max_workers=1) as jobs:
        submission = BulkArtworkCoordinator(jobs).submit_selected(
            selection,
            ["item-1"],
            {"item-1": item},
            lambda *args: outcome,
            mode=ArtworkSearchMode.ALL_UNLOCKED,
        )
        for job in submission.jobs:
            queue.track(job.job_id, job.item_id)
        jobs.wait_for_idle(timeout=10)
        events = jobs.drain_events()

    updates = [update for event in events if (update := queue.handle_event(event)) is not None]

    assert [job.item_id for job in submission.jobs] == ["item-1"]
    assert any(update.needs_review for update in updates)
    assert queue.pending_item_ids == ("item-1",)
    assert queue.result_for("item-1")["decision"] == "review"


def _stored_item(external_id: str, title: str) -> SourceLibraryItem:
    return SourceLibraryItem(
        stable_id=stable_source_item_id("epic", external_id=external_id),
        source="epic",
        external_id=external_id,
        title=title,
        install_path=rf"C:\Games\{title}",
        launch_target=rf"C:\Games\{title}\{title}.exe",
        platform="windows",
        size_bytes=1024,
        launch_target_exists=True,
    )


def test_accepting_a_queued_review_locks_the_slot_and_releases_the_item() -> None:
    """Accept persists a local lock only — never a write into Steam."""
    with tempfile.TemporaryDirectory() as tmp:
        store = LibraryStore(Path(tmp) / "library.sqlite3")
        stored = _stored_item("one", "Example")
        store.replace_source_snapshot("epic", [stored])
        controller = LibraryController(store)
        try:
            queue = ArtworkReviewQueue()
            queue.track("job-1", stored.stable_id)
            queue.handle_event(
                _event(
                    "job-1",
                    JobState.NEEDS_REVIEW,
                    result={
                        "item_id": stored.stable_id,
                        "decision": "review",
                        "requested_slots": ["grid"],
                        "provider": "real-providers",
                        "candidate_ids": {"grid": "grid-1"},
                        "details": {"validated_files": {"grid": {"path": r"C:\cache\grid-1.png"}}},
                    },
                )
            )

            result = queue.result_for(stored.stable_id)
            assert result is not None
            persistence = controller.accept_artwork_review_result(result)
            queue.discard(stored.stable_id)

            assert persistence.accepted == 1
            assert queue.pending_item_ids == ()
            locks = store.list_artwork_locks(stored.stable_id)
            assert [(lock.slot, lock.candidate_id) for lock in locks] == [("grid", "grid-1")]
            assert locks[0].local_path == r"C:\cache\grid-1.png"
        finally:
            controller.close(wait=False, cancel_pending=True)


def test_rejecting_a_queued_review_records_the_candidate_and_locks_nothing() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        store = LibraryStore(Path(tmp) / "library.sqlite3")
        stored = _stored_item("one", "Example")
        store.replace_source_snapshot("epic", [stored])
        controller = LibraryController(store)
        try:
            queue = ArtworkReviewQueue()
            queue.track("job-1", stored.stable_id)
            queue.handle_event(
                _event(
                    "job-1",
                    JobState.NEEDS_REVIEW,
                    result={
                        "item_id": stored.stable_id,
                        "decision": "review",
                        "provider": "real-providers",
                        "candidate_ids": {"grid": "grid-1"},
                    },
                )
            )

            result = queue.result_for(stored.stable_id)
            assert result is not None
            persistence = controller.reject_artwork_review_result(result)
            queue.discard(stored.stable_id)

            assert persistence.rejected == 1
            assert store.list_artwork_locks(stored.stable_id) == []
            rejected = store.list_rejected_matches(stored.stable_id)
            assert [(match.slot, match.candidate_id) for match in rejected] == [("grid", "grid-1")]
        finally:
            controller.close(wait=False, cancel_pending=True)


if __name__ == "__main__":
    test_build_artwork_review_rows_preserves_item_order_and_slot_metadata()
    test_review_result_slot_count_only_counts_known_slots()
    test_artwork_review_action_messages()
    test_artwork_review_dialog_text_helpers()
    test_review_clear_messages()
    test_pending_review_item_ids_preserves_selected_order()
    test_selected_artwork_review_results_preserves_selected_order()
    test_build_artwork_review_summary_counts_items_and_slots()
    test_review_queue_ignores_events_for_jobs_it_does_not_own()
    test_review_queue_reports_running_progress_without_finishing_the_job()
    test_review_queue_holds_needs_review_results_for_a_human_decision()
    test_review_queue_does_not_hold_decisions_that_persisted_themselves()
    test_review_queue_surfaces_failures_instead_of_queueing_them_for_review()
    test_review_queue_discard_and_clear_release_pending_items()
    test_artwork_queue_progress_text_distinguishes_running_from_finished()
    test_real_coordinator_results_land_in_the_review_queue()
    test_accepting_a_queued_review_locks_the_slot_and_releases_the_item()
    test_rejecting_a_queued_review_records_the_candidate_and_locks_nothing()
    print("Artwork review workspace tests passed.")
