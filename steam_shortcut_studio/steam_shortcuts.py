from __future__ import annotations

import binascii
import logging
import shutil
import tempfile
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .metadata import build_metadata_notes
from .models import DetectedGame, SteamProfile
from .vdf import VdfParseError, dump_binary_vdf, load_binary_vdf

LOGGER = logging.getLogger(__name__)
NON_STEAM_COLLECTION_TAG = "Non Steam"


def normalize_category_tag(tag: str) -> str:
    cleaned = " ".join(tag.strip().split())
    if cleaned.casefold() in {"non-steam", "non steam"}:
        return NON_STEAM_COLLECTION_TAG
    return cleaned


@dataclass(slots=True)
class ShortcutRecord:
    appid: int
    app_name: str
    exe: str
    start_dir: str
    icon: str = ""
    shortcut_path: str = ""
    launch_options: str = ""
    is_hidden: int = 0
    allow_desktop_config: int = 1
    allow_overlay: int = 1
    open_vr: int = 0
    devkit: int = 0
    devkit_game_id: str = ""
    devkit_override_app_id: str = ""
    last_play_time: int = 0
    flatpak_app_id: str = ""
    sort_as: str = ""
    tags: list[str] = field(default_factory=list)

    @property
    def unsigned_appid(self) -> int:
        return self.appid & 0xFFFFFFFF


def quote_path(path: str | Path) -> str:
    text = str(path)
    if text.startswith('"') and text.endswith('"'):
        return text
    return f'"{text}"'


def unquote_path(path: str) -> str:
    return path.strip().strip('"')


def normalize_for_match(path: str) -> str:
    return str(Path(unquote_path(path))).casefold()


def generate_appid(exe: str | Path, app_name: str) -> int:
    crc_input = (str(exe) + app_name).encode("utf-8", errors="replace")
    appid = (binascii.crc32(crc_input) & 0xFFFFFFFF) | 0x80000000
    return appid if appid <= 0x7FFFFFFF else appid - 0x100000000


def grid_appid(appid: int) -> int:
    return appid & 0xFFFFFFFF


def _shortcut_from_mapping(mapping: OrderedDict[str, object]) -> ShortcutRecord:
    tags: list[str] = []
    tag_map = mapping.get("tags")
    if isinstance(tag_map, OrderedDict):
        for key in sorted(tag_map, key=lambda item: int(item) if str(item).isdigit() else 999999):
            value = tag_map.get(key)
            if isinstance(value, str) and value:
                tags.append(value)
    appid_value = mapping.get("appid")
    if not isinstance(appid_value, int):
        appid_value = generate_appid(str(mapping.get("Exe", "")), str(mapping.get("AppName", "")))
    return ShortcutRecord(
        appid=appid_value,
        app_name=str(mapping.get("AppName", "")),
        exe=str(mapping.get("Exe", "")),
        start_dir=str(mapping.get("StartDir", "")),
        icon=str(mapping.get("icon", "")),
        shortcut_path=str(mapping.get("ShortcutPath", "")),
        launch_options=str(mapping.get("LaunchOptions", "")),
        is_hidden=int(mapping.get("IsHidden", 0) or 0),
        allow_desktop_config=int(mapping.get("AllowDesktopConfig", 1) or 0),
        allow_overlay=int(mapping.get("AllowOverlay", 1) or 0),
        open_vr=int(mapping.get("OpenVR", 0) or 0),
        devkit=int(mapping.get("Devkit", 0) or 0),
        devkit_game_id=str(mapping.get("DevkitGameID", "")),
        devkit_override_app_id=str(mapping.get("DevkitOverrideAppID", "")),
        last_play_time=int(mapping.get("LastPlayTime", 0) or 0),
        flatpak_app_id=str(mapping.get("FlatpakAppID", "")),
        sort_as=str(mapping.get("sortas", "")),
        tags=tags,
    )


def _mapping_from_shortcut(record: ShortcutRecord) -> OrderedDict[str, object]:
    tags: OrderedDict[str, object] = OrderedDict()
    for index, tag in enumerate(record.tags):
        tags[str(index)] = tag
    return OrderedDict(
        [
            ("appid", record.appid),
            ("AppName", record.app_name),
            ("Exe", record.exe),
            ("StartDir", record.start_dir),
            ("icon", record.icon),
            ("ShortcutPath", record.shortcut_path),
            ("LaunchOptions", record.launch_options),
            ("IsHidden", record.is_hidden),
            ("AllowDesktopConfig", record.allow_desktop_config),
            ("AllowOverlay", record.allow_overlay),
            ("OpenVR", record.open_vr),
            ("Devkit", record.devkit),
            ("DevkitGameID", record.devkit_game_id),
            ("DevkitOverrideAppID", record.devkit_override_app_id),
            ("LastPlayTime", record.last_play_time),
            ("FlatpakAppID", record.flatpak_app_id),
            ("sortas", record.sort_as),
            ("tags", tags),
        ]
    )


