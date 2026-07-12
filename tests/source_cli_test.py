from __future__ import annotations

import io
import json
import sys
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from steam_shortcut_studio.library_store import LibraryStore  # noqa: E402
from steam_shortcut_studio.source_cli import main  # noqa: E402
from steam_shortcut_studio.sources.base import SourceLibraryItem, stable_source_item_id  # noqa: E402


def _run(arguments: list[str]) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        code = main(arguments)
    return code, stdout.getvalue(), stderr.getvalue()


def _write_fake_exe(path: Path, size: int = 1024 * 1024) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = bytearray(max(size, 512))
    data[0:2] = b"MZ"
    data[0x3C:0x40] = (0x80).to_bytes(4, "little")
    data[0x80:0x84] = b"PE\x00\x00"
    data[0x84:0x86] = (0x8664).to_bytes(2, "little")
    data[0x98:0x9A] = (0x20B).to_bytes(2, "little")
    data[0x80 + 24 + 108 : 0x80 + 24 + 110] = (2).to_bytes(2, "little")
    path.write_bytes(data)


def test_scan_folder_persists_real_scanner_result() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        games = root / "Games"
        executable = games / "Example Game" / "ExampleGame.exe"
        _write_fake_exe(executable)
        database = root / "library.sqlite3"

        code, output, error = _run(
            [
                "scan-folder",
                "--root",
                str(games),
                "--database",
                str(database),
                "--json",
            ]
        )
        payload = json.loads(output)

        assert code == 0
        assert error == ""
        assert payload["source"] == "folder"
        assert payload["detected_items"] == 1
        assert payload["snapshot"]["inserted"] == 1
        records = LibraryStore(database).list_records(source="folder")
        assert len(records) == 1
        assert records[0].title == "Example Game"
        assert Path(records[0].launch_target) == executable


def test_missing_folder_root_is_blocked_and_preserves_previous_snapshot() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        database = root / "library.sqlite3"
        store = LibraryStore(database)
        item = SourceLibraryItem(
            stable_id=stable_source_item_id(
                "folder",
                install_path=str(root / "Old Game"),
                title="Old Game",
            ),
            source="folder",
            external_id="",
            title="Old Game",
            install_path=str(root / "Old Game"),
            launch_target=str(root / "Old Game" / "Old.exe"),
        )
        store.replace_source_snapshot("folder", [item])

        code, output, error = _run(
            [
                "scan-folder",
                "--root",
                str(root / "Missing"),
                "--database",
                str(database),
                "--json",
            ]
        )
        payload = json.loads(output)

        assert code == 2
        assert error == ""
        assert payload["persisted"] is False
        assert payload["authoritative"] is False
        existing = LibraryStore(database).get_record(item.stable_id)
        assert existing is not None and existing.is_present is True


def test_missing_steam_root_is_blocked_and_preserves_previous_snapshot() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        database = root / "library.sqlite3"
        store = LibraryStore(database)
        item = SourceLibraryItem(
            stable_id=stable_source_item_id("steam", external_id="424242"),
            source="steam",
            external_id="424242",
            title="Native Example",
            install_path=str(root / "Steam" / "Native Example"),
            launch_target="steam://rungameid/424242",
        )
        store.replace_source_snapshot("steam", [item])

        code, output, error = _run(
            [
                "scan-steam",
                "--steam-root",
                str(root / "MissingSteam"),
                "--database",
                str(database),
                "--json",
            ]
        )
        payload = json.loads(output)

        assert code == 2
        assert error == ""
        assert payload["persisted"] is False
        assert payload["authoritative"] is False
        existing = LibraryStore(database).get_record(item.stable_id)
        assert existing is not None and existing.is_present is True


def test_human_output_is_clear_for_blocked_scan() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        code, output, error = _run(
            [
                "scan-steam",
                "--steam-root",
                str(root / "MissingSteam"),
                "--database",
                str(root / "library.sqlite3"),
            ]
        )
        assert code == 2
        assert error == ""
        assert "Steam scan: BLOCKED" in output
        assert "Stored library presence was not changed" in output
        assert "steam_root_missing" in output


if __name__ == "__main__":
    test_scan_folder_persists_real_scanner_result()
    test_missing_folder_root_is_blocked_and_preserves_previous_snapshot()
    test_missing_steam_root_is_blocked_and_preserves_previous_snapshot()
    test_human_output_is_clear_for_blocked_scan()
    print("Steam and folder source CLI tests passed.")
