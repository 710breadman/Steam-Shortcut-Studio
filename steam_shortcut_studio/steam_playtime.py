"""Read Steam's own "last played" record for installed games.

Steam keeps this per user account in
`userdata/<id>/config/localconfig.vdf`, under
`UserLocalConfigStore/Software/Valve/Steam/apps/<appid>/LastPlayed` as a Unix
timestamp. This module reads it and nothing else -- it never writes, and a
missing, unreadable, or malformed file yields no data rather than an error,
because a library view must still render when Steam has never run.

Only native Steam games have this. Launcher and folder games have no
equivalent, and this module deliberately does not invent one: a blank cell is
honest, a fabricated date is not.
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path

from .vdf import load_text_vdf


LAST_PLAYED_PATH = ("UserLocalConfigStore", "Software", "Valve", "Steam", "apps")


def _descend(node: object, keys: tuple[str, ...]) -> Mapping[str, object] | None:
    """Walk a VDF mapping case-insensitively; Steam's casing is not stable."""
    for key in keys:
        if not isinstance(node, Mapping):
            return None
        match = next((existing for existing in node if str(existing).casefold() == key.casefold()), None)
        if match is None:
            return None
        node = node[match]
    return node if isinstance(node, Mapping) else None


def _timestamp(value: object) -> int:
    try:
        stamp = int(str(value).strip())
    except (TypeError, ValueError):
        return 0
    # Steam writes 0 for "never played", and a negative value is corrupt.
    return stamp if stamp > 0 else 0


def last_played_from_localconfig(path: Path | str) -> dict[int, int]:
    """AppID -> Unix timestamp for one user's `localconfig.vdf`."""
    try:
        data = load_text_vdf(Path(path))
    except Exception:  # noqa: BLE001 - an unreadable config is simply no data
        return {}
    apps = _descend(data, LAST_PLAYED_PATH)
    if apps is None:
        return {}

    played: dict[int, int] = {}
    for appid, info in apps.items():
        if not isinstance(info, Mapping):
            continue
        key = next((k for k in info if str(k).casefold() == "lastplayed"), None)
        if key is None:
            continue
        stamp = _timestamp(info[key])
        if not stamp:
            continue
        try:
            played[int(str(appid).strip())] = stamp
        except (TypeError, ValueError):
            continue
    return played


def localconfig_paths(steam_path: Path | str) -> tuple[Path, ...]:
    userdata = Path(steam_path) / "userdata"
    try:
        entries = sorted(userdata.iterdir())
    except OSError:
        return ()
    return tuple(
        entry / "config" / "localconfig.vdf"
        for entry in entries
        if entry.is_dir() and (entry / "config" / "localconfig.vdf").is_file()
    )


def load_last_played(steam_path: Path | str | None) -> dict[int, int]:
    """AppID -> most recent Unix timestamp across every Steam user on this PC.

    Shared machines have several accounts; the most recent play across them is
    the useful answer for "when did anyone last play this".
    """
    if not steam_path:
        return {}
    merged: dict[int, int] = {}
    for config_path in localconfig_paths(steam_path):
        for appid, stamp in last_played_from_localconfig(config_path).items():
            if stamp > merged.get(appid, 0):
                merged[appid] = stamp
    return merged


def format_last_played(timestamp: int, *, now: datetime | None = None) -> str:
    """Human-readable recency, or an em dash when Steam has no record."""
    if not timestamp or timestamp <= 0:
        return "—"
    current = now or datetime.now(timezone.utc)
    try:
        played = datetime.fromtimestamp(timestamp, timezone.utc)
    except (OverflowError, OSError, ValueError):
        return "—"

    days = (current.date() - played.date()).days
    if days < 0:
        # A clock skew or a bad record; show the date rather than "in -3 days".
        return played.strftime("%d %b %Y")
    if days == 0:
        return "Today"
    if days == 1:
        return "Yesterday"
    if days < 7:
        return f"{days} days ago"
    if days < 31:
        weeks = days // 7
        return "1 week ago" if weeks == 1 else f"{weeks} weeks ago"
    if days < 365:
        return played.strftime("%b %Y")
    years = days // 365
    return "1 year ago" if years == 1 else f"{years} years ago"
