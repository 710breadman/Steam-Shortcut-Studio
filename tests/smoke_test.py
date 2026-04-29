from __future__ import annotations

import os
import tempfile
import sys
import json
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import steam_shortcut_studio.scanner as scanner_module
from steam_shortcut_studio.artwork import asset_download_cache_path, artwork_assets_for_steam_slots, copy_all_artwork_to_steam
from steam_shortcut_studio.metadata import MetadataService
from steam_shortcut_studio.models import ArtworkAsset, DetectedGame, ExecutableCandidate, GameMetadata, SteamProfile
from steam_shortcut_studio.scanner import GameScanner, clean_display_title, is_specific_title_match, similarity
from steam_shortcut_studio.settings_store import AppSettings, SettingsStore
from steam_shortcut_studio.steam_detection import is_valid_steam_path
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
    GAME_COLUMNS,
    MainWindow,
    RAWG_API_URL,
    SORT_PRESETS,
    STEAMGRIDDB_API_URL,
    THEME_PALETTES,
    THEMES,
    artwork_candidate_score,
    build_artwork_search_terms,
    merge_detected_game_lists,
    normalized_artwork_cache_key,
    normalize_windows_path_text,
    release_year_from_text,
)
from steam_shortcut_studio.steam_store import find_steam_app, official_steam_assets, steam_store_media_assets


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


def same_path(left: Path | None, right: Path) -> bool:
    return left is not None and left.resolve(strict=False) == right.resolve(strict=False)


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
        assert same_path(games[0].selected_exe, exe)


def test_scanner_prefers_root_title_exe_over_unrelated_shipping_codename() -> None:
    root = Path(r"D:\pcgame\Disney Epic Mickey Rebrushed")
    root_candidate = ExecutableCandidate(
        path=root / "Rebrushed.exe",
        score=54,
        confidence=54,
        size_bytes=768 * 1024,
        depth=0,
        reasons=[],
    )
    shipping_candidate = ExecutableCandidate(
        path=root / "recolored" / "Binaries" / "Win64" / "recolored-Win64-Shipping.exe",
        score=100,
        confidence=100,
        size_bytes=180 * 1024 * 1024,
        depth=4,
        reasons=[],
    )
    candidates = [shipping_candidate, root_candidate]
    GameScanner().rebalance_candidate_scores("Disney Epic Mickey Rebrushed", root, candidates)
    candidates.sort(key=lambda candidate: candidate.score, reverse=True)
    assert candidates[0].path.name == "Rebrushed.exe"


def test_scanner_reports_games_as_they_are_ranked() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_fake_exe(root / "Alpha Adventure" / "Alpha.exe", size=8 * 1024 * 1024)
        write_fake_exe(root / "Beta Adventure" / "Beta.exe", size=8 * 1024 * 1024)
        live_titles: list[str] = []

        games = GameScanner(game_callback=lambda game: live_titles.append(game.title)).scan(root)

        assert live_titles == [game.title for game in games]
        assert live_titles == ["Alpha Adventure", "Beta Adventure"]


def test_scanner_detects_exes_but_leaves_games_unselected_by_default() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_fake_exe(root / "Unchecked Example" / "UncheckedExample.exe", size=8 * 1024 * 1024)
        games = GameScanner().scan(root)
        assert len(games) == 1
        assert games[0].selected_exe is not None
        assert games[0].selected is False


def test_scanner_detects_native_linux_launch_candidates() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        native_launcher = root / "Native Example" / "NativeExample.sh"
        native_launcher.parent.mkdir(parents=True, exist_ok=True)
        native_launcher.write_text("#!/usr/bin/env sh\nexec ./NativeExample\n", encoding="utf-8")

        original = scanner_module.native_launch_candidates_enabled
        scanner_module.native_launch_candidates_enabled = lambda: True
        try:
            games = GameScanner().scan(root)
        finally:
            scanner_module.native_launch_candidates_enabled = original

        assert len(games) == 1
        assert games[0].title == "Native Example"
        assert same_path(games[0].selected_exe, native_launcher)
        assert any("Linux" in reason for reason in games[0].candidates[0].reasons)


def test_linux_steam_path_can_be_validated() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        steam_root = Path(tmp) / "Steam"
        (steam_root / "userdata").mkdir(parents=True)
        (steam_root / "steamapps").mkdir()
        (steam_root / "steam.sh").write_text("#!/usr/bin/env sh\n", encoding="utf-8")
        assert is_valid_steam_path(steam_root)


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
        game = DetectedGame(title="Example", root_path=exe.parent, selected_exe=exe, selected=True)
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
        game = DetectedGame(title="Example", root_path=exe.parent, selected_exe=exe, selected=True)
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


