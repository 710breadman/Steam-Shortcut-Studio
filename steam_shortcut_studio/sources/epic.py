from __future__ import annotations

import json
import os
from pathlib import Path, PureWindowsPath
from typing import Mapping

from .base import (
    SourceIssue,
    SourceLibraryItem,
    SourceScanResult,
    stable_source_item_id,
)


EPIC_SOURCE_NAME = "epic"
EPIC_MANIFEST_RELATIVE_PATH = Path("Epic") / "EpicGamesLauncher" / "Data" / "Manifests"


def default_epic_manifest_dir(environment: Mapping[str, str] | None = None) -> Path | None:
    env = environment if environment is not None else os.environ
    program_data = str(env.get("PROGRAMDATA", "")).strip()
    if not program_data:
        return None
    return Path(program_data) / EPIC_MANIFEST_RELATIVE_PATH


def _as_bool(value: object, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value or "").strip().casefold()
    if text in {"true", "yes", "1", "on"}:
        return True
    if text in {"false", "no", "0", "off"}:
        return False
    return default


def _as_nonnegative_int(value: object) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _looks_like_windows_path(value: str) -> bool:
    text = str(value or "")
    return bool(
        "\\" in text
        or (len(text) >= 2 and text[1] == ":")
        or text.startswith("//")
    )


def resolve_epic_launch_target(install_location: str, launch_executable: str) -> str:
    install_text = str(install_location or "").strip().strip('"')
    executable_text = str(launch_executable or "").strip().strip('"')
    if not executable_text:
        return ""

    if _looks_like_windows_path(install_text) or _looks_like_windows_path(executable_text):
        executable = PureWindowsPath(executable_text)
        if executable.is_absolute() or executable.drive:
            return str(executable)
        return str(PureWindowsPath(install_text) / executable)

    executable = Path(executable_text)
    if executable.is_absolute():
        return str(executable)
    return str(Path(install_text) / executable)


def _working_directory(install_location: str, launch_target: str) -> str:
    if not launch_target:
        return install_location
    if _looks_like_windows_path(launch_target):
        return str(PureWindowsPath(launch_target).parent)
    return str(Path(launch_target).parent)


def _launch_target_exists(launch_target: str) -> bool | None:
    if not launch_target:
        return False
    if _looks_like_windows_path(launch_target) and os.name != "nt":
        return None
    try:
        return Path(launch_target).is_file()
    except OSError:
        return False


def _target_is_outside_install(install_location: str, launch_target: str) -> bool:
    if not install_location or not launch_target:
        return False
    if _looks_like_windows_path(install_location) or _looks_like_windows_path(launch_target):
        install = PureWindowsPath(install_location)
        target = PureWindowsPath(launch_target)
        try:
            target.relative_to(install)
            return False
        except ValueError:
            return True
    try:
        target_path = Path(launch_target).resolve(strict=False)
        install_path = Path(install_location).resolve(strict=False)
        return not target_path.is_relative_to(install_path)
    except OSError:
        return False


