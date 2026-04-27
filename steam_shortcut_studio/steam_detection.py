from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

from .models import SteamProfile

LOGGER = logging.getLogger(__name__)
STEAMID64_OFFSET = 76561197960265728


def _read_registry_value(root_name: str, key_path: str, value_name: str) -> str:
    try:
        import winreg
    except ImportError:
        return ""
    root = {
        "HKCU": winreg.HKEY_CURRENT_USER,
        "HKLM": winreg.HKEY_LOCAL_MACHINE,
    }[root_name]
    try:
        with winreg.OpenKey(root, key_path) as key:
            value, _ = winreg.QueryValueEx(key, value_name)
            return str(value)
    except OSError:
        return ""


def detect_steam_install() -> Path | None:
    candidates: list[Path] = []
    registry_checks = [
        ("HKCU", r"Software\Valve\Steam", "SteamPath"),
        ("HKCU", r"Software\Valve\Steam", "SteamExe"),
        ("HKLM", r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath"),
        ("HKLM", r"SOFTWARE\Valve\Steam", "InstallPath"),
    ]
    for root, key, value in registry_checks:
        raw = _read_registry_value(root, key, value)
        if not raw:
            continue
        path = Path(raw.replace("/", "\\"))
        if path.name.lower() == "steam.exe":
            path = path.parent
        candidates.append(path)

    if os.environ.get("STEAM_PATH"):
        candidates.append(Path(os.environ["STEAM_PATH"]))
    candidates.extend(
        [
            Path(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")) / "Steam",
            Path(os.environ.get("PROGRAMFILES", r"C:\Program Files")) / "Steam",
        ]
    )

    for candidate in candidates:
        if is_valid_steam_path(candidate):
            return candidate.resolve()
    return None


def is_valid_steam_path(path: Path) -> bool:
    return path.exists() and path.is_dir() and (path / "steam.exe").exists() and (path / "userdata").exists()


def _parse_login_users(steam_path: Path) -> dict[str, dict[str, str | bool]]:
    login_vdf = steam_path / "config" / "loginusers.vdf"
    users: dict[str, dict[str, str | bool]] = {}
    if not login_vdf.exists():
        return users
    try:
        text = login_vdf.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return users
    for match in re.finditer(r'"(?P<steamid>\d{16,20})"\s*\{(?P<body>.*?)\n\s*\}', text, re.S):
        steamid64 = match.group("steamid")
        body = match.group("body")
        try:
            account_id = str(int(steamid64) - STEAMID64_OFFSET)
        except ValueError:
            continue
        data: dict[str, str | bool] = {}
        for key in ("AccountName", "PersonaName", "MostRecent"):
            field = re.search(rf'"{key}"\s+"([^"]*)"', body)
            if not field:
                continue
            value = field.group(1)
            if key == "MostRecent":
                data[key] = value == "1"
            else:
                data[key] = value
        users[account_id] = data
    return users


def _localconfig_names(config_dir: Path) -> tuple[str, str]:
    localconfig = config_dir / "localconfig.vdf"
    if not localconfig.exists():
        return "", ""
    try:
        text = localconfig.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return "", ""
    account = ""
    persona = ""
    account_match = re.search(r'"AccountName"\s+"([^"]*)"', text)
    persona_match = re.search(r'"PersonaName"\s+"([^"]*)"', text)
    if account_match:
        account = account_match.group(1)
    if persona_match:
        persona = persona_match.group(1)
    return account, persona


def find_steam_profiles(steam_path: Path) -> list[SteamProfile]:
    steam_path = steam_path.expanduser().resolve()
    userdata = steam_path / "userdata"
    if not userdata.exists():
        return []
    login_users = _parse_login_users(steam_path)
    profiles: list[SteamProfile] = []
    for child in sorted(userdata.iterdir(), key=lambda item: item.name):
        if not child.is_dir() or not child.name.isdigit():
            continue
        config_dir = child / "config"
        grid_dir = config_dir / "grid"
        data = login_users.get(child.name, {})
        account_name = str(data.get("AccountName") or "")
        persona_name = str(data.get("PersonaName") or "")
        if not account_name and not persona_name:
            account_name, persona_name = _localconfig_names(config_dir)
        profiles.append(
            SteamProfile(
                user_id=child.name,
                config_dir=config_dir,
                shortcuts_path=config_dir / "shortcuts.vdf",
                grid_dir=grid_dir,
                account_name=account_name,
                persona_name=persona_name,
                most_recent=bool(data.get("MostRecent")),
            )
        )
    profiles.sort(key=lambda profile: (not profile.most_recent, profile.user_id))
    return profiles


def is_steam_running() -> bool:
    if shutil.which("tasklist"):
        try:
            output = subprocess.check_output(
                ["tasklist", "/FI", "IMAGENAME eq steam.exe"],
                text=True,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
            )
            return "steam.exe" in output.lower()
        except Exception:
            return False
    return False


def wait_for_steam_exit(timeout_seconds: int = 30) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if not is_steam_running():
            return True
        time.sleep(0.5)
    return not is_steam_running()


def shutdown_steam_for_write(steam_path: Path, timeout_seconds: int = 30) -> bool:
    """Close Steam before writing shortcuts.

    Returns True when Steam was running and this function attempted to close it.
    Raises RuntimeError if Steam is still running after graceful and forceful attempts.
    """
    if not is_steam_running():
        return False
    steam_exe = steam_path / "steam.exe"
    if steam_exe.exists():
        try:
            subprocess.Popen(
                [str(steam_exe), "-shutdown"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
            )
        except Exception as exc:
            LOGGER.warning("Could not ask Steam to shut down gracefully: %s", exc)
    if wait_for_steam_exit(timeout_seconds):
        return True

    try:
        subprocess.run(
            ["taskkill", "/IM", "steam.exe", "/F", "/T"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
            check=False,
        )
    except Exception as exc:
        LOGGER.warning("Could not force close Steam: %s", exc)
    if not wait_for_steam_exit(10):
        raise RuntimeError("Steam is still running, so shortcuts were not written.")
    return True


def reopen_steam(steam_path: Path) -> bool:
    steam_exe = steam_path / "steam.exe"
    if not steam_exe.exists():
        return False
    subprocess.Popen(
        [str(steam_exe)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
    )
    return True
