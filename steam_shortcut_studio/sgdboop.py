from __future__ import annotations

import os
import re
import shutil
from pathlib import Path


def _registry_command() -> str:
    try:
        import winreg
    except ImportError:
        return ""
    keys = [
        (winreg.HKEY_CURRENT_USER, r"Software\Classes\sgdb\shell\open\command"),
        (winreg.HKEY_CLASSES_ROOT, r"sgdb\shell\open\command"),
    ]
    for root, key_path in keys:
        try:
            with winreg.OpenKey(root, key_path) as key:
                value, _ = winreg.QueryValueEx(key, "")
                return str(value)
        except OSError:
            continue
    return ""


def detect_sgdboop() -> Path | None:
    from_path = shutil.which("SGDBoop.exe") or shutil.which("sgdboop.exe") or shutil.which("sgdboop") or shutil.which("SGDBoop")
    if from_path:
        return Path(from_path)
    command = _registry_command()
    if command:
        quoted = re.match(r'"([^"]+SGDBoop\.exe)"', command, re.I)
        if quoted:
            path = Path(quoted.group(1))
            if path.exists():
                return path
        raw = command.split(" ", 1)[0].strip('"')
        if raw.lower().endswith("sgdboop.exe") and Path(raw).exists():
            return Path(raw)
    for base in [os.environ.get("LOCALAPPDATA"), os.environ.get("PROGRAMFILES"), os.environ.get("PROGRAMFILES(X86)")]:
        if not base:
            continue
        root = Path(base)
        for relative in [
            Path("SGDBoop") / "SGDBoop.exe",
            Path("SteamGridDB") / "SGDBoop" / "SGDBoop.exe",
            Path("SteamGridDB") / "SGDBoop.exe",
        ]:
            candidate = root / relative
            if candidate.exists():
                return candidate
    return None


def build_boop_url(asset_url: str) -> str:
    # SGDBoop registers the sgdb:// protocol and SteamGridDB "BOOP" buttons use
    # that protocol. Direct app integration is intentionally optional because
    # built-in copying covers the normal artwork path.
    return f"sgdb://{asset_url}"
