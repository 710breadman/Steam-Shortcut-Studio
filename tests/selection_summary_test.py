from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from steam_shortcut_studio.selection_summary import build_mixed_selection_summary, build_selection_summary  # noqa: E402


def test_selection_summary_formats_empty_state() -> None:
    summary = build_selection_summary((), ())

    assert summary.label == "0 selected"


def test_selection_summary_counts_total_and_visible_selection() -> None:
    summary = build_selection_summary(
        (True, False, True, True),
        (0, 2, 8),
    )

    assert summary.total == 4
    assert summary.selected == 3
    assert summary.visible_total == 3
    assert summary.visible_selected == 2
    assert summary.label == "3/4 selected; 2/3 visible"


def test_mixed_selection_summary_prefers_controller_ids_for_persistent_rows() -> None:
    summary = build_mixed_selection_summary(
        (True, True, False, False),
        ("stored-one", "", "stored-two", ""),
        (0, 1, 2),
        frozenset({"stored-two"}),
    )

    assert summary.total == 4
    assert summary.selected == 2
    assert summary.visible_total == 3
    assert summary.visible_selected == 2
    assert summary.label == "2/4 selected; 2/3 visible"


if __name__ == "__main__":
    test_selection_summary_formats_empty_state()
    test_selection_summary_counts_total_and_visible_selection()
    test_mixed_selection_summary_prefers_controller_ids_for_persistent_rows()
    print("Selection summary tests passed.")
