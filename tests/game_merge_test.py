from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from steam_shortcut_studio.game_merge import (  # noqa: E402
    apply_existing_shortcut_choices,
    compare_games_with_shortcuts,
    game_identity_keys,
    merge_detected_game_lists,
    normalized_artwork_cache_key,
)
from steam_shortcut_studio.models import DetectedGame, ExecutableCandidate  # noqa: E402
from steam_shortcut_studio.steam_shortcuts import ShortcutRecord, generate_appid, mark_existing_shortcuts  # noqa: E402


def _write_fake_exe(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"MZ" + (b"\0" * 510))


def test_identity_keys_prefer_stable_known_ids() -> None:
    steam_game = DetectedGame(title="Steam Game", root_path=Path(), source_type="steam", steam_appid=123)
    shortcut_game = DetectedGame(title="Shortcut", root_path=Path(), existing_appid=-456)
    folder_game = DetectedGame(title="Folder", root_path=Path(r"C:\Games\Folder"))

    assert game_identity_keys(steam_game) == {("steam", "123")}
    assert ("shortcut-appid", "-456") in game_identity_keys(shortcut_game)
    assert game_identity_keys(folder_game) == {("folder", "folder")}
    assert normalized_artwork_cache_key("  Ghost   OF Tsushima  ") == "ghost of tsushima"


def test_merge_detected_games_keeps_native_steam_distinct_from_shortcut_title_match() -> None:
    steam_game = DetectedGame(title="Example", root_path=Path(), source_type="steam", steam_appid=123)
    shortcut_game = DetectedGame(
        title="Example",
        root_path=Path(r"C:\Games\Example"),
        selected_exe=Path(r"C:\Games\Example\Example.exe"),
        source_type="shortcut",
        existing_appid=-123,
    )

    merged = merge_detected_game_lists([steam_game], [shortcut_game])

    assert merged == [steam_game, shortcut_game]


def test_existing_shortcut_choices_restore_remembered_launch_target() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        remembered_exe = root / "Games" / "Example" / "Remembered.exe"
        scanned_exe = root / "Games" / "Example" / "Engine" / "Project.exe"
        _write_fake_exe(remembered_exe)
        _write_fake_exe(scanned_exe)
        record = ShortcutRecord(
            appid=generate_appid(remembered_exe, "Example"),
            app_name="Example",
            exe=f'"{remembered_exe}"',
            start_dir=f'"{remembered_exe.parent}"',
            launch_options="-old-option",
            tags=["ManualTag"],
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
                    depth=2,
                )
            ],
            source_type="folder",
        )
        mark_existing_shortcuts([game], [record])

        apply_existing_shortcut_choices([game], [record])

        assert game.selected_exe == remembered_exe
        assert game.candidates[0].path == remembered_exe
        assert game.existing_appid == record.appid
        assert game.launch_options == "-old-option"


def test_compare_games_with_shortcuts_can_include_existing_nonsteam_rows() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        exe = root / "Games" / "Example" / "Example.exe"
        _write_fake_exe(exe)
        record = ShortcutRecord(
            appid=generate_appid(exe, "Example"),
            app_name="Example",
            exe=f'"{exe}"',
            start_dir=f'"{exe.parent}"',
            launch_options="-old-option",
        )
        scanned = DetectedGame(title="Example", root_path=exe.parent, selected_exe=exe, source_type="folder")

        result = compare_games_with_shortcuts([scanned], [record], include_nonsteam_games=True)

        assert result.shortcut_count == 1
        assert len(result.games) == 1
        assert result.games[0].existing_appid == record.appid
        assert result.games[0].launch_options == "-old-option"


if __name__ == "__main__":
    test_identity_keys_prefer_stable_known_ids()
    test_merge_detected_games_keeps_native_steam_distinct_from_shortcut_title_match()
    test_existing_shortcut_choices_restore_remembered_launch_target()
    test_compare_games_with_shortcuts_can_include_existing_nonsteam_rows()
    print("Game merge tests passed.")
