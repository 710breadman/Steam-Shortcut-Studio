from __future__ import annotations

import tempfile
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from steam_shortcut_studio.artwork import artwork_assets_for_steam_slots, copy_all_artwork_to_steam
from steam_shortcut_studio.metadata import MetadataService
from steam_shortcut_studio.models import ArtworkAsset, DetectedGame, GameMetadata, SteamProfile
from steam_shortcut_studio.scanner import GameScanner, clean_display_title, is_specific_title_match, similarity
from steam_shortcut_studio.settings_store import AppSettings, SettingsStore
from steam_shortcut_studio.steam_library import games_from_nonsteam_shortcuts
from steam_shortcut_studio.steam_notes import write_metadata_notes
from steam_shortcut_studio.steam_shortcuts import (
    ShortcutRecord,
    generate_appid,
    load_shortcuts,
    mark_existing_shortcuts,
    preview_changes,
    shortcut_from_game,
    upsert_games,
    write_shortcuts_file,
)
from steam_shortcut_studio.ui import (
    RAWG_API_URL,
    STEAMGRIDDB_API_URL,
    THEME_PALETTES,
    THEMES,
    build_artwork_search_terms,
    merge_detected_game_lists,
    normalized_artwork_cache_key,
)


def write_fake_exe(path: Path, size: int = 1024 * 1024) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = bytearray(max(size, 512))
    data[0:2] = b"MZ"
    data[0x3C:0x40] = (0x80).to_bytes(4, "little")
    data[0x80:0x84] = b"PE\x00\x00"
    data[0x84:0x86] = (0x8664).to_bytes(2, "little")
    data[0x98:0x9A] = (0x20B).to_bytes(2, "little")
    data[0x80 + 24 + 108 : 0x80 + 24 + 110] = (2).to_bytes(2, "little")
    path.write_bytes(data)


def test_vdf_roundtrip() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "shortcuts.vdf"
        record = ShortcutRecord(
            appid=generate_appid(r"C:\Games\Test\Test.exe", "Test Game"),
            app_name="Test Game",
            exe='"C:\\Games\\Test\\Test.exe"',
            start_dir='"C:\\Games\\Test"',
            icon=r"C:\Games\Test\Test.exe",
            tags=["Non Steam", "Imported"],
        )
        write_shortcuts_file(path, [record])
        loaded = load_shortcuts(path)
        assert len(loaded) == 1
        assert loaded[0].app_name == "Test Game"
        assert loaded[0].tags == ["Non Steam", "Imported"]


def test_scanner_ranks_primary_exe() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_fake_exe(root / "Cyberpunk 2077" / "bin" / "x64" / "Cyberpunk2077.exe", size=25 * 1024 * 1024)
        write_fake_exe(root / "Cyberpunk 2077" / "setup.exe", size=2 * 1024 * 1024)
        write_fake_exe(root / "Cyberpunk 2077" / "_CommonRedist" / "vc_redist.exe", size=8 * 1024 * 1024)
        games = GameScanner().scan(root)
        assert len(games) == 1
        assert games[0].title == "Cyberpunk 2077"
        assert games[0].selected_exe is not None
        assert games[0].selected_exe.name == "Cyberpunk2077.exe"


def test_title_normalization_handles_god_of_war_and_gta() -> None:
    assert clean_display_title("God of War") == "God of War"
    assert clean_display_title("God of War - Ragnarok") == "God of War Ragnarok"
    assert clean_display_title("GTA - The Trilogy - DELauncher") == "Grand Theft Auto: The Trilogy - The Definitive Edition"
    assert not is_specific_title_match("God of War Ragnarok", "God of War", minimum_similarity=0.52)
    assert similarity("God of War Ragnarok", "God of War") < 0.80


def test_scanner_uses_root_exe_title_instead_of_collection_name() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "PCGames"
        exe = root / "GTA - The Trilogy - DELauncher.exe"
        write_fake_exe(exe, size=8 * 1024 * 1024)
        games = GameScanner().scan(root)
        assert len(games) == 1
        assert games[0].title == "Grand Theft Auto: The Trilogy - The Definitive Edition"
        assert games[0].source_title == "GTA - The Trilogy - DELauncher"
        assert games[0].selected_exe == exe


