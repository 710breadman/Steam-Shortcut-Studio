from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from steam_shortcut_studio.artwork_search_service import (  # noqa: E402
    ArtworkProviderSearchService,
    add_steamgriddb_assets_to_slots,
)
from steam_shortcut_studio.models import ArtworkAsset, DetectedGame  # noqa: E402


class FakeSteamGridClient:
    configured = True

    def __init__(self) -> None:
        self.asset_calls: list[tuple[int, str]] = []
        self.platform_calls: list[tuple[str, int | str, str]] = []
        self.search_calls: list[str] = []

    def get_assets(self, game_id: int, kind: str) -> list[ArtworkAsset]:
        self.asset_calls.append((game_id, kind))
        return [
            ArtworkAsset(
                kind=kind,
                asset_id=f"sgdb-{game_id}-{kind}",
                url=f"https://example.invalid/{game_id}/{kind}.png",
                width=600 if kind == "grid" else 1920,
                height=900 if kind == "grid" else 1080,
                score=9000,
            )
        ]

    def get_assets_by_platform(self, platform: str, external_id: int | str, kind: str) -> list[ArtworkAsset]:
        self.platform_calls.append((platform, external_id, kind))
        return []

    def get_game(self, game_id: int) -> dict[str, Any]:
        return {"id": game_id, "name": "Fixture Game", "release_date": "2024-01-01"}

    def get_game_by_steam_appid(self, appid: int) -> dict[str, Any]:
        return {"id": appid + 1}

    def search_games(self, term: str, use_cache: bool = True) -> list[dict[str, Any]]:
        self.search_calls.append(term)
        return [{"id": 321, "name": "Fixture Game", "release_date": "2024-01-01"}]


def _game() -> DetectedGame:
    game = DetectedGame(title="Fixture Game", root_path=Path("C:/Games/Fixture Game"))
    game.metadata.release_year = "2024"
    return game


def test_collect_assets_uses_selected_sgdb_id_and_updates_metadata() -> None:
    client = FakeSteamGridClient()
    service = ArtworkProviderSearchService(
        find_steam_app_func=lambda _term: None,
        wikimedia_artwork_assets_func=lambda _term: {"grid": [], "wide": [], "hero": [], "logo": [], "icon": []},
        rawg_artwork_assets_func=lambda *_args, **_kwargs: {"grid": [], "wide": [], "hero": [], "logo": [], "icon": []},
    )
    game = _game()

    assets = service.collect_assets(
        game,
        "Fixture Game",
        client,
        enabled_sources={"steam": False, "steamgriddb": True, "wikimedia": False, "rawg": False},
        sgdb_game_id=123,
    )

    assert game.metadata.sgdb_id == 123
    assert client.asset_calls == [(123, "grid"), (123, "hero"), (123, "logo"), (123, "icon")]
    assert assets["grid"][0].asset_id == "sgdb-123-grid"
    assert assets["wide"][0].asset_id == "sgdb-123-grid-wide-fallback"


def test_collect_assets_adds_steam_store_media_and_dedupes_urls() -> None:
    client = FakeSteamGridClient()
    duplicate = ArtworkAsset(kind="wide", asset_id="official-wide", url="https://example.invalid/shared.png")
    duplicate_later = ArtworkAsset(kind="wide", asset_id="store-wide", url="https://example.invalid/shared.png")
    service = ArtworkProviderSearchService(
        find_steam_app_func=lambda _term: {"id": 456, "name": "Fixture Game"},
        official_steam_assets_func=lambda _appid, _name: {"grid": [], "wide": [duplicate], "hero": [], "logo": [], "icon": []},
        get_steam_app_details_func=lambda _appid: {"header_image": "present"},
        steam_store_media_assets_func=lambda _appid, _name, _detail: {"grid": [], "wide": [duplicate_later], "hero": [], "logo": [], "icon": []},
        wikimedia_artwork_assets_func=lambda _term: {"grid": [], "wide": [], "hero": [], "logo": [], "icon": []},
        rawg_artwork_assets_func=lambda *_args, **_kwargs: {"grid": [], "wide": [], "hero": [], "logo": [], "icon": []},
    )
    game = _game()

    assets = service.collect_assets(
        game,
        "Fixture Game",
        client,
        enabled_sources={"steam": True, "steamgriddb": False, "wikimedia": False, "rawg": False},
    )

    assert game.metadata.steam_appid == 456
    assert [asset.asset_id for asset in assets["wide"]] == ["official-wide"]
    assert client.asset_calls == []
    assert client.search_calls == []


def _grid(asset_id: str, width: int, height: int) -> ArtworkAsset:
    return ArtworkAsset(kind="grid", asset_id=asset_id, url=f"https://x.invalid/{asset_id}.png",
                        width=width, height=height)


def _empty_slots() -> dict[str, list[ArtworkAsset]]:
    return {kind: [] for kind in ("grid", "wide", "hero", "logo", "icon")}


def test_capsule_shapes_are_sorted_into_the_slot_they_actually_fit() -> None:
    """SteamGridDB returns every capsule shape under one "grid" kind."""
    slots = _empty_slots()
    add_steamgriddb_assets_to_slots(slots, "grid", [
        _grid("square", 1024, 1024),
        _grid("portrait", 600, 900),
        _grid("capsule", 920, 430),
    ])

    assert [a.asset_id for a in slots["grid"]] == ["portrait"]
    assert [a.asset_id for a in slots["wide"]] == ["capsule-wide"]


def test_a_square_never_outranks_correctly_shaped_art() -> None:
    """SteamGridDB sorts by its own popularity score, so a square can arrive
    first; it must still lose to art that is actually the right shape."""
    slots = _empty_slots()
    add_steamgriddb_assets_to_slots(slots, "grid", [
        _grid("popular-square", 1024, 1024),
        _grid("portrait", 660, 930),
        _grid("capsule", 920, 430),
    ])

    assert slots["grid"][0].asset_id == "portrait"
    assert slots["wide"][0].asset_id == "capsule-wide"


def test_a_square_is_used_only_when_nothing_better_exists() -> None:
    slots = _empty_slots()
    add_steamgriddb_assets_to_slots(slots, "grid", [_grid("square", 1024, 1024)])

    assert [a.asset_id for a in slots["grid"]] == ["square"]
    assert [a.asset_id for a in slots["wide"]] == ["square-wide-fallback"]


def test_assets_without_dimensions_still_reach_a_slot() -> None:
    slots = _empty_slots()
    add_steamgriddb_assets_to_slots(slots, "grid", [_grid("unknown", 0, 0)])

    assert slots["grid"] or slots["wide"]


def test_non_grid_kinds_pass_through_untouched() -> None:
    slots = _empty_slots()
    hero = ArtworkAsset(kind="hero", asset_id="h", url="https://x.invalid/h.png", width=1920, height=620)
    add_steamgriddb_assets_to_slots(slots, "hero", [hero])

    assert slots["hero"] == [hero]


if __name__ == "__main__":
    test_collect_assets_uses_selected_sgdb_id_and_updates_metadata()
    test_collect_assets_adds_steam_store_media_and_dedupes_urls()
    test_capsule_shapes_are_sorted_into_the_slot_they_actually_fit()
    test_a_square_never_outranks_correctly_shaped_art()
    test_a_square_is_used_only_when_nothing_better_exists()
    test_assets_without_dimensions_still_reach_a_slot()
    test_non_grid_kinds_pass_through_untouched()
    print("Artwork search service tests passed.")
