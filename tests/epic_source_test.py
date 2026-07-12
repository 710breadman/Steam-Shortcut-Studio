from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from steam_shortcut_studio.sources.base import stable_source_item_id  # noqa: E402
from steam_shortcut_studio.sources.epic import (  # noqa: E402
    EpicManifestAdapter,
    default_epic_manifest_dir,
    resolve_epic_launch_target,
)


def _write_manifest(directory: Path, name: str, payload: dict[str, object]) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{name}.item"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _base_manifest(install: Path) -> dict[str, object]:
    return {
        "AppName": "ExampleApp",
        "DisplayName": "Example Game",
        "CatalogNamespace": "example-namespace",
        "CatalogItemId": "example-item",
        "InstallLocation": str(install),
        "LaunchExecutable": "Binaries/Example.exe",
        "LaunchCommand": "-AUTH_LOGIN=unused -windowed",
        "AppVersionString": "1.2.3",
        "InstallSize": 123456,
        "InstallationGuid": "installation-guid",
        "MainGameAppName": "ExampleApp",
        "InstallTags": ["en"],
        "bCanRunOffline": True,
        "bIsExecutable": True,
        "bIsIncompleteInstall": False,
        "bNeedsValidation": False,
    }


def test_default_manifest_path_uses_programdata() -> None:
    path = default_epic_manifest_dir({"PROGRAMDATA": r"C:\ProgramData"})
    assert path is not None
    assert str(path).replace("\\", "/").endswith(
        "C:/ProgramData/Epic/EpicGamesLauncher/Data/Manifests"
    )
    assert default_epic_manifest_dir({}) is None


def test_valid_manifest_produces_authoritative_launch_item() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        manifests = root / "Manifests"
        install = root / "Games" / "Example"
        executable = install / "Binaries" / "Example.exe"
        executable.parent.mkdir(parents=True)
        executable.write_bytes(b"MZ")
        manifest = _write_manifest(manifests, "example", _base_manifest(install))

        result = EpicManifestAdapter(manifests).scan()

        assert result.item_count == 1
        item = result.items[0]
        assert item.source == "epic"
        assert item.external_id == "example-namespace:example-item"
        assert item.title == "Example Game"
        assert Path(item.install_path) == install
        assert Path(item.launch_target) == executable
        assert item.launch_arguments.endswith("-windowed")
        assert Path(item.working_directory) == executable.parent
        assert item.launch_target_exists is True
        assert item.version == "1.2.3"
        assert item.size_bytes == 123456
        assert item.source_record_path == str(manifest)
        assert "Epic LaunchExecutable" in item.evidence
        assert item.metadata["installation_guid"] == "installation-guid"
        assert result.issues == ()


def test_incomplete_and_non_executable_components_are_skipped() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        manifests = root / "Manifests"
        incomplete = _base_manifest(root / "Incomplete")
        incomplete["AppName"] = "Incomplete"
        incomplete["CatalogItemId"] = "incomplete"
        incomplete["bIsIncompleteInstall"] = True
        component = _base_manifest(root / "Component")
        component["AppName"] = "Component"
        component["CatalogItemId"] = "component"
        component["bIsExecutable"] = False
        _write_manifest(manifests, "incomplete", incomplete)
        _write_manifest(manifests, "component", component)

        result = EpicManifestAdapter(manifests).scan()

        assert result.items == ()
        assert {issue.code for issue in result.issues} == {
            "incomplete_install_skipped",
            "non_executable_component_skipped",
        }


def test_malformed_manifest_is_reported_without_aborting_other_games() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        manifests = root / "Manifests"
        manifests.mkdir()
        (manifests / "broken.item").write_text("not json", encoding="utf-8")
        install = root / "Valid"
        _write_manifest(manifests, "valid", _base_manifest(install))

        result = EpicManifestAdapter(manifests).scan()

        assert result.item_count == 1
        assert any(issue.code == "invalid_manifest_json" for issue in result.issues)


def test_missing_launch_executable_is_retained_for_manual_review() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        manifests = root / "Manifests"
        payload = _base_manifest(root / "Game")
        payload["LaunchExecutable"] = ""
        _write_manifest(manifests, "missing-launch", payload)

        result = EpicManifestAdapter(manifests).scan()

        assert result.item_count == 1
        assert result.items[0].launch_target == ""
        assert result.items[0].launch_target_exists is False
        assert any(issue.code == "missing_launch_executable" for issue in result.issues)


def test_launch_target_outside_install_is_flagged_for_review() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        manifests = root / "Manifests"
        payload = _base_manifest(root / "Game")
        payload["LaunchExecutable"] = str(root / "Shared" / "Launcher.exe")
        _write_manifest(manifests, "outside", payload)

        result = EpicManifestAdapter(manifests).scan()

        assert result.item_count == 1
        assert any(issue.code == "launch_target_outside_install" for issue in result.issues)


def test_source_ids_and_windows_target_resolution_are_deterministic() -> None:
    first = stable_source_item_id("epic", external_id="Namespace:Item")
    second = stable_source_item_id("EPIC", external_id=" namespace:item ")
    assert first == second
    assert resolve_epic_launch_target(
        r"C:\Games\Example",
        r"Binaries\Win64\Example.exe",
    ) == r"C:\Games\Example\Binaries\Win64\Example.exe"


if __name__ == "__main__":
    test_default_manifest_path_uses_programdata()
    test_valid_manifest_produces_authoritative_launch_item()
    test_incomplete_and_non_executable_components_are_skipped()
    test_malformed_manifest_is_reported_without_aborting_other_games()
    test_missing_launch_executable_is_retained_for_manual_review()
    test_launch_target_outside_install_is_flagged_for_review()
    test_source_ids_and_windows_target_resolution_are_deterministic()
    print("Epic source adapter tests passed.")