class EpicManifestAdapter:
    """Read installed Epic games from Epic Games Launcher `.item` manifests."""

    source_name = EPIC_SOURCE_NAME

    def __init__(
        self,
        manifest_dir: Path | str | None = None,
        *,
        environment: Mapping[str, str] | None = None,
    ) -> None:
        explicit = str(manifest_dir or "").strip()
        self.manifest_dir = Path(explicit) if explicit else default_epic_manifest_dir(environment)

    def scan(self) -> SourceScanResult:
        if self.manifest_dir is None:
            return SourceScanResult(
                source=self.source_name,
                issues=(
                    SourceIssue(
                        source=self.source_name,
                        code="programdata_unavailable",
                        message="PROGRAMDATA is unavailable; Epic manifests could not be located.",
                        severity="info",
                    ),
                ),
            )

        manifest_dir = self.manifest_dir.expanduser()
        if not manifest_dir.is_dir():
            return SourceScanResult(
                source=self.source_name,
                issues=(
                    SourceIssue(
                        source=self.source_name,
                        code="manifest_directory_missing",
                        message="Epic manifest directory does not exist.",
                        record_path=str(manifest_dir),
                        severity="info",
                    ),
                ),
            )

        items: list[SourceLibraryItem] = []
        issues: list[SourceIssue] = []
        seen_ids: set[str] = set()

        for manifest_path in sorted(manifest_dir.glob("*.item"), key=lambda path: path.name.casefold()):
            try:
                payload = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
            except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                issues.append(
                    SourceIssue(
                        source=self.source_name,
                        code="invalid_manifest_json",
                        message=f"Epic manifest could not be read: {exc}",
                        record_path=str(manifest_path),
                        severity="error",
                    )
                )
                continue

            if not isinstance(payload, dict):
                issues.append(
                    SourceIssue(
                        source=self.source_name,
                        code="invalid_manifest_root",
                        message="Epic manifest root is not a JSON object.",
                        record_path=str(manifest_path),
                        severity="error",
                    )
                )
                continue

            parsed = self._parse_manifest(payload, manifest_path)
            if isinstance(parsed, SourceIssue):
                issues.append(parsed)
                continue
            item, item_issues = parsed
            issues.extend(item_issues)
            if item is None:
                continue
            if item.stable_id in seen_ids:
                issues.append(
                    SourceIssue(
                        source=self.source_name,
                        code="duplicate_manifest_identity",
                        message="Another Epic manifest resolved to the same stable identity.",
                        record_path=str(manifest_path),
                        item_external_id=item.external_id,
                    )
                )
                continue
            seen_ids.add(item.stable_id)
            items.append(item)

        items.sort(key=lambda item: (item.title.casefold(), item.external_id.casefold()))
        return SourceScanResult(self.source_name, tuple(items), tuple(issues))

    def _parse_manifest(
        self,
        payload: dict[str, object],
        manifest_path: Path,
    ) -> tuple[SourceLibraryItem | None, list[SourceIssue]] | SourceIssue:
        app_name = str(payload.get("AppName") or "").strip()
        title = str(payload.get("DisplayName") or app_name).strip()
        install_location = str(payload.get("InstallLocation") or "").strip().strip('"')

        if _as_bool(payload.get("bIsIncompleteInstall"), False):
            return SourceIssue(
                source=self.source_name,
                code="incomplete_install_skipped",
                message="Epic manifest represents an incomplete installation.",
                record_path=str(manifest_path),
                item_external_id=app_name,
                severity="info",
            )

        if not _as_bool(payload.get("bIsExecutable"), True):
            return SourceIssue(
                source=self.source_name,
                code="non_executable_component_skipped",
                message="Epic manifest is not an executable application.",
                record_path=str(manifest_path),
                item_external_id=app_name,
                severity="info",
            )

        if not title:
            return SourceIssue(
                source=self.source_name,
                code="missing_title",
                message="Epic manifest has no DisplayName or AppName.",
                record_path=str(manifest_path),
                severity="error",
            )
        if not install_location:
            return SourceIssue(
                source=self.source_name,
                code="missing_install_location",
                message="Epic manifest has no InstallLocation.",
                record_path=str(manifest_path),
                item_external_id=app_name,
                severity="error",
            )

        namespace = str(payload.get("CatalogNamespace") or "").strip()
        catalog_item_id = str(payload.get("CatalogItemId") or "").strip()
        if namespace and catalog_item_id:
            external_id = f"{namespace}:{catalog_item_id}"
        else:
            external_id = app_name

        launch_executable = str(payload.get("LaunchExecutable") or "").strip()
        launch_target = resolve_epic_launch_target(install_location, launch_executable)
        launch_exists = _launch_target_exists(launch_target)
        item_issues: list[SourceIssue] = []

        if not launch_executable:
            item_issues.append(
                SourceIssue(
                    source=self.source_name,
                    code="missing_launch_executable",
                    message="Epic manifest has no LaunchExecutable; manual launch selection is required.",
                    record_path=str(manifest_path),
                    item_external_id=external_id,
                )
            )
        elif launch_exists is False:
            item_issues.append(
                SourceIssue(
                    source=self.source_name,
                    code="launch_target_missing",
                    message="Epic launch target does not currently exist.",
                    record_path=str(manifest_path),
                    item_external_id=external_id,
                )
            )

        if launch_target and _target_is_outside_install(install_location, launch_target):
            item_issues.append(
                SourceIssue(
                    source=self.source_name,
                    code="launch_target_outside_install",
                    message="Epic launch target resolves outside InstallLocation and requires review.",
                    record_path=str(manifest_path),
                    item_external_id=external_id,
                )
            )

        evidence = ["Epic Games Launcher .item manifest"]
        if namespace and catalog_item_id:
            evidence.append("Epic catalog namespace and item ID")
        if launch_executable:
            evidence.append("Epic LaunchExecutable")
        if str(payload.get("InstallationGuid") or "").strip():
            evidence.append("Epic installation GUID")

        item = SourceLibraryItem(
            stable_id=stable_source_item_id(
                self.source_name,
                external_id=external_id,
                install_path=install_location,
                title=title,
            ),
            source=self.source_name,
            external_id=external_id,
            title=title,
            install_path=install_location,
            launch_target=launch_target,
            launch_arguments=str(payload.get("LaunchCommand") or "").strip(),
            working_directory=_working_directory(install_location, launch_target),
            platform="windows",
            version=str(payload.get("AppVersionString") or "").strip(),
            size_bytes=_as_nonnegative_int(payload.get("InstallSize")),
            source_record_path=str(manifest_path),
            launch_target_exists=launch_exists,
            evidence=tuple(evidence),
            metadata={
                "app_name": app_name,
                "catalog_namespace": namespace,
                "catalog_item_id": catalog_item_id,
                "installation_guid": str(payload.get("InstallationGuid") or "").strip(),
                "main_game_app_name": str(payload.get("MainGameAppName") or "").strip(),
                "can_run_offline": _as_bool(payload.get("bCanRunOffline"), True),
                "needs_validation": _as_bool(payload.get("bNeedsValidation"), False),
                "install_tags": list(payload.get("InstallTags") or []),
            },
        )
        return item, item_issues
