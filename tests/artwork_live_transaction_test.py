from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PIL import Image  # noqa: E402

from steam_shortcut_studio.artwork import (  # noqa: E402
    copy_game_artwork_to_steam,
    plan_game_artwork_transaction,
)
from steam_shortcut_studio.image_validation import ArtworkValidationError  # noqa: E402
from steam_shortcut_studio.models import ArtworkAsset, DetectedGame, SteamProfile  # noqa: E402


def _image(path: Path, size: tuple[int, int], color: tuple[int, int, int]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, color).save(path)
    return path


def _profile(root: Path) -> SteamProfile:
    return SteamProfile(
        user_id="123",
        config_dir=root / "Steam" / "userdata" / "123" / "config",
        shortcuts_path=root / "Steam" / "userdata" / "123" / "config" / "shortcuts.vdf",
        grid_dir=root / "Steam" / "userdata" / "123" / "config" / "grid",
    )


def _native_game(root: Path) -> DetectedGame:
    return DetectedGame(
        title="Native Example",
        root_path=root / "Steam" / "steamapps" / "common" / "Native Example",
        selected=True,
        source_type="steam",
        steam_appid=424242,
    )


def test_live_artwork_copy_commits_fallback_slots_and_removes_stale_variants() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        profile = _profile(root)
        source = _image(root / "cache" / "grid.png", (600, 900), (10, 20, 30))
        game = _native_game(root)
        game.artwork.grid = ArtworkAsset(
            kind="grid",
            asset_id="grid",
            url="https://example.invalid/grid.png",
            width=600,
            height=900,
            local_path=source,
        )
        stale = [
            _image(profile.grid_dir / "424242p.jpg", (600, 900), (100, 0, 0)),
            _image(profile.grid_dir / "424242.jpg", (920, 430), (0, 100, 0)),
            _image(profile.grid_dir / "424242_hero.jpg", (1920, 620), (0, 0, 100)),
            _image(profile.grid_dir / "424242_icon.jpg", (64, 64), (100, 100, 0)),
        ]

        writes, removals = plan_game_artwork_transaction(game, profile)
        copied = copy_game_artwork_to_steam(game, profile)

        assert {request.slot for request in writes} == {"grid", "wide", "hero", "icon"}
        assert set(removals) == {path.resolve() for path in stale}
        assert {path.name for path in copied} == {
            "424242p.png",
            "424242.png",
            "424242_hero.png",
            "424242_icon.png",
        }
        assert all(path.read_bytes() == source.read_bytes() for path in copied)
        assert all(not path.exists() for path in stale)


def test_invalid_live_artwork_is_blocked_before_existing_target_changes() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        profile = _profile(root)
        target = _image(profile.grid_dir / "424242p.png", (600, 900), (50, 60, 70))
        original = target.read_bytes()
        invalid = root / "cache" / "invalid.png"
        invalid.parent.mkdir(parents=True)
        invalid.write_text("<html>provider error</html>", encoding="utf-8")
        game = _native_game(root)
        game.artwork.grid = ArtworkAsset(
            kind="grid",
            asset_id="bad",
            url="https://example.invalid/invalid.png",
            width=600,
            height=900,
            local_path=invalid,
        )

        try:
            copy_game_artwork_to_steam(game, profile)
        except ArtworkValidationError:
            pass
        else:
            raise AssertionError("Invalid production artwork was written")

        assert target.read_bytes() == original
        assert not (profile.grid_dir / "424242.png").exists()
        assert not (profile.grid_dir / "424242_hero.png").exists()
        assert not (profile.grid_dir / "424242_icon.png").exists()


def test_existing_target_selected_as_source_is_a_true_noop() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        profile = _profile(root)
        logo = _image(profile.grid_dir / "424242_logo.png", (512, 256), (20, 30, 40))
        game = _native_game(root)
        game.artwork.logo = ArtworkAsset(
            kind="logo",
            asset_id="existing-logo",
            url=logo.resolve().as_uri(),
            width=512,
            height=256,
            local_path=logo,
        )
        original = logo.read_bytes()

        writes, removals = plan_game_artwork_transaction(game, profile)
        copied = copy_game_artwork_to_steam(game, profile)

        assert writes == []
        assert removals == []
        assert copied == []
        assert logo.read_bytes() == original


if __name__ == "__main__":
    test_live_artwork_copy_commits_fallback_slots_and_removes_stale_variants()
    test_invalid_live_artwork_is_blocked_before_existing_target_changes()
    test_existing_target_selected_as_source_is_a_true_noop()
    print("Live atomic artwork tests passed.")
