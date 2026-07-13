from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from steam_shortcut_studio.selection_actions import selection_action_label, selection_action_result, selection_target_label  # noqa: E402


def test_selection_action_labels_all_scope() -> None:
    assert selection_action_label("select", "all", 4) == "Selected 4 all game row(s)."
    assert selection_action_label("clear", "all", 4) == "Cleared 4 all game row(s)."
    assert selection_action_label("invert", "all", 4) == "Inverted 4 game selection(s)."


def test_selection_action_labels_visible_scope() -> None:
    assert selection_action_label("select", "visible", 3) == "Selected 3 visible game row(s)."
    assert selection_action_label("clear", "visible", 3) == "Cleared 3 visible game row(s)."
    assert selection_action_label("invert", "visible", 3) == "Inverted 3 visible game row(s)."


def test_selection_action_labels_current_filter_scope() -> None:
    assert selection_action_label("select", "current_filter", 2) == "Selected 2 row(s) matching current filter."
    assert selection_action_label("clear", "current_filter", 2) == "Cleared 2 row(s) matching current filter."
    assert selection_action_label("invert", "current_filter", 2) == "Inverted 2 row(s) matching current filter."


def test_selection_action_result_label() -> None:
    result = selection_action_result("invert", "visible", 5)
    assert result.action == "invert"
    assert result.scope == "visible"
    assert result.row_count == 5
    assert result.label == "Inverted 5 visible game row(s)."


def test_selection_target_labels() -> None:
    assert selection_target_label("needing_artwork", 2) == "Selected 2 game(s) needing artwork."
    assert selection_target_label("new_nonsteam", 3) == "Selected 3 new non-Steam shortcut(s)."


if __name__ == "__main__":
    test_selection_action_labels_all_scope()
    test_selection_action_labels_visible_scope()
    test_selection_action_labels_current_filter_scope()
    test_selection_action_result_label()
    test_selection_target_labels()
    print("Selection action tests passed.")
