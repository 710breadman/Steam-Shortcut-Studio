from __future__ import annotations

from pathlib import Path
from typing import Callable

from ..models import DetectedGame
from ..scanner import GameScanner
from .base import (
    SourceIssue,
    SourceLibraryItem,
    SourceScanResult,
    stable_source_item_id,
)


LOCAL_FOLDER_SOURCE = "folder"


def _candidate_metadata(game: DetectedGame) -> list[dict[str, object]]:
    return [
        {
            "path": str(candidate.path),
            "score": candidate.score,
            "confidence": candidate.confidence,
            "size_bytes": candidate.size_bytes,
            "depth": candidate.depth,
            "reasons": list(candidate.reasons),
        }
        for candidate in game.candidates
    ]


class FolderScannerAdapter:
    """Normalize the existing loose-folder scanner into persistent source items."""

    source_name = LOCAL_FOLDER_SOURCE

    def __init__(
        self,
        root: Path | str,
        *,
        scanner_factory: Callable[[], GameScanner] = GameScanner,
    ) -> None:
        self.root = Path(root).expanduser()
        self.scanner_factory = scanner_factory

    def scan(self) -> SourceScanResult:
        if not self.root.is_dir():
            return SourceScanResult(
                source=self.source_name,
                issues=(
                    SourceIssue(
                        source=self.source_name,
                        code="collection_root_missing",
                        message="Local game collection folder does not exist.",
                        record_path=str(self.root),
                        severity="info",
                    ),
                ),
            )

        try:
            games = self.scanner_factory().scan(self.root)
        except Exception as exc:
            return SourceScanResult(
                source=self.source_name,
                issues=(
                    SourceIssue(
                        source=self.source_name,
                        code="folder_scan_failed",
                        message=f"Local game folder scan failed: {type(exc).__name__}: {exc}",
                        record_path=str(self.root),
                        severity="error",
                    ),
                ),
            )

        items: list[SourceLibraryItem] = []
        issues: list[SourceIssue] = []
        seen_ids: set[str] = set()

        for game in games:
            install_path = str(game.root_path)
            launch_target = str(game.selected_exe) if game.selected_exe else ""
            stable_id = stable_source_item_id(
                self.source_name,
                install_path=install_path,
                title=game.title,
            )
            if stable_id in seen_ids:
                issues.append(
                    SourceIssue(
                        source=self.source_name,
                        code="duplicate_folder_identity",
                        message="Multiple folder scan rows resolved to the same stable identity.",
                        record_path=install_path,
                    )
                )
                continue
            seen_ids.add(stable_id)

            launch_exists: bool | None
            if game.selected_exe is None:
                launch_exists = False
                issues.append(
                    SourceIssue(
                        source=self.source_name,
                        code="launch_target_needs_review",
                        message="No launch target was selected for this local game.",
                        record_path=install_path,
                        item_external_id=stable_id,
                    )
                )
            else:
                try:
                    launch_exists = game.selected_exe.is_file()
                except OSError:
                    launch_exists = False
                if not launch_exists:
                    issues.append(
                        SourceIssue(
                            source=self.source_name,
                            code="launch_target_missing",
                            message="The selected local launch target does not exist.",
                            record_path=launch_target,
                            item_external_id=stable_id,
                        )
                    )

            evidence = ["Local collection folder"]
            if game.source_title:
                evidence.append("Original folder/source title")
            if game.selected_exe:
                evidence.append("Ranked executable candidate")

            items.append(
                SourceLibraryItem(
                    stable_id=stable_id,
                    source=self.source_name,
                    external_id="",
                    title=game.display_title,
                    install_path=install_path,
                    launch_target=launch_target,
                    launch_arguments=game.launch_options,
                    working_directory=(
                        str(game.selected_exe.parent)
                        if game.selected_exe
                        else install_path
                    ),
                    platform="windows" if game.selected_exe and game.selected_exe.suffix.casefold() == ".exe" else "pc",
                    source_record_path=install_path,
                    launch_target_exists=launch_exists,
                    evidence=tuple(evidence),
                    metadata={
                        "source_title": game.source_title,
                        "source_type": game.source_type,
                        "candidate_count": len(game.candidates),
                        "candidates": _candidate_metadata(game),
                    },
                )
            )

        items.sort(key=lambda item: (item.title.casefold(), item.stable_id))
        return SourceScanResult(self.source_name, tuple(items), tuple(issues))