def load_shortcuts(path: Path) -> list[ShortcutRecord]:
    if not path.exists():
        return []
    try:
        root = load_binary_vdf(path)
    except VdfParseError:
        raise
    except Exception as exc:
        raise VdfParseError(str(exc)) from exc
    shortcuts_map = root.get("shortcuts", OrderedDict())
    if not isinstance(shortcuts_map, OrderedDict):
        return []
    records: list[ShortcutRecord] = []
    for key in sorted(shortcuts_map, key=lambda item: int(item) if str(item).isdigit() else 999999):
        value = shortcuts_map.get(key)
        if isinstance(value, OrderedDict):
            records.append(_shortcut_from_mapping(value))
    return records


def shortcut_to_game_match(records: list[ShortcutRecord], game: DetectedGame) -> tuple[int | None, str]:
    game_exe = normalize_for_match(str(game.selected_exe)) if game.selected_exe else ""
    game_title = game.display_title.casefold()
    if game_exe:
        for record in records:
            if normalize_for_match(record.exe) == game_exe:
                return record.appid, "exe"
    for record in records:
        if record.app_name.casefold() == game_title:
            return record.appid, "title"
    return None, ""


def matching_record_for_game(records: list[ShortcutRecord], game: DetectedGame) -> ShortcutRecord | None:
    game_exe = normalize_for_match(str(game.selected_exe)) if game.selected_exe else ""
    game_title = game.display_title.casefold()
    if game_exe:
        for record in records:
            if normalize_for_match(record.exe) == game_exe:
                return record
    for record in records:
        if record.app_name.casefold() == game_title:
            return record
    return None


def mark_existing_shortcuts(games: list[DetectedGame], records: list[ShortcutRecord]) -> None:
    for game in games:
        appid, match = shortcut_to_game_match(records, game)
        game.existing_appid = appid
        game.existing_match = match
        if appid is not None:
            game.duplicate_action = "update"


def shortcut_from_game(game: DetectedGame, default_tags: list[str] | None = None) -> ShortcutRecord:
    if game.is_native_steam_game:
        raise ValueError(f"Refusing to create a non-Steam shortcut from installed Steam game {game.title}")
    if not game.selected_exe:
        raise ValueError(f"No selected executable for {game.title}")
    exe = game.selected_exe.resolve()
    app_name = game.display_title
    appid = game.existing_appid if game.existing_appid is not None else generate_appid(exe, app_name)
    tags: list[str] = []
    for raw_tag in [NON_STEAM_COLLECTION_TAG, *(default_tags or [])]:
        tag = normalize_category_tag(raw_tag)
        if tag and tag.casefold() not in {existing.casefold() for existing in tags}:
            tags.append(tag)
    for genre in game.metadata.genres:
        if genre and genre.casefold() not in {existing.casefold() for existing in tags}:
            tags.append(genre)
    for tag in (
        f"Year: {game.metadata.release_year}" if game.metadata.release_year else "",
        f"Developer: {game.metadata.developer}" if game.metadata.developer else "",
        f"Publisher: {game.metadata.publisher}" if game.metadata.publisher else "",
        f"Steam AppID: {game.metadata.steam_appid}" if game.metadata.steam_appid else "",
        f"SteamGridDB: {game.metadata.sgdb_id}" if game.metadata.sgdb_id else "",
    ):
        if tag and tag.casefold() not in {existing.casefold() for existing in tags}:
            tags.append(tag)
    icon = str(game.artwork.icon.local_path) if game.artwork.icon and game.artwork.icon.local_path else str(exe)
    return ShortcutRecord(
        appid=appid,
        app_name=app_name,
        exe=quote_path(exe),
        start_dir=quote_path(exe.parent),
        icon=icon,
        launch_options=game.launch_options,
        tags=tags,
        sort_as=app_name,
    )


