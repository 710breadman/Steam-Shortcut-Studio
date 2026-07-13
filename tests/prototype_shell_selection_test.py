from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from prototypes.modern_shell import MockGame, initial_selection_state  # noqa: E402
from steam_shortcut_studio.selection import SelectionState  # noqa: E402


def test_initial_selection_state_uses_shared_selection_model() -> None:
    games = [
        MockGame("one", "One", "Epic", "Windows", "-", "1 GB", "Ready"),
        MockGame("two", "Two", "Steam", "Windows", "-", "2 GB", "Review"),
    ]

    selection = initial_selection_state(games)

    assert isinstance(selection, SelectionState)
    assert selection.active_id == "one"
    assert selection.selected_ids == {"one"}


def test_initial_selection_state_handles_empty_library() -> None:
    selection = initial_selection_state([])

    assert selection.active_id is None
    assert selection.selected_ids == set()


if __name__ == "__main__":
    test_initial_selection_state_uses_shared_selection_model()
    test_initial_selection_state_handles_empty_library()
    print("Prototype shell selection tests passed.")
