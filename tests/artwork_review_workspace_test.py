from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from steam_shortcut_studio.artwork_review_workspace import (  # noqa: E402
    artwork_rejection_clear_message,
    artwork_review_action_message,
    build_artwork_review_rows,
    build_artwork_review_summary,
    pending_review_item_ids,
    review_result_slot_count,
    source_review_clear_message,
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


if __name__ == "__main__":
    test_build_artwork_review_rows_preserves_item_order_and_slot_metadata()
    test_review_result_slot_count_only_counts_known_slots()
    test_artwork_review_action_messages()
    test_review_clear_messages()
    test_pending_review_item_ids_preserves_selected_order()
    test_build_artwork_review_summary_counts_items_and_slots()
    print("Artwork review workspace tests passed.")