def test_combined_scan_merges_existing_shortcut_when_scan_picks_different_exe() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        old_exe = root / "Games" / "Assassin's Creed Mirage" / "ACMirage.exe"
        scanned_exe = root / "Games" / "Assassin's Creed Mirage" / "scimitar_engine_win64_vs2019.exe"
        write_fake_exe(old_exe)
        write_fake_exe(scanned_exe)
        existing_record = ShortcutRecord(
            appid=generate_appid(old_exe, "Assassin's Creed Mirage"),
            app_name="Assassin's Creed Mirage",
            exe=f'"{old_exe}"',
            start_dir=f'"{old_exe.parent}"',
            tags=["ManualTag"],
        )
        shortcut_row = games_from_nonsteam_shortcuts([existing_record])[0]
        folder_row = DetectedGame(
            title="Assassin's Creed Mirage",
            root_path=scanned_exe.parent,
            selected_exe=scanned_exe,
            selected=True,
            source_type="folder",
        )
        merged = merge_detected_game_lists([shortcut_row], [folder_row])
        assert len(merged) == 1
        assert merged[0].source_type == "folder"
        assert same_path(merged[0].selected_exe, old_exe)
        assert merged[0].existing_appid == existing_record.appid
        assert merged[0].existing_match == "shortcut"
        assert merged[0].launch_options == shortcut_row.launch_options


def test_rescan_title_match_remembers_existing_shortcut_exe() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        remembered_exe = root / "Games" / "Example" / "Remembered.exe"
        scanned_exe = root / "Games" / "Example" / "Engine" / "Binaries" / "Win64" / "Project-Win64-Shipping.exe"
        write_fake_exe(remembered_exe)
        write_fake_exe(scanned_exe)
        record = ShortcutRecord(
            appid=generate_appid(remembered_exe, "Example"),
            app_name="Example",
            exe=f'"{remembered_exe}"',
            start_dir=f'"{remembered_exe.parent}"',
        )
        game = DetectedGame(
            title="Example",
            root_path=remembered_exe.parent,
            selected_exe=scanned_exe,
            candidates=[
                ExecutableCandidate(
                    path=scanned_exe,
                    score=100,
                    confidence=100,
                    size_bytes=scanned_exe.stat().st_size,
                    depth=4,
                )
            ],
            source_type="folder",
        )
        mark_existing_shortcuts([game], [record])
        window = object.__new__(MainWindow)
        window.apply_existing_shortcut_choices([game], [record])
        assert same_path(game.selected_exe, remembered_exe)
        assert same_path(game.candidates[0].path, remembered_exe)
        assert game.selected is False


def test_nonsteam_shortcut_title_merge_does_not_absorb_native_steam_game() -> None:
    steam_game = DetectedGame(
        title="Example",
        root_path=Path(r"C:\Steam\steamapps\common\Example"),
        selected=False,
        source_type="steam",
        steam_appid=123,
    )
    shortcut_row = DetectedGame(
        title="Example",
        root_path=Path(r"C:\Games\Example"),
        selected_exe=Path(r"C:\Games\Example\Example.exe"),
        source_type="shortcut",
        existing_appid=-123,
    )
    merged = merge_detected_game_lists([steam_game], [shortcut_row])
    assert len(merged) == 2


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
        game = DetectedGame(title="Example", root_path=exe.parent, selected_exe=exe, selected=True)
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
        game = DetectedGame(title="God of War", root_path=exe.parent, selected_exe=exe, selected=True)
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
        game = DetectedGame(title="Example", root_path=exe.parent, selected_exe=exe, selected=True)
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


def test_native_steam_game_artwork_can_be_replaced_without_shortcuts() -> None:
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
        names = {path.name for path in copied}
        assert names == {"424242.png", "424242_hero.png", "424242_icon.png"}
        assert not profile.shortcuts_path.exists()


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
            selected=True,
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
        game = DetectedGame(title="Example", root_path=exe.parent, selected_exe=exe, selected=True)
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


def test_game_list_columns_remove_confidence_from_defaults() -> None:
    assert "confidence" not in GAME_COLUMNS
    assert "Confidence high" not in SORT_PRESETS
    settings = AppSettings()
    assert "confidence" not in settings.visible_game_columns
    assert "confidence" not in settings.game_column_order


