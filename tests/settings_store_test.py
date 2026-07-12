from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from steam_shortcut_studio.settings_store import SettingsStore  # noqa: E402


def test_legacy_column_settings_gain_library_columns() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        settings_path = Path(tmp) / "settings.json"
        settings_path.write_text(
            json.dumps(
                {
                    "visible_game_columns": ["add", "title", "exe", "artwork", "existing"],
                    "game_column_order": ["add", "title", "exe", "artwork", "existing"],
                }
            ),
            encoding="utf-8",
        )

        settings = SettingsStore(settings_path).load()

        assert settings.visible_game_columns == [
            "add",
            "title",
            "source",
            "platform",
            "status",
            "exe",
            "artwork",
            "existing",
        ]
        assert settings.game_column_order == settings.visible_game_columns


if __name__ == "__main__":
    test_legacy_column_settings_gain_library_columns()
    print("Settings store tests passed.")
