from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from steam_shortcut_studio.models import DetectedGame, GameMetadata  # noqa: E402
from steam_shortcut_studio.selection_bulk_controller import apply_scope_selection, invert_scope_selection  # noqa: E402
from steam_shortcut_studio.ui_library_adapter import LIBRARY_ITEM_ID_META  # noqa: E402


class _Controller:
    def __init__(self) -> None:
        self.selected: list[tuple[str, bool]] = []
        self.toggled: list[tuple[str, ...]] = []
        self.selected_ids: set[str] = set()

    def set_items_selected(self, item_ids: tuple[str, ...], selected: bool) -> None:
        self.selected.extend((item_id, selected) for item_id in item_ids)
        if selected:
            self.selected_ids.update(item_ids)
        else:
            self.selected_ids.difference_update(item_ids)

    def toggle_items(self, item_ids: tuple[str, ...]) -> None:
        self.toggled.append(item_ids)
        for item_id in item_ids:
            if item_id in self.selected_ids:
                self.selected_ids.remove(item_id)
            else:
                self.selected_ids.add(item_id)

    def snapshot(self):
        return type("Snapshot", (), {"selected_ids": frozenset(self.selected_ids)})()


def _stored_game(item_id: str, title: str, *, selected: bool = False) -> DetectedGame:
    return DetectedGame(
        title=title,
        root_path=Path(),
        selected=selected,
        metadata=GameMetadata(extra={LIBRARY_ITEM_ID_META: item_id}),
        source_type="library",
    )


def test_apply_scope_selection_updates_controller_and_loose_rows() -> None:
    controller = _Controller()
    stored = _stored_game("stored", "Stored")
    loose = DetectedGame(title="Loose", root_path=Path(), selected=False)
    games = [stored, loose]

    count = apply_scope_selection(games, controller, [0, 1], True)

    assert count == 2
    assert controller.selected == [("stored", True)]
    assert stored.selected is True
    assert loose.selected is True


def test_invert_scope_selection_toggles_controller_and_loose_rows() -> None:
    controller = _Controller()
    stored = _stored_game("stored", "Stored", selected=True)
    loose = DetectedGame(title="Loose", root_path=Path(), selected=False)
    controller.selected_ids.add("stored")
    games = [stored, loose]

    count = invert_scope_selection(games, controller, [0, 1])

    assert count == 2
    assert controller.toggled == [("stored",)]
    assert stored.selected is False
    assert loose.selected is True


if __name__ == "__main__":
    test_apply_scope_selection_updates_controller_and_loose_rows()
    test_invert_scope_selection_toggles_controller_and_loose_rows()
    print("Selection bulk controller tests passed.")
