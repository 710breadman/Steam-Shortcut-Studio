from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from steam_shortcut_studio.artwork_review_workspace import (  # noqa: E402
    build_artwork_review_rows,
    pending_review_item_ids,
    review_result_slot_count,
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


def test_pending_review_item_ids_preserves_selected_order() -> None:
    assert pending_review_item_ids(
        ("missing", "second", "first"),
        {
            "first": {"candidate_ids": {"grid": "grid-1"}},
            "second": {"candidate_ids": {"grid": "grid-2"}},
        },
    ) == ("second", "first")


if __name__ == "__main__":
    test_build_artwork_review_rows_preserves_item_order_and_slot_metadata()
    test_review_result_slot_count_only_counts_known_slots()
    test_pending_review_item_ids_preserves_selected_order()
    print("Artwork review workspace tests passed.")
