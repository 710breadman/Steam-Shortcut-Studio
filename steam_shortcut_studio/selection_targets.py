from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from .models import DetectedGame
from .ui_library_adapter import library_item_id_for_game

SelectionTarget = Literal["needing_artwork", "new_nonsteam"]


@dataclass(frozen=True, slots=True)
class SelectionTargetPlan:
    target: SelectionTarget
    selected_indices: tuple[int, ...]
    persistent_item_ids_to_clear: tuple[str, ...]

    @property
    def selected_count(self) -> int:
        return len(self.selected_indices)


def game_matches_selection_target(game: DetectedGame, target: SelectionTarget) -> bool:
    if target == "needing_artwork":
        return game.artwork.selected_count() < len(game.artwork.slot_names())
    return not game.is_native_steam_game and game.existing_appid is None


def build_selection_target_plan(
    games: Sequence[DetectedGame],
    target: SelectionTarget,
) -> SelectionTargetPlan:
    selected_indices: list[int] = []
    persistent_item_ids_to_clear: list[str] = []
    for index, game in enumerate(games):
        item_id = library_item_id_for_game(game)
        if item_id:
            persistent_item_ids_to_clear.append(item_id)
            continue
        if game_matches_selection_target(game, target):
            selected_indices.append(index)
    return SelectionTargetPlan(
        target=target,
        selected_indices=tuple(selected_indices),
        persistent_item_ids_to_clear=tuple(persistent_item_ids_to_clear),
    )


def apply_selection_target_plan(
    games: Sequence[DetectedGame],
    plan: SelectionTargetPlan,
) -> None:
    selected_indices = set(plan.selected_indices)
    for index, game in enumerate(games):
        if not library_item_id_for_game(game):
            game.selected = index in selected_indices
