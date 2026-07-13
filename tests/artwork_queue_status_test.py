from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from steam_shortcut_studio.artwork_queue_status import (  # noqa: E402
    artwork_queue_item_status,
    artwork_queue_submission_message,
)


def test_artwork_queue_status_messages() -> None:
    assert artwork_queue_item_status("persistent artwork plan") == "Queued persistent artwork plan"
    assert artwork_queue_submission_message(3, "artwork review retry") == "Queued 3 artwork review retry job(s)."


if __name__ == "__main__":
    test_artwork_queue_status_messages()
    print("Artwork queue status tests passed.")
