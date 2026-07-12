from __future__ import annotations

import io
import json
import sys
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from steam_shortcut_studio.cli import main  # noqa: E402


def _manifest(install: Path) -> dict[str, object]:
    return {
        "AppName": "ExampleApp",
        "DisplayName": "Example Game",
        "CatalogNamespace": "namespace",
        "CatalogItemId": "item",
        "InstallLocation": str(install),
        "LaunchExecutable": "Example.exe",
        "LaunchCommand": "-windowed",
        "bIsExecutable": True,
        "bIsIncompleteInstall": False,
    }


def _run(arguments: list[str]) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        code = main(arguments)
    return code, stdout.getvalue(), stderr.getvalue()


def test_cli_scans_epic_and_lists_persisted_library_as_json() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        manifests = root / "Manifests"
        manifests.mkdir()
        install = root / "Games" / "Example"
        install.mkdir(parents=True)
        (install / "Example.exe").write_bytes(b"MZ")
        (manifests / "example.item").write_text(
            json.dumps(_manifest(install)),
            encoding="utf-8",
        )
        database = root / "library.sqlite3"

        scan_code, scan_output, scan_error = _run(
            [
                "scan-epic",
                "--manifest-dir",
                str(manifests),
                "--database",
                str(database),
                "--json",
            ]
        )
        payload = json.loads(scan_output)

        assert scan_code == 0
        assert scan_error == ""
        assert payload["status"] == "completed"
        assert payload["detected_items"] == 1
        assert payload["snapshot"] == {
            "inserted": 1,
            "marked_missing": 0,
            "updated": 0,
        }

        list_code, list_output, list_error = _run(
            [
                "list-library",
                "--database",
                str(database),
                "--source",
                "epic",
                "--json",
            ]
        )
        items = json.loads(list_output)

        assert list_code == 0
        assert list_error == ""
        assert len(items) == 1
        assert items[0]["display_title"] == "Example Game"
        assert Path(items[0]["launch_target"]) == install / "Example.exe"
        assert items[0]["is_present"] is True


def test_cli_partial_scan_returns_blocked_without_clearing_library() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        manifests = root / "Manifests"
        manifests.mkdir()
        install = root / "Example"
        install.mkdir()
        (manifests / "example.item").write_text(
            json.dumps(_manifest(install)),
            encoding="utf-8",
        )
        database = root / "library.sqlite3"

        first_code, _, _ = _run(
            [
                "scan-epic",
                "--manifest-dir",
                str(manifests),
                "--database",
                str(database),
            ]
        )
        blocked_code, blocked_output, blocked_error = _run(
            [
                "scan-epic",
                "--manifest-dir",
                str(root / "Missing"),
                "--database",
                str(database),
                "--json",
            ]
        )
        blocked = json.loads(blocked_output)
        _, list_output, _ = _run(
            ["list-library", "--database", str(database), "--json"]
        )

        assert first_code == 0
        assert blocked_code == 2
        assert blocked_error == ""
        assert blocked["persisted"] is False
        assert blocked["authoritative"] is False
        assert "left unchanged" in blocked["error"]
        assert len(json.loads(list_output)) == 1


def test_cli_scan_history_reports_completed_and_failed_runs() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        manifests = root / "Manifests"
        manifests.mkdir()
        install = root / "Example"
        install.mkdir()
        (manifests / "example.item").write_text(
            json.dumps(_manifest(install)),
            encoding="utf-8",
        )
        database = root / "library.sqlite3"

        _run(
            [
                "scan-epic",
                "--manifest-dir",
                str(manifests),
                "--database",
                str(database),
            ]
        )
        _run(
            [
                "scan-epic",
                "--manifest-dir",
                str(root / "Missing"),
                "--database",
                str(database),
            ]
        )
        code, output, error = _run(
            ["scan-history", "--database", str(database), "--json"]
        )
        runs = json.loads(output)

        assert code == 0
        assert error == ""
        assert [run["status"] for run in runs] == ["failed", "completed"]


def test_cli_human_output_and_argument_errors_are_clear() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        database = Path(tmp) / "library.sqlite3"
        code, output, error = _run(
            ["list-library", "--database", str(database)]
        )
        assert code == 0
        assert "No stored library items" in output
        assert error == ""


if __name__ == "__main__":
    test_cli_scans_epic_and_lists_persisted_library_as_json()
    test_cli_partial_scan_returns_blocked_without_clearing_library()
    test_cli_scan_history_reports_completed_and_failed_runs()
    test_cli_human_output_and_argument_errors_are_clear()
    print("CLI tests passed.")
