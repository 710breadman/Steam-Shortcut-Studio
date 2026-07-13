from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from steam_shortcut_studio.scan_plan import build_combined_scan_plan  # noqa: E402


def test_combined_scan_plan_counts_enabled_sources() -> None:
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        plan = build_combined_scan_plan(
            r"C:\Steam",
            str(root),
            is_valid_steam_path=lambda path: str(path) == r"C:\Steam",
        )

    assert plan.has_work is True
    assert plan.steam_ready is True
    assert plan.folder_ready is True
    assert plan.total_steps == 5


def test_combined_scan_plan_rejects_missing_sources() -> None:
    plan = build_combined_scan_plan(
        "",
        r"Z:\missing-games",
        is_valid_steam_path=lambda _path: False,
    )

    assert plan.has_work is False
    assert plan.steam_path is None
    assert plan.folder_ready is False
    assert plan.total_steps == 1


if __name__ == "__main__":
    test_combined_scan_plan_counts_enabled_sources()
    test_combined_scan_plan_rejects_missing_sources()
    print("Combined scan plan tests passed.")
