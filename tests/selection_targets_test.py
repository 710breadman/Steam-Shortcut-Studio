from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from steam_shortcut_studio.models import ArtworkAsset, ArtworkSelection, DetectedGame, GameMetadata  # noqa: E402
from steam_shortcut_studio.selection_targets import (  # noqa: E402
    apply_selection_target_plan,
    build_selection_target_plan,
    game_matches_selection_target,
)
from steam_shortcut_studio.ui_library_adapter import LIBRARY_ITEM_ID_META  # noqa: E402


def _game(title: str, **kwargs: object) -> DetectedGame:
    return DetectedGame(title=title, root_path=Path(r"C:\Games") / title, **kwargs)


def test_selection_target_plan_finds_nonpersistent_games_needing_artwork() -> None:
    complete_art = ArtworkSelection(
        grid=ArtworkAsset(kind="grid", asset_id="grid", url=""),
        wide=ArtworkAsset(kind="wide", asset_id="wide", url=""),
        hero=ArtworkAsset(kind="hero", asset_id="hero", url=""),
        logo=ArtworkAsset(kind="logo", asset_id="logo", url=""),
        icon=ArtworkAsset(kind="icon", asset_id="icon", url=""),
    )
    games = [
        _game("Needs Art"),
        _game("Ready Art", artwork=complete_art),
        _game("Persistent", metadata=GameMetadata(extra={LIBRARY_ITEM_ID_META: "item-1"})),
    ]

    plan = build_selection_target_plan(games, "needing_artwork")

    assert plan.selected_indices == (0,)
    assert plan.selected_count == 1
    assert plan.persistent_item_ids_to_clear == ("item-1",)


def test_selection_target_plan_finds_new_nonsteam_shortcuts() -> None:
    games = [
        _game("New Folder"),
        _game("Existing Shortcut", existing_appid=123),
        _game("Steam", source_type="steam", steam_appid=456),
        _game("Persistent", metadata=GameMetadata(extra={LIBRARY_ITEM_ID_META: "item-2"})),
    ]

    plan = build_selection_target_plan(games, "new_nonsteam")

    assert plan.selected_indices == (0,)
    assert plan.persistent_item_ids_to_clear == ("item-2",)


def test_apply_selection_target_plan_updates_only_nonpersistent_rows() -> None:
    games = [
        _game("New Folder", selected=False),
        _game("Existing Shortcut", existing_appid=123, selected=True),
        _game("Persistent", selected=True, metadata=GameMetadata(extra={LIBRARY_ITEM_ID_META: "item-3"})),
    ]
    plan = build_selection_target_plan(games, "new_nonsteam")

    apply_selection_target_plan(games, plan)

    assert [game.selected for game in games] == [True, False, True]


def test_game_matches_selection_target() -> None:
    assert game_matches_selection_target(_game("Needs Art"), "needing_artwork") is True
    assert game_matches_selection_target(_game("New Folder"), "new_nonsteam") is True
    assert game_matches_selection_target(_game("Steam", source_type="steam", steam_appid=1), "new_nonsteam") is False


if __name__ == "__main__":
    test_selection_target_plan_finds_nonpersistent_games_needing_artwork()
    test_selection_target_plan_finds_new_nonsteam_shortcuts()
    test_apply_selection_target_plan_updates_only_nonpersistent_rows()
    test_game_matches_selection_target()
    print("Selection target tests passed.")