def test_upsert_and_duplicate_marking() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        steam_root = Path(tmp) / "SteamUser"
        profile = SteamProfile(
            user_id="123",
            config_dir=steam_root / "config",
            shortcuts_path=steam_root / "config" / "shortcuts.vdf",
            grid_dir=steam_root / "config" / "grid",
        )
        exe = Path(tmp) / "Games" / "Example" / "Example.exe"
        write_fake_exe(exe)
        game = DetectedGame(title="Example", root_path=exe.parent, selected_exe=exe)
        added, updated, backup = upsert_games(profile, [game], update_existing=True, default_tags=[])
        assert added == 1
        assert updated == 0
        assert backup is None
        records = load_shortcuts(profile.shortcuts_path)
        assert records[0].tags == ["Non Steam"]
        records[0].launch_options = "-manual-option"
        records[0].allow_overlay = 0
        records[0].tags = ["ManualTag"]
        write_shortcuts_file(profile.shortcuts_path, records)
        mark_existing_shortcuts([game], records)
        assert game.existing_appid is not None
        game.metadata.genres = ["Action"]
        added, updated, backup = upsert_games(profile, [game], update_existing=True, default_tags=["Imported"])
        assert added == 0
        assert updated == 1
        assert backup is not None and backup.exists()
        updated_record = load_shortcuts(profile.shortcuts_path)[0]
        assert updated_record.launch_options == "-manual-option"
        assert updated_record.allow_overlay == 0
        assert updated_record.tags == ["ManualTag", "Non Steam", "Imported", "Action"]


def test_malformed_shortcuts_vdf_is_backed_up_and_replaced() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        profile = SteamProfile(
            user_id="123",
            config_dir=root / "config",
            shortcuts_path=root / "config" / "shortcuts.vdf",
            grid_dir=root / "config" / "grid",
        )
        profile.shortcuts_path.parent.mkdir(parents=True, exist_ok=True)
        profile.shortcuts_path.write_bytes(b"\x00shortcuts\x00\x00broken")
        exe = root / "Games" / "Example" / "Example.exe"
        write_fake_exe(exe)
        game = DetectedGame(title="Example", root_path=exe.parent, selected_exe=exe)
        preview = preview_changes(profile, [game], update_existing=True, default_tags=[])
        assert "could not be parsed" in preview
        added, updated, backup = upsert_games(profile, [game], update_existing=True, default_tags=[])
        assert (added, updated) == (1, 0)
        assert backup is not None and backup.exists()
        records = load_shortcuts(profile.shortcuts_path)
        assert len(records) == 1
        assert records[0].app_name == "Example"


def test_combined_scan_keeps_folder_row_writable_when_shortcut_exists() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        steam_root = root / "SteamUser"
        profile = SteamProfile(
            user_id="123",
            config_dir=steam_root / "config",
            shortcuts_path=steam_root / "config" / "shortcuts.vdf",
            grid_dir=steam_root / "config" / "grid",
        )
        exe = root / "Games" / "Example" / "Example.exe"
        write_fake_exe(exe)
        existing_record = ShortcutRecord(
            appid=generate_appid(exe, "Example"),
            app_name="Example",
            exe=f'"{exe}"',
            start_dir=f'"{exe.parent}"',
            launch_options="-old-option",
            tags=["ManualTag"],
        )
        write_shortcuts_file(profile.shortcuts_path, [existing_record])
        shortcut_row = games_from_nonsteam_shortcuts([existing_record])[0]
        folder_row = DetectedGame(title="Example", root_path=exe.parent, selected_exe=exe, selected=True)
        merged = merge_detected_game_lists([shortcut_row], [folder_row])
        assert len(merged) == 1
        assert merged[0].source_type == "folder"
        assert merged[0].selected is True
        assert merged[0].existing_appid == existing_record.appid
        assert merged[0].launch_options == "-old-option"
        added, updated, backup = upsert_games(profile, merged, update_existing=True, default_tags=[])
        assert (added, updated) == (0, 1)
        assert backup is not None and backup.exists()
        updated_record = load_shortcuts(profile.shortcuts_path)[0]
        assert updated_record.app_name == "Example"
        assert "Non Steam" in updated_record.tags


class FakeMetadataProvider:
    name = "Fake Metadata"

    def enrich(self, game: DetectedGame) -> GameMetadata:
        return GameMetadata(
            clean_title="Example Deluxe",
            release_year="2021",
            developer="Example Dev",
            publisher="Example Pub",
            genres=["Action", "Adventure"],
            description="A scraped overview for a non-Steam game.",
            source=self.name,
            extra={"Platform": "Windows"},
        )


class BadShortTitleProvider:
    name = "Bad Short Title"

    def enrich(self, game: DetectedGame) -> GameMetadata:
        return GameMetadata(clean_title="GoW", source=self.name, description="Wrong title should not replace folder title.")


