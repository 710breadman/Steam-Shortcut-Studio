from __future__ import annotations

import tempfile
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import SteamProfile
from .steam_shortcuts import ShortcutRecord, create_backup
from .vdf import dump_text_vdf, load_text_vdf

COMPAT_ROOT = "InstallConfigStore"
COMPAT_PRIORITY = "250"


@dataclass(slots=True)
class CompatToolWriteResult:
    config_path: Path
    tool: str
    applied: int = 0
    cleared: int = 0
    backup: Path | None = None
    changed: bool = False


def normalize_compat_tool_name(tool: str | None) -> str:
    return " ".join(str(tool or "").strip().split())


def _ensure_mapping(parent: OrderedDict[str, Any], key: str) -> OrderedDict[str, Any]:
    value = parent.get(key)
    if not isinstance(value, OrderedDict):
        value = OrderedDict()
        parent[key] = value
    return value


def _valve_key(software: OrderedDict[str, Any]) -> str:
    for key in ("Valve", "valve"):
        if isinstance(software.get(key), OrderedDict):
            return key
    return "Valve"


def _compat_tool_mapping(root: OrderedDict[str, Any]) -> OrderedDict[str, Any]:
    install = _ensure_mapping(root, COMPAT_ROOT)
    software = _ensure_mapping(install, "Software")
    valve = _ensure_mapping(software, _valve_key(software))
    steam = _ensure_mapping(valve, "Steam")
    return _ensure_mapping(steam, "CompatToolMapping")


def _load_config(path: Path) -> OrderedDict[str, Any]:
    if not path.exists():
        return OrderedDict([(COMPAT_ROOT, OrderedDict())])
    return load_text_vdf(path)


def _write_config(path: Path, root: OrderedDict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = dump_text_vdf(root)
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile("w", delete=False, dir=path.parent, suffix=".tmp", encoding="utf-8", newline="\n") as handle:
            temp_path = Path(handle.name)
            handle.write(data)
        temp_path.replace(path)
    finally:
        if temp_path and temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass


def unique_compat_appids(records: list[ShortcutRecord]) -> list[str]:
    appids: list[str] = []
    seen: set[str] = set()
    for record in records:
        appid = str(record.unsigned_appid)
        if appid not in seen:
            seen.add(appid)
            appids.append(appid)
    return appids


def write_compat_tool_mappings(profile: SteamProfile, records: list[ShortcutRecord], compat_tool: str | None) -> CompatToolWriteResult:
    tool = normalize_compat_tool_name(compat_tool)
    path = profile.compatibility_config_path
    appids = unique_compat_appids(records)
    result = CompatToolWriteResult(config_path=path, tool=tool)
    if not appids:
        return result

    root = _load_config(path)
    mapping = _compat_tool_mapping(root)
    changed = False

    if tool:
        payload = OrderedDict([("name", tool), ("config", ""), ("priority", COMPAT_PRIORITY)])
        for appid in appids:
            if mapping.get(appid) != payload:
                mapping[appid] = OrderedDict(payload)
                changed = True
            result.applied += 1
    else:
        for appid in appids:
            if appid in mapping:
                del mapping[appid]
                changed = True
                result.cleared += 1

    result.changed = changed
    if not changed:
        return result
    result.backup = create_backup(path) if path.exists() else None
    _write_config(path, root)
    return result
