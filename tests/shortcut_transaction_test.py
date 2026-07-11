from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from steam_shortcut_studio.file_transactions import FileTransactionVerificationError
from steam_shortcut_studio.models import DetectedGame, SteamProfile
from steam_shortcut_studio.shortcut_transactions import (
    ShortcutWriteBlockedError,
    upsert_games_transactional,
)
from steam_shortcut_studio.steam_shortcuts import (
    ShortcutRecord,
    generate_appid,
    load_shortcuts,
    write_shortcuts_file,
)


def write_fake_exe(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"MZ" + (b"\x00" * 1022))


def make_profile(root: Path) -> SteamProfile:
    config = root / "Steam" / "userdata" / "123" / "config"
    return SteamProfile(
        user_id="123",
        config_dir=config,
        shortcuts_path=config / "shortcuts.vdf",
        grid_dir=config / "grid",
    )


class ShortcutTransactionTests(unittest.TestCase):
    def test_add_preserves_unrelated_records_and_creates_manifest_backup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profile = make_profile(root)
            unrelated_exe = root / "Games" / "Unrelated" / "Unrelated.exe"
            new_exe = root / "Games" / "Example" / "Example.exe"
            write_fake_exe(unrelated_exe)
            write_fake_exe(new_exe)
            unrelated = ShortcutRecord(
                appid=generate_appid(unrelated_exe, "Unrelated"),
                app_name="Unrelated",
                exe=f'"{unrelated_exe}"',
                start_dir=f'"{unrelated_exe.parent}"',
                launch_options="-keep-me",
                allow_overlay=0,
                tags=["ManualTag"],
            )
            write_shortcuts_file(profile.shortcuts_path, [unrelated])
            original_bytes = profile.shortcuts_path.read_bytes()
            game = DetectedGame(
                title="Example",
                root_path=new_exe.parent,
                selected_exe=new_exe,
                selected=True,
            )

            result = upsert_games_transactional(
                profile,
                [game],
                default_tags=["Imported"],
                transaction_root=root / "transactions",
            )

            self.assertEqual((result.added, result.updated), (1, 0))
            self.assertIsNotNone(result.transaction)
            self.assertIsNotNone(result.backup)
            self.assertEqual(result.backup.read_bytes(), original_bytes)
            self.assertTrue(Path(result.transaction.manifest_path).exists())
            records = load_shortcuts(profile.shortcuts_path)
            self.assertEqual(len(records), 2)
            self.assertEqual(records[0], unrelated)
            self.assertEqual(records[1].app_name, "Example")

    def test_update_preserves_user_managed_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profile = make_profile(root)
            exe = root / "Games" / "Example" / "Example.exe"
            write_fake_exe(exe)
            existing = ShortcutRecord(
                appid=generate_appid(exe, "Example"),
                app_name="Example",
                exe=f'"{exe}"',
                start_dir=f'"{exe.parent}"',
                launch_options="-manual-option",
                allow_overlay=0,
                tags=["ManualTag"],
            )
            write_shortcuts_file(profile.shortcuts_path, [existing])
            game = DetectedGame(
                title="Example",
                root_path=exe.parent,
                selected_exe=exe,
                selected=True,
            )
            game.metadata.genres = ["Action"]

            result = upsert_games_transactional(
                profile,
                [game],
                default_tags=["Imported"],
                transaction_root=root / "transactions",
            )

            self.assertEqual((result.added, result.updated), (0, 1))
            updated = load_shortcuts(profile.shortcuts_path)[0]
            self.assertEqual(updated.launch_options, "-manual-option")
            self.assertEqual(updated.allow_overlay, 0)
            self.assertEqual(updated.tags, ["ManualTag", "Non Steam", "Imported", "Action"])

    def test_malformed_active_file_aborts_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profile = make_profile(root)
            profile.shortcuts_path.parent.mkdir(parents=True, exist_ok=True)
            malformed = b"\x00shortcuts\x00\x00broken"
            profile.shortcuts_path.write_bytes(malformed)
            exe = root / "Games" / "Example" / "Example.exe"
            write_fake_exe(exe)
            game = DetectedGame(
                title="Example",
                root_path=exe.parent,
                selected_exe=exe,
                selected=True,
            )

            with self.assertRaises(ShortcutWriteBlockedError):
                upsert_games_transactional(
                    profile,
                    [game],
                    transaction_root=root / "transactions",
                )

            self.assertEqual(profile.shortcuts_path.read_bytes(), malformed)
            self.assertFalse((root / "transactions").exists())

    def test_failed_verification_restores_original_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profile = make_profile(root)
            old_exe = root / "Games" / "Existing" / "Existing.exe"
            new_exe = root / "Games" / "New" / "New.exe"
            write_fake_exe(old_exe)
            write_fake_exe(new_exe)
            existing = ShortcutRecord(
                appid=generate_appid(old_exe, "Existing"),
                app_name="Existing",
                exe=f'"{old_exe}"',
                start_dir=f'"{old_exe.parent}"',
            )
            write_shortcuts_file(profile.shortcuts_path, [existing])
            original = profile.shortcuts_path.read_bytes()
            game = DetectedGame(
                title="New",
                root_path=new_exe.parent,
                selected_exe=new_exe,
                selected=True,
            )

            with self.assertRaises(FileTransactionVerificationError) as raised:
                upsert_games_transactional(
                    profile,
                    [game],
                    transaction_root=root / "transactions",
                    post_write_check=lambda _path: (_ for _ in ()).throw(
                        RuntimeError("injected readback failure")
                    ),
                )

            self.assertEqual(profile.shortcuts_path.read_bytes(), original)
            self.assertEqual(load_shortcuts(profile.shortcuts_path), [existing])
            self.assertTrue(raised.exception.outcome.restore_verified)

    def test_failed_new_file_transaction_leaves_no_active_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profile = make_profile(root)
            exe = root / "Games" / "New" / "New.exe"
            write_fake_exe(exe)
            game = DetectedGame(
                title="New",
                root_path=exe.parent,
                selected_exe=exe,
                selected=True,
            )

            with self.assertRaises(FileTransactionVerificationError):
                upsert_games_transactional(
                    profile,
                    [game],
                    transaction_root=root / "transactions",
                    post_write_check=lambda _path: (_ for _ in ()).throw(
                        RuntimeError("injected failure")
                    ),
                )

            self.assertFalse(profile.shortcuts_path.exists())


if __name__ == "__main__":
    unittest.main()