def test_metadata_scrape_populates_nonsteam_notes() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        exe = Path(tmp) / "Games" / "Example" / "Example.exe"
        write_fake_exe(exe)
        game = DetectedGame(title="Example", root_path=exe.parent, selected_exe=exe)
        MetadataService([FakeMetadataProvider()]).enrich(game)
        assert "A scraped overview for a non-Steam game." in game.metadata.notes
        assert "Released: 2021" in game.metadata.notes
        assert "Developer: Example Dev" not in game.metadata.notes
        assert "Publisher: Example Pub" not in game.metadata.notes
        assert "Genres/tags: Action, Adventure" not in game.metadata.notes


def test_bad_short_metadata_title_does_not_replace_folder_title() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        exe = Path(tmp) / "Games" / "God of War" / "GoW.exe"
        write_fake_exe(exe)
        game = DetectedGame(title="God of War", root_path=exe.parent, selected_exe=exe)
        MetadataService([BadShortTitleProvider()]).enrich(game)
        assert game.display_title == "God of War"


def test_metadata_scrape_preserves_user_edited_notes() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        exe = Path(tmp) / "Games" / "Example" / "Example.exe"
        write_fake_exe(exe)
        game = DetectedGame(title="Example", root_path=exe.parent, selected_exe=exe)
        game.metadata.notes = "User curated notes."
        MetadataService([FakeMetadataProvider()]).enrich(game)
        assert game.metadata.notes == "User curated notes."


def test_preview_shows_exact_notes_payload() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        profile = SteamProfile(
            user_id="123",
            config_dir=root / "config",
            shortcuts_path=root / "config" / "shortcuts.vdf",
            grid_dir=root / "config" / "grid",
        )
        exe = root / "Games" / "Example" / "Example.exe"
        write_fake_exe(exe)
        game = DetectedGame(title="Example", root_path=exe.parent, selected_exe=exe)
        game.metadata.notes = "Exact reviewed notes.\nLine two."
        text = preview_changes(profile, [game], update_existing=True, default_tags=[])
        assert "Notes preview:" in text
        assert "Exact reviewed notes." in text
        assert "Line two." in text


def test_selected_executable_is_written_to_shortcut() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        first = root / "Games" / "Example" / "Launcher.exe"
        second = root / "Games" / "Example" / "Example.exe"
        write_fake_exe(first)
        write_fake_exe(second)
        game = DetectedGame(title="Example", root_path=first.parent, selected_exe=first)
        record = shortcut_from_game(game)
        assert "Launcher.exe" in record.exe
        game.selected_exe = second
        record = shortcut_from_game(game)
        assert "Example.exe" in record.exe
        assert "Example" in record.start_dir


def test_manual_title_override_is_written_to_shortcut() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        profile = SteamProfile(
            user_id="123",
            config_dir=root / "config",
            shortcuts_path=root / "config" / "shortcuts.vdf",
            grid_dir=root / "config" / "grid",
        )
        exe = root / "Games" / "God of War" / "GoW.exe"
        write_fake_exe(exe)
        game = DetectedGame(title="God of War", root_path=exe.parent, selected_exe=exe)
        game.metadata.clean_title = "God of War Custom"
        game.metadata.title_locked = True
        added, updated, _backup = upsert_games(profile, [game], update_existing=True, default_tags=[])
        assert (added, updated) == (1, 0)
        records = load_shortcuts(profile.shortcuts_path)
        assert records[0].app_name == "God of War Custom"
        assert "GoW.exe" in records[0].exe


def test_metadata_notes_are_marked_and_updated() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        steam_root = Path(tmp) / "SteamUser"
        profile = SteamProfile(
            user_id="123",
            config_dir=steam_root / "config",
            shortcuts_path=steam_root / "config" / "shortcuts.vdf",
            grid_dir=steam_root / "config" / "grid",
        )
        exe = Path(tmp) / "Games" / "Example" / "Example.exe"
        write_fake_exe(exe)
        game = DetectedGame(title="Example", root_path=exe.parent, selected_exe=exe)
        game.metadata.description = "A useful test description."
        paths = write_metadata_notes(profile, [game])
        assert len(paths) >= 2
        text = "\n".join(path.read_text(encoding="utf-8") for path in paths)
        assert "Steam Shortcut Studio Notes BEGIN" in text
        assert "A useful test description." in text
        steam_note = next(path for path in paths if path.name == "notes_shortcut_Example")
        data = json.loads(steam_note.read_text(encoding="utf-8"))
        assert data["shortcut_name"] == "Example"
        assert any(note["id"] == "steam_shortcut_studio_metadata" for note in data["notes"])
        visible_note = next(note for note in data["notes"] if note["id"] == "steam_shortcut_studio_metadata")
        assert visible_note["title"] == "A useful test description."
        assert any(path.name == "Example.txt" for path in paths)