def merge_shortcut_update(existing: ShortcutRecord, replacement: ShortcutRecord) -> ShortcutRecord:
    """Keep Steam/user-managed fields while updating the fields this app owns."""
    merged_tags = list(existing.tags)
    for tag in replacement.tags:
        if tag and tag.casefold() not in {existing_tag.casefold() for existing_tag in merged_tags}:
            merged_tags.append(tag)
    return ShortcutRecord(
        appid=existing.appid,
        app_name=replacement.app_name or existing.app_name,
        exe=replacement.exe or existing.exe,
        start_dir=replacement.start_dir or existing.start_dir,
        icon=replacement.icon or existing.icon,
        shortcut_path=existing.shortcut_path or replacement.shortcut_path,
        launch_options=replacement.launch_options or existing.launch_options,
        is_hidden=existing.is_hidden,
        allow_desktop_config=existing.allow_desktop_config,
        allow_overlay=existing.allow_overlay,
        open_vr=existing.open_vr,
        devkit=existing.devkit,
        devkit_game_id=existing.devkit_game_id,
        devkit_override_app_id=existing.devkit_override_app_id,
        last_play_time=existing.last_play_time,
        flatpak_app_id=existing.flatpak_app_id,
        sort_as=replacement.sort_as or existing.sort_as,
        tags=merged_tags,
    )


def create_backup(path: Path) -> Path | None:
    if not path.exists():
        return None
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = path.with_name(f"{path.name}.{timestamp}.bak")
    shutil.copy2(path, backup)
    return backup


def load_shortcuts_for_write(path: Path) -> tuple[list[ShortcutRecord], Path | None, bool]:
    """Load shortcuts for writing, backing up malformed files instead of aborting.

    A malformed `shortcuts.vdf` cannot be safely merged. For the core add-to-Steam
    path, keep a timestamped backup and start from an empty shortcut list so the
    user can still add games instead of being blocked by a corrupt file.
    """
    if not path.exists():
        return [], None, False
    try:
        records = load_shortcuts(path)
    except VdfParseError as exc:
        backup = create_backup(path)
        LOGGER.error("shortcuts.vdf is malformed and will be replaced after backup: %s; backup=%s", exc, backup)
        return [], backup, True
    backup = create_backup(path)
    return records, backup, False


def write_shortcuts_file(path: Path, records: list[ShortcutRecord]) -> None:
    shortcuts_map: OrderedDict[str, object] = OrderedDict()
    for index, record in enumerate(records):
        shortcuts_map[str(index)] = _mapping_from_shortcut(record)
    root: OrderedDict[str, object] = OrderedDict([("shortcuts", shortcuts_map)])
    path.parent.mkdir(parents=True, exist_ok=True)
    data = dump_binary_vdf(root)
    with tempfile.NamedTemporaryFile(delete=False, dir=path.parent, suffix=".tmp") as handle:
        temp_path = Path(handle.name)
        handle.write(data)
    temp_path.replace(path)


def upsert_games(
    profile: SteamProfile,
    games: list[DetectedGame],
    update_existing: bool = True,
    default_tags: list[str] | None = None,
) -> tuple[int, int, Path | None]:
    selected_games = [game for game in games if game.selected and game.is_managed_non_steam]
    LOGGER.info("Preparing to write %s selected non-Steam shortcut(s).", len(selected_games))
    existing, backup, recovered_from_malformed = load_shortcuts_for_write(profile.shortcuts_path)
    if backup:
        LOGGER.info("Backed up shortcuts.vdf to %s", backup)
    if recovered_from_malformed:
        LOGGER.warning("Writing a fresh shortcuts.vdf because the existing file could not be parsed.")
    by_exe = {normalize_for_match(record.exe): index for index, record in enumerate(existing)}
    by_title = {record.app_name.casefold(): index for index, record in enumerate(existing)}
    added = 0
    updated = 0
    expected_games: list[DetectedGame] = []

    for game in selected_games:
        record = shortcut_from_game(game, default_tags=default_tags)
        match_index = None
        exe_key = normalize_for_match(record.exe)
        title_key = record.app_name.casefold()
        LOGGER.info("Shortcut payload: title=%s exe=%s start_dir=%s", record.app_name, record.exe, record.start_dir)
        if exe_key in by_exe:
            match_index = by_exe[exe_key]
        elif title_key in by_title:
            match_index = by_title[title_key]

        if match_index is not None and update_existing:
            LOGGER.info("Updating existing non-Steam shortcut for %s.", record.app_name)
            old_exe_key = normalize_for_match(existing[match_index].exe)
            old_title_key = existing[match_index].app_name.casefold()
            existing[match_index] = merge_shortcut_update(existing[match_index], record)
            by_exe.pop(old_exe_key, None)
            by_title.pop(old_title_key, None)
            by_exe[normalize_for_match(existing[match_index].exe)] = match_index
            by_title[existing[match_index].app_name.casefold()] = match_index
            updated += 1
            expected_games.append(game)
        elif match_index is None:
            LOGGER.info("Adding new non-Steam shortcut for %s.", record.app_name)
            existing.append(record)
            by_exe[exe_key] = len(existing) - 1
            by_title[title_key] = len(existing) - 1
            added += 1
            expected_games.append(game)
        else:
            LOGGER.info("Skipping duplicate non-Steam shortcut for %s because update_existing is disabled.", record.app_name)

    write_shortcuts_file(profile.shortcuts_path, existing)
    written = load_shortcuts(profile.shortcuts_path)
    missing = []
    for game in expected_games:
        record = matching_record_for_game(written, game)
        if record is None:
            missing.append(game.display_title)
            continue
        LOGGER.info("Verified shortcut write for %s as AppID %s.", game.display_title, record.unsigned_appid)
    if missing:
        raise RuntimeError("Shortcut write verification failed for: " + ", ".join(missing))
    return added, updated, backup


