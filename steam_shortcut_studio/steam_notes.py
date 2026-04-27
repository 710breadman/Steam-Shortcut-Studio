from __future__ import annotations

import json
import shutil
import time
from datetime import datetime
from pathlib import Path

from .metadata import build_metadata_notes
from .models import DetectedGame, SteamProfile
from .steam_shortcuts import grid_appid, shortcut_from_game

BEGIN_MARKER = "--- Steam Shortcut Studio Notes BEGIN ---"
END_MARKER = "--- Steam Shortcut Studio Notes END ---"
OLD_BEGIN_MARKER = "--- Steam Shortcut Studio Metadata BEGIN ---"
OLD_END_MARKER = "--- Steam Shortcut Studio Metadata END ---"
METADATA_NOTE_ID = "steam_shortcut_studio_metadata"


def _replace_marked_section(existing: str, section: str) -> str:
    markers = [(BEGIN_MARKER, END_MARKER), (OLD_BEGIN_MARKER, OLD_END_MARKER)]
    for begin_marker, end_marker in markers:
        start = existing.find(begin_marker)
        end = existing.find(end_marker)
        if start < 0 or end <= start:
            continue
        end += len(end_marker)
        prefix = existing[:start].rstrip()
        suffix = existing[end:].lstrip()
        return "\n\n".join(part for part in [prefix, section, suffix] if part).strip() + "\n"
    if existing.strip():
        return existing.rstrip() + "\n\n" + section + "\n"
    return section + "\n"


def _backup_if_present(path: Path) -> Path | None:
    if not path.exists():
        return None
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = path.with_name(f"{path.name}.{timestamp}.bak")
    shutil.copy2(path, backup)
    return backup


def _safe_name(text: str) -> str:
    invalid = '<>:"/\\|?*'
    cleaned = "".join("_" if ch in invalid or ord(ch) < 32 else ch for ch in text).strip()
    return (cleaned or "game")[:120]


def _shortcut_note_ids(appid: int) -> list[str]:
    unsigned = grid_appid(appid)
    signed = appid
    shortcut_id = ((unsigned & 0xFFFFFFFF) << 32) | 0x02000000
    ids = [str(unsigned), str(shortcut_id)]
    if signed < 0:
        ids.append(str(signed))
    return list(dict.fromkeys(ids))


def _write_marked_note(note_path: Path, section: str) -> Path:
    note_path.parent.mkdir(parents=True, exist_ok=True)
    existing = note_path.read_text(encoding="utf-8", errors="replace") if note_path.exists() else ""
    _backup_if_present(note_path)
    note_path.write_text(_replace_marked_section(existing, section), encoding="utf-8")
    return note_path


def _steam_note_content(note_body: str) -> str:
    paragraphs = [part.strip() for part in note_body.splitlines() if part.strip()]
    return "".join(f"[p]{paragraph}[/p]" for paragraph in paragraphs)


def _one_line(text: str) -> str:
    return " ".join(text.split())


def _visible_note_title(game: DetectedGame, note_body: str, max_chars: int = 320) -> str:
    description = _one_line(game.metadata.description)
    if description:
        return description[:max_chars].rstrip()
    pieces = []
    title = game.display_title or game.title
    if game.metadata.release_year:
        title = f"{title} ({game.metadata.release_year})"
    pieces.append(title)
    if game.metadata.developer:
        pieces.append(f"Developer: {game.metadata.developer}")
    if game.metadata.publisher:
        pieces.append(f"Publisher: {game.metadata.publisher}")
    if game.metadata.genres:
        pieces.append(f"Tags: {', '.join(game.metadata.genres[:5])}")
    if game.metadata.steam_appid:
        pieces.append(f"Steam: https://store.steampowered.com/app/{game.metadata.steam_appid}/")
    summary = " | ".join(piece for piece in pieces if piece)
    if summary:
        return summary[:max_chars].rstrip()
    for line in note_body.splitlines():
        clean = _one_line(line)
        if clean and clean.casefold() not in {"steam shortcut studio notes", "steam shortcut studio metadata"}:
            return clean[:max_chars].rstrip()
    return "Steam Shortcut Studio notes"


def _load_steam_note_json(path: Path, shortcut_name: str) -> dict:
    if not path.exists():
        return {"notes": [], "shortcut_name": shortcut_name}
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        raw = path.read_text(encoding="utf-8", errors="replace")
        return {
            "notes": [
                {
                    "id": "legacy_imported_note",
                    "shortcut_name": shortcut_name,
                    "ordinal": 0,
                    "time_created": int(time.time()),
                    "time_modified": int(time.time()),
                    "title": "Previous note content",
                    "content": _steam_note_content(raw),
                }
            ],
            "shortcut_name": shortcut_name,
        }
    if not isinstance(data, dict):
        return {"notes": [], "shortcut_name": shortcut_name}
    notes = data.get("notes")
    if not isinstance(notes, list):
        data["notes"] = []
    data["shortcut_name"] = str(data.get("shortcut_name") or shortcut_name)
    return data


def _write_steam_note_json(note_path: Path, shortcut_name: str, note_body: str, note_title: str, appid: int | None = None) -> Path:
    note_path.parent.mkdir(parents=True, exist_ok=True)
    data = _load_steam_note_json(note_path, shortcut_name)
    notes = [note for note in data.get("notes", []) if isinstance(note, dict)]
    now = int(time.time())
    existing = next((note for note in notes if note.get("id") == METADATA_NOTE_ID), None)
    if existing is None:
        existing = {
            "id": METADATA_NOTE_ID,
            "shortcut_name": shortcut_name,
            "ordinal": len(notes),
            "time_created": now,
        }
        notes.append(existing)
    existing.update(
        {
            "shortcut_name": shortcut_name,
            "time_modified": now,
            "title": note_title,
            "content": _steam_note_content(note_body),
        }
    )
    data["notes"] = notes
    data["shortcut_name"] = shortcut_name
    if appid is not None:
        data["appid"] = appid
    _backup_if_present(note_path)
    note_path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return note_path


def write_game_metadata_notes(profile: SteamProfile, game: DetectedGame) -> list[Path]:
    if game.is_native_steam_game:
        return []
    if not game.selected_exe:
        return []
    notes_dir = profile.config_dir.parent / "2371090" / "remote"
    fallback_dir = profile.config_dir / "SteamShortcutStudio" / "metadata_notes"
    note_body = game.metadata.notes or build_metadata_notes(game)
    note_title = _visible_note_title(game, note_body)
    section = f"{BEGIN_MARKER}\n{note_body}\n{END_MARKER}"
    written: list[Path] = []
    shortcut_name = game.display_title
    record = shortcut_from_game(game)
    shortcut_name = record.app_name
    written.append(_write_steam_note_json(notes_dir / f"notes_shortcut_{_safe_name(shortcut_name)}", shortcut_name, note_body, note_title))
    for note_id in _shortcut_note_ids(record.appid):
        written.append(_write_steam_note_json(notes_dir / f"notes_{note_id}", shortcut_name, note_body, note_title))
    fallback_name = _safe_name(shortcut_name)
    written.append(_write_marked_note(fallback_dir / f"{fallback_name}.txt", section))
    return written


def write_metadata_notes(profile: SteamProfile, games: list[DetectedGame]) -> list[Path]:
    written: list[Path] = []
    for game in games:
        if not game.selected or not game.is_managed_non_steam:
            continue
        written.extend(write_game_metadata_notes(profile, game))
    return written