def test_native_steam_game_notes_are_not_written() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        steam_root = Path(tmp) / "SteamUser"
        profile = SteamProfile(
            user_id="123",
            config_dir=steam_root / "config",
            shortcuts_path=steam_root / "config" / "shortcuts.vdf",
            grid_dir=steam_root / "config" / "grid",
        )
        game = DetectedGame(
            title="Native Example",
            root_path=Path(tmp) / "Steam" / "steamapps" / "common" / "Native Example",
            metadata=GameMetadata(clean_title="Native Example", steam_appid=424242, description="Native game description."),
            source_type="steam",
            steam_appid=424242,
        )
        game.selected = True
        paths = write_metadata_notes(profile, [game])
        assert paths == []


def test_native_steam_game_artwork_is_not_modified() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        profile = SteamProfile(
            user_id="123",
            config_dir=root / "config",
            shortcuts_path=root / "config" / "shortcuts.vdf",
            grid_dir=root / "config" / "grid",
        )
        image = root / "cache" / "hero.png"
        image.parent.mkdir(parents=True, exist_ok=True)
        image.write_bytes(b"fake image")
        game = DetectedGame(
            title="Native Example",
            root_path=root / "Steam" / "steamapps" / "common" / "Native Example",
            source_type="steam",
            steam_appid=424242,
        )
        game.artwork.hero = ArtworkAsset(kind="hero", asset_id="hero", url="https://example.invalid/hero.png", local_path=image)
        game.selected = True
        copied = copy_all_artwork_to_steam([game], profile)
        assert copied == []


def test_native_steam_game_shortcut_is_not_upserted() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        profile = SteamProfile(
            user_id="123",
            config_dir=root / "config",
            shortcuts_path=root / "config" / "shortcuts.vdf",
            grid_dir=root / "config" / "grid",
        )
        game = DetectedGame(
            title="Native Example",
            root_path=root / "Steam" / "steamapps" / "common" / "Native Example",
            selected=True,
            source_type="steam",
            steam_appid=424242,
        )
        added, updated, _backup = upsert_games(profile, [game], update_existing=True, default_tags=[])
        assert (added, updated) == (0, 0)
        assert load_shortcuts(profile.shortcuts_path) == []


def test_grid_artwork_writes_both_steam_grid_slots() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        profile = SteamProfile(
            user_id="123",
            config_dir=root / "config",
            shortcuts_path=root / "config" / "shortcuts.vdf",
            grid_dir=root / "config" / "grid",
        )
        profile.grid_dir.mkdir(parents=True, exist_ok=True)
        stale_portrait = profile.grid_dir / "424242p.jpg"
        stale_wide = profile.grid_dir / "424242.jpg"
        stale_portrait.write_bytes(b"old portrait")
        stale_wide.write_bytes(b"old wide")
        image = root / "cache" / "grid.png"
        image.parent.mkdir(parents=True, exist_ok=True)
        image.write_bytes(b"new grid")
        game = DetectedGame(
            title="Native Example",
            root_path=root / "Steam" / "steamapps" / "common" / "Native Example",
            selected_exe=root / "Games" / "Native Example" / "NativeExample.exe",
            existing_appid=424242,
        )
        game.artwork.grid = ArtworkAsset(kind="grid", asset_id="grid", url="https://example.invalid/grid.png", width=600, height=900, local_path=image)
        copied = copy_all_artwork_to_steam([game], profile)
        names = {path.name for path in copied}
        assert names == {"424242p.png", "424242.png", "424242_hero.png", "424242_icon.png"}
        assert not stale_portrait.exists()
        assert not stale_wide.exists()
        assert (profile.grid_dir / "424242p.png").read_bytes() == b"new grid"
        assert (profile.grid_dir / "424242.png").read_bytes() == b"new grid"


def test_user_edited_notes_are_preserved_when_written() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        profile = SteamProfile(
            user_id="123",
            config_dir=root / "config",
            shortcuts_path=root / "config" / "shortcuts.vdf",
            grid_dir=root / "config" / "grid",
        )
        exe = root / "Games" / "Example" / "Example.exe"
        write_fake_exe(exe)
        game = DetectedGame(title="Example", root_path=exe.parent, selected_exe=exe)
        game.metadata.description = "Scraped text that should not replace the edit."
        game.metadata.notes = "User edited note.\n\nKeep this wording."
        paths = write_metadata_notes(profile, [game])
        steam_note = next(path for path in paths if path.name == "notes_shortcut_Example")
        data = json.loads(steam_note.read_text(encoding="utf-8"))
        content = data["notes"][0]["content"]
        assert "User edited note." in content
        assert "Scraped text that should not replace the edit." not in content