def test_clear_cached_artwork_removes_downloads_and_search_cache_only() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        cache = Path(tmp) / "cache"
        artwork_file = cache / "artwork" / "grid" / "cover.png"
        artwork_file.parent.mkdir(parents=True)
        artwork_file.write_bytes(b"cover")
        artwork_search = cache / "artwork_search_cache.json"
        artwork_search.write_text("{}", encoding="utf-8")
        sgdb_search = cache / "sgdb_search_cache.json"
        sgdb_search.write_text("{}", encoding="utf-8")
        keep = cache / "metadata_cache.json"
        keep.write_text("keep", encoding="utf-8")

        result = SettingsStore(Path(tmp) / "settings.json").clear_cached_artwork(AppSettings(cache_dir=str(cache)))

        assert result.files_deleted == 3
        assert not artwork_file.exists()
        assert not artwork_search.exists()
        assert not sgdb_search.exists()
        assert not (cache / "artwork").exists()
        assert keep.exists()
        assert cache.exists()


def test_individual_artwork_search_deletes_only_that_games_cached_files() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        cache = Path(tmp) / "cache"
        cached_file = cache / "artwork" / "grid" / "old-cover.png"
        other_cached_file = cache / "artwork" / "grid" / "other-cover.png"
        steam_grid_file = Path(tmp) / "steam" / "userdata" / "grid" / "existing.png"
        for path in (cached_file, other_cached_file, steam_grid_file):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"image")

        old_asset = ArtworkAsset("grid", "old-cover", "https://example.test/old.png", local_path=cached_file)
        other_asset = ArtworkAsset("grid", "other-cover", "https://example.test/other.png", local_path=other_cached_file)
        steam_grid_asset = ArtworkAsset("hero", "existing", steam_grid_file.as_uri(), local_path=steam_grid_file)
        generated_asset = ArtworkAsset("wide", "generated-cover", "https://example.test/generated.jpg")
        generated_file = asset_download_cache_path(generated_asset, cache)
        generated_file.parent.mkdir(parents=True, exist_ok=True)
        generated_file.write_bytes(b"generated")
        game = DetectedGame(title="Test Game", source_title="Test Game", root_path=Path(r"C:\Games\Test Game"))
        game.artwork.grid = old_asset
        game.artwork.hero = steam_grid_asset

        window = object.__new__(MainWindow)
        window.settings = AppSettings(cache_dir=str(cache))
        window.games = [game]
        window.artwork_search_cache = {0: {"grid": [old_asset], "hero": [steam_grid_asset], "wide": [generated_asset]}}
        window.artwork_title_cache = {
            "test game": {"grid": [old_asset], "hero": [steam_grid_asset], "wide": [generated_asset]},
            "other game": {"grid": [other_asset]},
        }
        window.artwork_job_status = {}
        window.manual_artwork_slots = {(id(game), "grid"), (id(game), "hero")}
        window.current_game_index = None
        window.logger = logging.getLogger("SteamShortcutStudioTest")
        window.refresh_game_row = lambda _index: None
        window.save_persistent_artwork_search_cache = lambda: None

        window.clear_individual_artwork_cache(game)

        assert not cached_file.exists()
        assert not generated_file.exists()
        assert other_cached_file.exists()
        assert steam_grid_file.exists()
        assert game.artwork.grid is None
        assert game.artwork.hero is None
        assert 0 not in window.artwork_search_cache
        assert "test game" not in window.artwork_title_cache
        assert "other game" in window.artwork_title_cache
        assert not window.manual_artwork_slots


def test_list_artwork_search_clears_cache_for_selected_current_view_games() -> None:
    visible_selected = DetectedGame(title="Visible Selected", root_path=Path(r"C:\Games\Visible Selected"), selected=True)
    visible_unselected = DetectedGame(title="Visible Unselected", root_path=Path(r"C:\Games\Visible Unselected"), selected=False)
    hidden_selected = DetectedGame(title="Hidden Selected", root_path=Path(r"C:\Games\Hidden Selected"), selected=True)

    window = object.__new__(MainWindow)
    window.games = [visible_selected, visible_unselected, hidden_selected]
    window.displayed_game_indices = [0, 1]
    cleared: list[str] = []
    started: list[tuple[list[str], bool]] = []
    window.clear_individual_artwork_cache = lambda game: cleared.append(game.display_title)
    window.match_metadata_and_art_for_games = lambda games, force_refresh=False: started.append(
        ([game.display_title for game in games], force_refresh)
    )

    window.match_metadata_and_art_for_selected(force_refresh=True)

    assert cleared == ["Visible Selected"]
    assert started == [(["Visible Selected"], True)]


