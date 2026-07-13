from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from steam_shortcut_studio.metadata_targets import (  # noqa: E402
    metadata_refresh_indices,
    selected_or_current_indices,
)


def test_selected_or_current_prefers_selected_indices() -> None:
    assert selected_or_current_indices((False, True, True), 0) == (1, 2)


def test_selected_or_current_falls_back_to_current_index() -> None:
    assert selected_or_current_indices((False, False, False), 1) == (1,)
    assert selected_or_current_indices((False,), 8) == ()


def test_metadata_refresh_indices_skip_native_steam_games() -> None:
    assert metadata_refresh_indices(
        (True, True, False, True),
        (False, True, False, False),
        None,
    ) == (0, 3)


if __name__ == "__main__":
    test_selected_or_current_prefers_selected_indices()
    test_selected_or_current_falls_back_to_current_index()
    test_metadata_refresh_indices_skip_native_steam_games()
    print("Metadata target tests passed.")
