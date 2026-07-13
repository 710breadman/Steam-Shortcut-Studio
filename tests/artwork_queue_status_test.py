from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from steam_shortcut_studio.artwork_queue_status import (  # noqa: E402
    artwork_cleared_message,
    artwork_editor_opened_message,
    artwork_queue_item_status,
    artwork_queue_submission_message,
    artwork_preview_refreshed_message,
    custom_artwork_selected_message,
)


def test_artwork_queue_status_messages() -> None:
    assert artwork_queue_item_status("persistent artwork plan") == "Queued persistent artwork plan"
    assert artwork_queue_submission_message(3, "artwork review retry") == "Queued 3 artwork review retry job(s)."


def test_artwork_slot_status_messages() -> None:
    assert custom_artwork_selected_message("grid", "Game") == "Custom grid artwork selected for Game."
    assert artwork_cleared_message("logo", "Game") == "Cleared logo artwork for Game."
    assert artwork_preview_refreshed_message("hero", "Game") == "Refreshed hero artwork preview for Game."
    assert artwork_editor_opened_message("icon", "Paint") == "Opened icon artwork in Paint."


if __name__ == "__main__":
    test_artwork_queue_status_messages()
    test_artwork_slot_status_messages()
    print("Artwork queue status tests passed.")