def test_reset_settings_to_defaults_rewrites_settings_file() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        old_env = {key: os.environ.get(key) for key in ("APPDATA", "LOCALAPPDATA", "XDG_CONFIG_HOME", "XDG_CACHE_HOME")}
        if os.name == "nt":
            os.environ["APPDATA"] = str(Path(tmp) / "Roaming")
            os.environ["LOCALAPPDATA"] = str(Path(tmp) / "Local")
            expected_cache = Path(tmp) / "Local" / "SteamShortcutStudio" / "cache"
        else:
            os.environ["XDG_CONFIG_HOME"] = str(Path(tmp) / "config")
            os.environ["XDG_CACHE_HOME"] = str(Path(tmp) / "cache-root")
            expected_cache = Path(tmp) / "cache-root" / "SteamShortcutStudio" / "cache"
        try:
            store = SettingsStore(Path(tmp) / "settings.json")
            store.save(
                AppSettings(
                    steam_path=r"D:\Steam",
                    collection_root=r"D:\pcgame",
                    steamgriddb_api_key="sgdb-key",
                    rawg_api_key="rawg-key",
                    cache_dir=str(Path(tmp) / "custom-cache"),
                    theme_name="Glacier Blue",
                    view_filter="Needs artwork",
                )
            )

            reset = store.reset_to_defaults()
            loaded = store.load()

            assert reset.steam_path == ""
            assert loaded.collection_root == ""
            assert loaded.steamgriddb_api_key == ""
            assert loaded.rawg_api_key == ""
            assert loaded.theme_name == "Follow System"
            assert loaded.view_filter == "All"
            assert Path(loaded.cache_dir) == expected_cache
        finally:
            for key, value in old_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value


def test_artwork_search_terms_prefer_folder_title_and_logical_aliases() -> None:
    game = DetectedGame(
        title="GoWR",
        source_title="God of War - Ragnarok",
        root_path=Path(r"C:\Games\God of War - Ragnarok"),
        selected_exe=Path(r"C:\Games\God of War - Ragnarok\GoWR.exe"),
    )
    game.metadata.release_year = "2022"
    terms = build_artwork_search_terms(game)
    assert terms[0] == "God of War - Ragnarok"
    assert "God of War Ragnarok" in terms
    assert "God of War Ragnarok 2022" in terms
    assert "GoWR" in terms
    game = DetectedGame(
        title="Disney Epic Mickey Rebrushed",
        source_title="Disney Epic Mickey Rebrushed",
        root_path=Path(r"C:\Games\Disney Epic Mickey Rebrushed"),
        selected_exe=Path(r"C:\Games\Disney Epic Mickey Rebrushed\recolored\Binaries\Win64\recolored-Win64-Shipping.exe"),
    )
    terms = build_artwork_search_terms(game)
    assert "Disney Epic Mickey: Rebrushed" in terms
    assert "Epic Mickey: Rebrushed" in terms
    assert "recolored-Win64-Shipping" not in terms
    game = DetectedGame(title="Ghost of Tsushima DC", source_title="Ghost of Tsushima DC", root_path=Path(r"C:\Games\Ghost of Tsushima DC"))
    terms = build_artwork_search_terms(game)
    assert "Ghost of Tsushima Director's Cut" in terms
    game = DetectedGame(title="WUCHANG Fallen Feathers", source_title="WUCHANG - Fallen Feathers", root_path=Path(r"C:\Games\WUCHANG - Fallen Feathers"))
    terms = build_artwork_search_terms(game)
    assert "WUCHANG: Fallen Feathers" in terms


def test_artwork_search_terms_use_typed_title_first() -> None:
    game = DetectedGame(
        title="RCRA",
        source_title="RCRA",
        root_path=Path(r"C:\Games\RCRA"),
        selected_exe=Path(r"C:\Games\RCRA\RCRA.exe"),
    )
    terms = build_artwork_search_terms(game, preferred="Ratchet & Clank Rift Apart")
    assert terms[0] == "Ratchet & Clank Rift Apart"
    assert "RCRA" in terms


