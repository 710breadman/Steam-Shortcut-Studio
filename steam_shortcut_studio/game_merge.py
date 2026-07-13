from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .models import DetectedGame, ExecutableCandidate
from .steam_library import games_from_nonsteam_shortcuts
from .steam_shortcuts import mark_existing_shortcuts, matching_record_for_game


@dataclass(frozen=True, slots=True)
class ShortcutComparisonResult:
    games: list[DetectedGame]
    shortcut_count: int = 0


def normalized_artwork_cache_key(title: str) -> str:
    return " ".join(str(title or "").casefold().strip().split())


def game_identity_keys(game: DetectedGame) -> set[tuple[str, str]]:
    keys: set[tuple[str, str]] = set()
    if game.steam_appid:
        keys.add(("steam", str(game.steam_appid)))
    if not game.is_native_steam_game and game.existing_appid is not None:
        keys.add(("shortcut-appid", str(game.existing_appid)))
    if game.selected_exe:
        keys.add(("exe", str(game.selected_exe).casefold()))
    if not keys:
        keys.add((game.source_type, game.display_title.casefold()))
    return keys


def same_known_nonsteam_shortcut(existing: DetectedGame, incoming: DetectedGame) -> bool:
    if existing.is_native_steam_game or incoming.is_native_steam_game:
        return False
    if existing.existing_appid is not None and existing.existing_appid == incoming.existing_appid:
        return True
    if existing.source_type != "shortcut" and incoming.source_type != "shortcut":
        return False
    existing_title = normalized_artwork_cache_key(existing.display_title)
    incoming_title = normalized_artwork_cache_key(incoming.display_title)
    return bool(existing_title and incoming_title and existing_title == incoming_title)


def merge_shortcut_state(target: DetectedGame, shortcut_game: DetectedGame) -> DetectedGame:
    target.existing_appid = shortcut_game.existing_appid or target.existing_appid
    target.existing_match = shortcut_game.existing_match or target.existing_match or "shortcut"
    target.duplicate_action = shortcut_game.duplicate_action or target.duplicate_action
    target.selected = target.selected or shortcut_game.selected
    if shortcut_game.selected_exe:
        shortcut_exe = shortcut_game.selected_exe
        target.selected_exe = shortcut_exe
        if not any(candidate.path == shortcut_exe for candidate in target.candidates):
            try:
                rel = shortcut_exe.relative_to(target.root_path)
                depth = max(0, len(rel.parts) - 1)
            except ValueError:
                depth = 0
            target.candidates.insert(
                0,
                ExecutableCandidate(
                    path=shortcut_exe,
                    score=100,
                    confidence=100,
                    size_bytes=shortcut_exe.stat().st_size if shortcut_exe.exists() else 0,
                    depth=depth,
                    reasons=["Remembered from the existing non-Steam shortcut."],
                ),
            )
    if not target.launch_options and shortcut_game.launch_options:
        target.launch_options = shortcut_game.launch_options
    for genre in shortcut_game.metadata.genres:
        if genre and genre.casefold() not in {existing.casefold() for existing in target.metadata.genres}:
            target.metadata.genres.append(genre)
    for key, value in shortcut_game.metadata.extra.items():
        target.metadata.extra.setdefault(key, value)
    for slot in target.artwork.slot_names():
        if getattr(target.artwork, slot) is None:
            setattr(target.artwork, slot, getattr(shortcut_game.artwork, slot))
    if shortcut_game.source_note and shortcut_game.source_note not in target.source_note:
        target.source_note = " / ".join(part for part in [target.source_note, shortcut_game.source_note] if part)
    return target


def merge_duplicate_game(existing: DetectedGame, incoming: DetectedGame) -> DetectedGame:
    if existing.is_native_steam_game or incoming.is_native_steam_game:
        return existing
    if existing.source_type == "shortcut" and incoming.source_type == "folder":
        return merge_shortcut_state(incoming, existing)
    if existing.source_type == "folder" and incoming.source_type == "shortcut":
        return merge_shortcut_state(existing, incoming)
    if not existing.selected_exe and incoming.selected_exe:
        existing.selected_exe = incoming.selected_exe
    if not existing.candidates and incoming.candidates:
        existing.candidates = incoming.candidates
    existing.selected = existing.selected or incoming.selected
    if incoming.existing_appid and not existing.existing_appid:
        existing.existing_appid = incoming.existing_appid
        existing.existing_match = incoming.existing_match
    return existing


def merge_detected_game_lists(existing: list[DetectedGame], incoming: list[DetectedGame]) -> list[DetectedGame]:
    merged = list(existing)
    key_to_index: dict[tuple[str, str], int] = {}
    for index, game in enumerate(merged):
        for key in game_identity_keys(game):
            key_to_index[key] = index
    for game in incoming:
        keys = game_identity_keys(game)
        duplicate_indices = [key_to_index[key] for key in keys if key in key_to_index]
        if not duplicate_indices:
            duplicate_indices = [
                index
                for index, existing_game in enumerate(merged)
                if same_known_nonsteam_shortcut(existing_game, game)
            ]
        if duplicate_indices:
            merge_index = duplicate_indices[0]
            merged[merge_index] = merge_duplicate_game(merged[merge_index], game)
            for key in game_identity_keys(merged[merge_index]):
                key_to_index[key] = merge_index
            continue
        merged.append(game)
        new_index = len(merged) - 1
        for key in keys:
            key_to_index[key] = new_index
    return merged


def apply_existing_shortcut_choices(games: list[DetectedGame], records: list[Any]) -> None:
    for game in games:
        if game.is_native_steam_game:
            continue
        record = matching_record_for_game(records, game)
        if not record:
            continue
        shortcut_row = games_from_nonsteam_shortcuts([record])[0]
        merge_shortcut_state(game, shortcut_row)


def compare_games_with_shortcuts(
    games: list[DetectedGame],
    records: list[Any],
    *,
    include_nonsteam_games: bool = False,
) -> ShortcutComparisonResult:
    compared = list(games)
    shortcut_count = 0
    if include_nonsteam_games:
        nonsteam_games = games_from_nonsteam_shortcuts(records)
        shortcut_count = len(nonsteam_games)
        compared = merge_detected_game_lists(compared, nonsteam_games)
    mark_existing_shortcuts(compared, records)
    apply_existing_shortcut_choices(compared, records)
    return ShortcutComparisonResult(games=compared, shortcut_count=shortcut_count)