def preview_changes(
    profile: SteamProfile,
    games: list[DetectedGame],
    update_existing: bool,
    default_tags: list[str] | None = None,
    compat_tool: str | None = None,
) -> str:
    warning = ""
    try:
        existing = load_shortcuts(profile.shortcuts_path) if profile.shortcuts_path.exists() else []
    except VdfParseError as exc:
        existing = []
        warning = f"Warning: existing shortcuts.vdf could not be parsed and will be backed up/replaced during write: {exc}"
    lines = [
        f"Steam user: {profile.display_name}",
        f"shortcuts.vdf: {profile.shortcuts_path}",
        "",
    ]
    if warning:
        lines.extend([warning, ""])
    selected_games = [game for game in games if game.selected and game.is_managed_non_steam]
    native_games = [game for game in games if game.selected and game.is_native_steam_game]
    if not selected_games and not native_games:
        return "\n".join(lines + ["No selected games to write."])
    by_exe = {normalize_for_match(record.exe): record for record in existing}
    by_title = {record.app_name.casefold(): record for record in existing}
    for game in native_games:
        lines.extend(
            [
                f"Protected installed Steam game skipped: {game.display_title}",
                f"  Steam AppID: {game.steam_appid}",
                f"  Install folder: {game.root_path}",
                "  This app will not modify notes, artwork, categories, or shortcut data for owned Steam games.",
            ]
        )
        existing_record = by_title.get(game.display_title.casefold())
        if existing_record:
            lines.append(f"  Also has matching non-Steam shortcut: {existing_record.unsigned_appid}")
        lines.append("")
    for game in selected_games:
        record = shortcut_from_game(game, default_tags=default_tags)
        existing_record = by_exe.get(normalize_for_match(record.exe)) or by_title.get(record.app_name.casefold())
        action = "Update" if existing_record and update_existing else "Skip duplicate" if existing_record else "Add"
        lines.extend(
            [
                f"{action}: {record.app_name}",
                f"  Exe: {record.exe}",
                f"  StartDir: {record.start_dir}",
                f"  Tags: {', '.join(record.tags) if record.tags else '(none)'}",
                f"  Artwork: {game.artwork.status_text()}",
                f"  Steam notes: {'yes' if game.metadata.notes or game.metadata.description else 'no'}",
            ]
        )
        if existing_record:
            lines.append(f"  Existing AppID: {existing_record.unsigned_appid}")
        else:
            lines.append(f"  New AppID: {record.unsigned_appid}")
        if compat_tool is not None:
            compat_text = compat_tool or "Steam default (clear forced tool)"
            lines.append(f"  Steam Play compatibility: {compat_text}")
        note_body = game.metadata.notes or build_metadata_notes(game)
        if note_body:
            lines.append("  Notes preview:")
            preview = note_body if len(note_body) <= 1800 else note_body[:1800].rstrip() + "\n  ... preview truncated ..."
            lines.extend(f"    {line}" if line else "" for line in preview.splitlines())
        lines.append("")
    return "\n".join(lines).rstrip()
