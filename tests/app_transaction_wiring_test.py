from __future__ import annotations

import tempfile
from pathlib import Path

from steam_shortcut_studio import app  # noqa: F401  (installs production adapters)
from steam_shortcut_studio.models import DetectedGame, SteamProfile
from steam_shortcut_studio.shortcut_transactions import ShortcutWriteBlockedError
from steam_shortcut_studio.ui import preview_changes, upsert_games


def _write_fake_exe(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"MZ" + (b"\x00" * 1022))


def test_desktop_app_blocks_malformed_shortcut_file() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        profile = SteamProfile(
            user_id="123",
            config_dir=root / "Steam" / "userdata" / "123" / "config",
            shortcuts_path=root / "Steam" / "userdata" / "123" / "config" / "shortcuts.vdf",
            grid_dir=root / "Steam" / "userdata" / "123" / "config" / "grid",
        )
        profile.shortcuts_path.parent.mkdir(parents=True, exist_ok=True)
        original = b"\x00shortcuts\x00\x00broken"
        profile.shortcuts_path.write_bytes(original)

        exe = root / "Games" / "Example" / "Example.exe"
        _write_fake_exe(exe)
        game = DetectedGame(
            title="Example",
            root_path=exe.parent,
            selected_exe=exe,
            selected=True,
        )

        preview = preview_changes(profile, [game], update_existing=True, default_tags=[])
        assert "BLOCKED:" in preview
        assert "No changes can be written" in preview

        try:
            upsert_games(profile, [game], update_existing=True, default_tags=[])
        except ShortcutWriteBlockedError as exc:
            assert "No changes were written" in str(exc)
        else:
            raise AssertionError("Desktop app write path did not block malformed shortcuts.vdf")

        assert profile.shortcuts_path.read_bytes() == original
        assert not list(profile.shortcuts_path.parent.glob("shortcuts.vdf.*.bak"))


if __name__ == "__main__":
    test_desktop_app_blocks_malformed_shortcut_file()
    print("App transaction wiring tests passed.")