def test_artwork_candidate_score_prefers_matching_release_year() -> None:
    game = DetectedGame(title="God of War", root_path=Path(r"C:\Games\God of War"))
    game.metadata.release_year = "2018"
    old_console_match = {"name": "God of War", "release_date": "2005-03-22"}
    modern_match = {"name": "God of War", "release_date": "2018-04-20"}
    assert release_year_from_text("Apr 20, 2018") == "2018"
    assert artwork_candidate_score(game, "God of War", modern_match) > artwork_candidate_score(game, "God of War", old_console_match)


def test_path_and_store_media_fallbacks_are_stable() -> None:
    expected_path = r"D:\pcgame" if os.name == "nt" else "D:/pcgame"
    assert normalize_windows_path_text("D:/pcgame") == expected_path
    assert find_steam_app("Ghost of Tsushima DC") == {"id": 2215430, "name": "Ghost of Tsushima DIRECTOR'S CUT"}
    official = official_steam_assets(2215430, "Ghost of Tsushima DIRECTOR'S CUT")
    assert any("store_item_assets" in asset.url for asset in official["wide"])
    assets = steam_store_media_assets(
        2215430,
        "Ghost of Tsushima DIRECTOR'S CUT",
        {
            "header_image": "https://example.invalid/header.jpg",
            "background": "https://example.invalid/background.jpg",
            "screenshots": [{"path_full": "https://example.invalid/screenshot.jpg"}],
        },
    )
    assert assets["wide"]
    assert assets["hero"]
    assert assets["icon"]


def test_artwork_cache_key_and_api_links_are_stable() -> None:
    assert normalized_artwork_cache_key("  God   of WAR  ") == "god of war"
    assert STEAMGRIDDB_API_URL == "https://www.steamgriddb.com/profile/preferences/api"
    assert RAWG_API_URL.startswith("https://rawg.io/")


if __name__ == "__main__":
    test_vdf_roundtrip()
    test_scanner_ranks_primary_exe()
    test_title_normalization_handles_god_of_war_and_gta()
    test_scanner_uses_root_exe_title_instead_of_collection_name()
    test_scanner_prefers_root_title_exe_over_unrelated_shipping_codename()
    test_scanner_reports_games_as_they_are_ranked()
    test_scanner_detects_exes_but_leaves_games_unselected_by_default()
    test_scanner_detects_native_linux_launch_candidates()
    test_linux_steam_path_can_be_validated()
    test_upsert_and_duplicate_marking()
    test_malformed_shortcuts_vdf_is_backed_up_and_replaced()
    test_combined_scan_keeps_folder_row_writable_when_shortcut_exists()
    test_combined_scan_merges_existing_shortcut_when_scan_picks_different_exe()
    test_rescan_title_match_remembers_existing_shortcut_exe()
    test_nonsteam_shortcut_title_merge_does_not_absorb_native_steam_game()
    test_metadata_notes_are_marked_and_updated()
    test_metadata_scrape_populates_nonsteam_notes()
    test_bad_short_metadata_title_does_not_replace_folder_title()
    test_metadata_scrape_preserves_user_edited_notes()
    test_preview_shows_exact_notes_payload()
    test_selected_executable_is_written_to_shortcut()
    test_manual_title_override_is_written_to_shortcut()
    test_native_steam_game_notes_are_not_written()
    test_native_steam_game_artwork_can_be_replaced_without_shortcuts()
    test_native_steam_game_shortcut_is_not_upserted()
    test_grid_artwork_writes_both_steam_grid_slots()
    test_user_edited_notes_are_preserved_when_written()
    test_artwork_slot_fallbacks_cover_big_picture_slots()
    test_theme_palettes_are_visibly_distinct()
    test_settings_roundtrip_includes_view_and_metadata_options()
    test_game_list_columns_remove_confidence_from_defaults()
    test_clear_cached_artwork_removes_downloads_and_search_cache_only()
    test_individual_artwork_search_deletes_only_that_games_cached_files()
    test_list_artwork_search_clears_cache_for_selected_current_view_games()
    test_reset_settings_to_defaults_rewrites_settings_file()
    test_artwork_search_terms_prefer_folder_title_and_logical_aliases()
    test_artwork_search_terms_use_typed_title_first()
    test_artwork_candidate_score_prefers_matching_release_year()
    test_path_and_store_media_fallbacks_are_stable()
    test_artwork_cache_key_and_api_links_are_stable()
    print("Smoke tests passed.")
