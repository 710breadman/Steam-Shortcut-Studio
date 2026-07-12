from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from steam_shortcut_studio.models import DetectedGame, ExecutableCandidate  # noqa: E402
from steam_shortcut_studio.sources.local import FolderScannerAdapter  # noqa: E402
from steam_shortcut_studio.sources.steam import SteamLibraryAdapter  # noqa: E402


class FakeFolderScanner:
    def __init__(self, games: list[DetectedGame] | None = None, error: Exception | None = None) -> None:
        self.games = games or []
        self.error = error

    def scan(self, root: Path) -> list[DetectedGame]:
        if self.error is not None:
            raise self.error
        return self.games


def test_folder_adapter_normalizes_ranked_launch_target_and_candidates() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "Games"
        game_root = root / "Example"
        executable = game_root / "Example.exe"
        executable.parent.mkdir(parents=True)
        executable.write_bytes(b"MZ")
        candidate = ExecutableCandidate(
            path=executable,
            score=88,
            confidence=91,
            size_bytes=2,
            depth=1,
            reasons=["Matches game title"],
        )
        game = DetectedGame(
            title="Example",
            source_title="Example Folder",
            root_path=game_root,
            selected_exe=executable,
            candidates=[candidate],
            launch_options="-windowed",
            source_type="folder",
        )
        adapter = FolderScannerAdapter(
            root,
            scanner_factory=lambda: FakeFolderScanner([game]),
        )

        result = adapter.scan()

        assert result.item_count == 1
        item = result.items[0]
        assert item.source == "folder"
        assert item.title == "Example"
        assert Path(item.install_path) == game_root
        assert Path(item.launch_target) == executable
        assert item.launch_arguments == "-windowed"
        assert item.launch_target_exists is True
        assert item.metadata["candidate_count"] == 1
        candidates = item.metadata["candidates"]
        assert isinstance(candidates, list)
        assert candidates[0]["score"] == 88
        assert result.issues == ()


def test_folder_adapter_keeps_games_needing_manual_launch_review() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "Games"
        game_root = root / "Needs Review"
        game_root.mkdir(parents=True)
        game = DetectedGame(
            title="Needs Review",
            root_path=game_root,
            selected_exe=None,
            candidates=[],
            source_type="folder",
        )
        result = FolderScannerAdapter(
            root,
            scanner_factory=lambda: FakeFolderScanner([game]),
        ).scan()

        assert result.item_count == 1
        assert result.items[0].launch_target == ""
        assert result.items[0].launch_target_exists is False
        assert any(issue.code == "launch_target_needs_review" for issue in result.issues)


def test_folder_adapter_missing_root_and_scan_failure_are_non_destructive_issues() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "Missing"
        missing = FolderScannerAdapter(root).scan()
        assert missing.items == ()
        assert missing.issues[0].code == "collection_root_missing"
        assert missing.issues[0].severity == "info"

        root.mkdir()
        failed = FolderScannerAdapter(
            root,
            scanner_factory=lambda: FakeFolderScanner(error=RuntimeError("boom")),
        ).scan()
        assert failed.items == ()
        assert failed.issues[0].code == "folder_scan_failed"
        assert failed.issues[0].severity == "error"


def test_steam_adapter_normalizes_native_game_identity_and_uri() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        steam_root = Path(tmp) / "Steam"
        install = steam_root / "steamapps" / "common" / "Native Example"
        install.mkdir(parents=True)
        game = DetectedGame(
            title="Native Example",
            source_title="Native Example",
            root_path=install,
            source_type="steam",
            steam_appid=424242,
        )
        adapter = SteamLibraryAdapter(
            steam_root,
            scan_function=lambda root: [game],
        )

        result = adapter.scan()

        assert result.item_count == 1
        item = result.items[0]
        assert item.source == "steam"
        assert item.external_id == "424242"
        assert item.title == "Native Example"
        assert item.launch_target == "steam://rungameid/424242"
        assert item.install_path == str(install)
        assert item.launch_target_exists is True
        assert item.metadata["steam_appid"] == 424242
        assert item.metadata["is_native_steam_game"] is True
        assert result.issues == ()


def test_steam_adapter_reports_missing_installs_duplicates_and_invalid_appids() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        steam_root = Path(tmp) / "Steam"
        steam_root.mkdir()
        missing_install = steam_root / "steamapps" / "common" / "Missing"
        valid = DetectedGame(
            title="Missing",
            root_path=missing_install,
            source_type="steam",
            steam_appid=10,
        )
        duplicate = DetectedGame(
            title="Duplicate",
            root_path=missing_install,
            source_type="steam",
            steam_appid=10,
        )
        invalid = DetectedGame(
            title="Invalid",
            root_path=missing_install,
            source_type="steam",
            steam_appid=None,
        )

        result = SteamLibraryAdapter(
            steam_root,
            scan_function=lambda root: [valid, duplicate, invalid],
        ).scan()

        assert result.item_count == 1
        assert result.items[0].launch_target_exists is False
        assert {issue.code for issue in result.issues} == {
            "steam_install_path_missing",
            "duplicate_steam_appid",
            "missing_steam_appid",
        }


def test_steam_adapter_missing_root_and_scan_failure_are_reported() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "MissingSteam"
        missing = SteamLibraryAdapter(root).scan()
        assert missing.issues[0].code == "steam_root_missing"
        assert missing.issues[0].severity == "info"

        root.mkdir()

        def fail(_root: Path) -> list[DetectedGame]:
            raise RuntimeError("steam parser failed")

        failed = SteamLibraryAdapter(root, scan_function=fail).scan()
        assert failed.issues[0].code == "steam_scan_failed"
        assert failed.issues[0].severity == "error"


if __name__ == "__main__":
    test_folder_adapter_normalizes_ranked_launch_target_and_candidates()
    test_folder_adapter_keeps_games_needing_manual_launch_review()
    test_folder_adapter_missing_root_and_scan_failure_are_non_destructive_issues()
    test_steam_adapter_normalizes_native_game_identity_and_uri()
    test_steam_adapter_reports_missing_installs_duplicates_and_invalid_appids()
    test_steam_adapter_missing_root_and_scan_failure_are_reported()
    print("Steam and folder source adapter tests passed.")