def test_artwork_slot_fallbacks_cover_big_picture_slots() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        image = root / "cache" / "grid.png"
        image.parent.mkdir(parents=True, exist_ok=True)
        image.write_bytes(b"new grid")
        game = DetectedGame(title="Example", root_path=root / "Example", selected_exe=root / "Example" / "Example.exe")
        game.artwork.grid = ArtworkAsset(kind="grid", asset_id="grid", url="https://example.invalid/grid.png", width=600, height=900, local_path=image)
        slots = artwork_assets_for_steam_slots(game)
        assert {asset.kind for asset in slots} == {"grid", "wide", "hero", "icon"}


def test_theme_palettes_are_visibly_distinct() -> None:
    seen = set()
    for theme in THEMES:
        if theme == "Follow System":
            continue
        palette = THEME_PALETTES[theme]
        signature = (palette["bg"], palette["panel"], palette["accent"], palette["selected"])
        assert signature not in seen
        seen.add(signature)
    assert len(seen) >= 8


def test_settings_roundtrip_includes_view_and_metadata_options() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        store = SettingsStore(Path(tmp) / "settings.json")
        settings = AppSettings(
            cache_dir=str(Path(tmp) / "cache"),
            view_filter="Needs artwork",
            sort_preset="Steam status",
            artwork_preview_limit=24,
            theme_name="Glacier Blue",
            rawg_api_key="rawg-test-key",
            artwork_sources={"steam": True, "steamgriddb": False, "wikimedia": True, "rawg": True},
            metadata_sources={"executable": True, "steamgriddb": False, "steam": True, "pcgamingwiki": False, "wikipedia": True},
        )
        store.save(settings)
        loaded = store.load()
        assert loaded.view_filter == "Needs artwork"
        assert loaded.sort_preset == "Steam status"
        assert loaded.artwork_preview_limit == 24
        assert loaded.theme_name == "Glacier Blue"
        assert loaded.rawg_api_key == "rawg-test-key"
        assert loaded.artwork_sources["rawg"] is True
        assert loaded.artwork_sources["steamgriddb"] is False
        assert loaded.metadata_sources["steamgriddb"] is False


def test_artwork_search_terms_prefer_folder_title_and_logical_aliases() -> None:
    game = DetectedGame(
        title="GoWR",
        source_title="God of War - Ragnarok",
        root_path=Path(r"C:\Games\God of War - Ragnarok"),
        selected_exe=Path(r"C:\Games\God of War - Ragnarok\GoWR.exe"),
    )
    terms = build_artwork_search_terms(game)
    assert terms[0] == "God of War - Ragnarok"
    assert "God of War Ragnarok" in terms
    assert "GoWR" in terms


def test_artwork_cache_key_and_api_links_are_stable() -> None:
    assert normalized_artwork_cache_key("  God   of WAR  ") == "god of war"
    assert STEAMGRIDDB_API_URL == "https://www.steamgriddb.com/profile/preferences/api"
    assert RAWG_API_URL.startswith("https://rawg.io/")


if __name__ == "__main__":
    test_vdf_roundtrip()
    test_scanner_ranks_primary_exe()
    test_title_normalization_handles_god_of_war_and_gta()
    test_scanner_uses_root_exe_title_instead_of_collection_name()
    test_upsert_and_duplicate_marking()
    test_malformed_shortcuts_vdf_is_backed_up_and_replaced()
    test_combined_scan_keeps_folder_row_writable_when_shortcut_exists()
    test_metadata_notes_are_marked_and_updated()
    test_metadata_scrape_populates_nonsteam_notes()
    test_bad_short_metadata_title_does_not_replace_folder_title()
    test_metadata_scrape_preserves_user_edited_notes()
    test_preview_shows_exact_notes_payload()
    test_selected_executable_is_written_to_shortcut()
    test_manual_title_override_is_written_to_shortcut()
    test_native_steam_game_notes_are_not_written()
    test_native_steam_game_artwork_is_not_modified()
    test_native_steam_game_shortcut_is_not_upserted()
    test_grid_artwork_writes_both_steam_grid_slots()
    test_user_edited_notes_are_preserved_when_written()
    test_artwork_slot_fallbacks_cover_big_picture_slots()
    test_theme_palettes_are_visibly_distinct()
    test_settings_roundtrip_includes_view_and_metadata_options()
    test_artwork_search_terms_prefer_folder_title_and_logical_aliases()
    test_artwork_cache_key_and_api_links_are_stable()
    print("Smoke tests passed.")
