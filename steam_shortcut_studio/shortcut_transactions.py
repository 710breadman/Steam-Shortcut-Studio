from __future__ import annotations

import logging
from collections import OrderedDict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable

from .file_transactions import FileTransactionOutcome, apply_verified_file_transaction
from .models import DetectedGame, SteamProfile
from .steam_shortcuts import (
    ShortcutRecord,
    _mapping_from_shortcut,
    load_shortcuts,
    matching_record_for_game,
    merge_shortcut_update,
    normalize_for_match,
    shortcut_from_game,
)
from .vdf import VdfParseError, dump_binary_vdf

LOGGER = logging.getLogger(__name__)
PostWriteCheck = Callable[[Path], None]


class ShortcutWriteBlockedError(RuntimeError):
    """Raised when the existing shortcut file cannot be safely merged."""


@dataclass(slots=True)
class ShortcutTransactionResult:
    added: int = 0
    updated: int = 0
    backup: Path | None = None
    transaction: FileTransactionOutcome | None = None

    def as_legacy_tuple(self) -> tuple[int, int, Path | None]:
        return self.added, self.updated, self.backup


def serialize_shortcuts(records: list[ShortcutRecord]) -> bytes:
    shortcuts_map: OrderedDict[str, object] = OrderedDict()
    for index, record in enumerate(records):
        shortcuts_map[str(index)] = _mapping_from_shortcut(record)
    root: OrderedDict[str, object] = OrderedDict([("shortcuts", shortcuts_map)])
    return dump_binary_vdf(root)


def _normalized_shortcut_record(record: ShortcutRecord) -> dict[str, object]:
    """Return a comparison form that matches Steam's 32-bit AppID semantics.

    Some shortcut writers encode ``appid`` as an unsigned integer while Steam and
    this project's normal writer commonly encode the same 32 bits as a signed
    INT32. Both representations identify the same shortcut. Comparing the raw
    Python integers would reject a valid staged file after a harmless round trip.
    """

    normalized = asdict(record)
    normalized["appid"] = record.unsigned_appid
    return normalized


def shortcut_records_equivalent(
    planned: list[ShortcutRecord],
    observed: list[ShortcutRecord],
) -> bool:
    if len(planned) != len(observed):
        return False
    return all(
        _normalized_shortcut_record(expected) == _normalized_shortcut_record(actual)
        for expected, actual in zip(planned, observed, strict=True)
    )


def _shortcut_record_difference(
    planned: list[ShortcutRecord],
    observed: list[ShortcutRecord],
) -> str:
    if len(planned) != len(observed):
        return f"record count planned={len(planned)} observed={len(observed)}"
    for index, (expected, actual) in enumerate(zip(planned, observed, strict=True)):
        expected_map = _normalized_shortcut_record(expected)
        actual_map = _normalized_shortcut_record(actual)
        for field in expected_map:
            if expected_map[field] != actual_map[field]:
                return f"record {index} field {field!r} planned={expected_map[field]!r} observed={actual_map[field]!r}"
    return "unknown record difference"


def load_shortcuts_strict(path: Path) -> list[ShortcutRecord]:
    if not path.exists():
        return []
    try:
        return load_shortcuts(path)
    except VdfParseError as exc:
        LOGGER.error("Blocked shortcuts.vdf write because the active file is malformed: %s", exc)
        raise ShortcutWriteBlockedError(
            "The existing shortcuts.vdf could not be parsed. No changes were written. "
            "Restore or repair the file before retrying."
        ) from exc


def _merge_selected_games(
    existing: list[ShortcutRecord],
    games: list[DetectedGame],
    *,
    update_existing: bool,
    default_tags: list[str] | None,
) -> tuple[list[ShortcutRecord], int, int, list[DetectedGame]]:
    records = list(existing)
    by_exe = {normalize_for_match(record.exe): index for index, record in enumerate(records)}
    by_title = {record.app_name.casefold(): index for index, record in enumerate(records)}
    added = 0
    updated = 0
    expected_games: list[DetectedGame] = []

    for game in games:
        record = shortcut_from_game(game, default_tags=default_tags)
        exe_key = normalize_for_match(record.exe)
        title_key = record.app_name.casefold()
        match_index = by_exe.get(exe_key)
        if match_index is None:
            match_index = by_title.get(title_key)

        if match_index is not None and update_existing:
            old_exe_key = normalize_for_match(records[match_index].exe)
            old_title_key = records[match_index].app_name.casefold()
            records[match_index] = merge_shortcut_update(records[match_index], record)
            by_exe.pop(old_exe_key, None)
            by_title.pop(old_title_key, None)
            by_exe[normalize_for_match(records[match_index].exe)] = match_index
            by_title[records[match_index].app_name.casefold()] = match_index
            updated += 1
            expected_games.append(game)
        elif match_index is None:
            records.append(record)
            by_exe[exe_key] = len(records) - 1
            by_title[title_key] = len(records) - 1
            added += 1
            expected_games.append(game)

    return records, added, updated, expected_games


def _verify_shortcut_records(
    path: Path,
    expected_records: list[ShortcutRecord],
    expected_games: list[DetectedGame],
) -> None:
    written = load_shortcuts(path)
    if not shortcut_records_equivalent(expected_records, written):
        raise RuntimeError("Shortcut read-back did not match the staged records.")

    missing = [
        game.display_title
        for game in expected_games
        if matching_record_for_game(written, game) is None
    ]
    if missing:
        raise RuntimeError("Shortcut write verification failed for: " + ", ".join(missing))


def upsert_games_transactional(
    profile: SteamProfile,
    games: list[DetectedGame],
    update_existing: bool = True,
    default_tags: list[str] | None = None,
    *,
    transaction_root: Path | None = None,
    post_write_check: PostWriteCheck | None = None,
) -> ShortcutTransactionResult:
    """Safely add/update selected non-Steam shortcuts.

    Malformed active files always abort; they are never silently replaced with a
    fresh shortcut list. Staged and written records are compared using Steam's
    unsigned 32-bit AppID semantics so equivalent signed/unsigned encodings do
    not create false validation failures.
    """

    selected_games = [
        game for game in games if game.selected and game.is_managed_non_steam
    ]
    if not selected_games:
        return ShortcutTransactionResult()

    existing = load_shortcuts_strict(profile.shortcuts_path)
    records, added, updated, expected_games = _merge_selected_games(
        existing,
        selected_games,
        update_existing=update_existing,
        default_tags=default_tags,
    )
    if added == 0 and updated == 0:
        return ShortcutTransactionResult()

    data = serialize_shortcuts(records)

    def validate_staged(path: Path) -> None:
        staged_records = load_shortcuts(path)
        if not shortcut_records_equivalent(records, staged_records):
            detail = _shortcut_record_difference(records, staged_records)
            raise RuntimeError(f"Staged shortcuts.vdf does not match the planned records ({detail}).")

    def verify_written(path: Path) -> None:
        _verify_shortcut_records(path, records, expected_games)
        if post_write_check is not None:
            post_write_check(path)

    outcome = apply_verified_file_transaction(
        profile.shortcuts_path,
        data,
        stage_validator=validate_staged,
        written_verifier=verify_written,
        transaction_root=transaction_root,
    )
    backup = Path(outcome.backup_path) if outcome.backup_path else None
    return ShortcutTransactionResult(
        added=added,
        updated=updated,
        backup=backup,
        transaction=outcome,
    )
