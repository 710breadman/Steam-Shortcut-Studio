from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from .models import DetectedGame
from .ui_library_adapter import apply_library_selection_to_games, is_persistent_library_game, library_item_ids_for_games


@dataclass(slots=True)
class SelectionBulkController:
    library_controller: object

    def select_scope(self, games: list[DetectedGame], indices: Iterable[int], selected: bool) -> int:
        scope = tuple(index for index in indices if 0 <= index < len(games))
        item_ids = library_item_ids_for_games(games, scope)
        if hasattr(self.library_controller, "set_items_selected"):
            self.library_controller.set_items_selected(item_ids, selected)
        for index in scope:
            game = games[index]
            if not is_persistent_library_game(game):
                game.selected = selected
        self._mirror(games)
        return len(scope)

    def invert_scope(self, games: list[DetectedGame], indices: Iterable[int]) -> int:
        scope = tuple(index for index in indices if 0 <= index < len(games))
        item_ids = library_item_ids_for_games(games, scope)
        if hasattr(self.library_controller, "toggle_items"):
            self.library_controller.toggle_items(item_ids)
        for index in scope:
            game = games[index]
            if not is_persistent_library_game(game):
                game.selected = not game.selected
        self._mirror(games)
        return len(scope)

    def _mirror(self, games: list[DetectedGame]) -> None:
        if hasattr(self.library_controller, "snapshot"):
            try:
                apply_library_selection_to_games(games, self.library_controller.snapshot().selected_ids)
            except Exception:
                pass


def apply_scope_selection(
    games: list[DetectedGame],
    controller: object,
    indices: Iterable[int],
    selected: bool,
) -> int:
    return SelectionBulkController(controller).select_scope(games, indices, selected)


def invert_scope_selection(
    games: list[DetectedGame],
    controller: object,
    indices: Iterable[int],
) -> int:
    return SelectionBulkController(controller).invert_scope(games, indices)
