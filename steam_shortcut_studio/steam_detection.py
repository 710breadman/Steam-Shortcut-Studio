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


def _is_windows() -> bool:
    return os.name == "nt"


def _normalize_steam_candidate(path: Path) -> Path:
    path = path.expanduser()
    if path.name.casefold() in {"steam.exe", "steam.sh", "steam"}:
        return path.parent
    return path


def _linux_steam_candidates() -> list[Path]:
    home = Path.home()
    candidates: list[Path] = []
    for env_name in ("STEAM_PATH", "STEAM_HOME"):
        raw = os.environ.get(env_name)
        if raw:
            candidates.append(Path(raw))
    candidates.extend(
        [
            home / ".local" / "share" / "Steam",
            home / ".steam" / "steam",
            home / ".steam" / "root",
            home / ".var" / "app" / "com.valvesoftware.Steam" / ".local" / "share" / "Steam",
            Path("/home/deck/.local/share/Steam"),
        ]
    )
    return candidates


def _windows_steam_candidates() -> list[Path]:
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
        candidates.append(Path(raw.replace("/", "\\")))

    if os.environ.get("STEAM_PATH"):
        candidates.append(Path(os.environ["STEAM_PATH"]))
    candidates.extend(
        [
            Path(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")) / "Steam",
            Path(os.environ.get("PROGRAMFILES", r"C:\Program Files")) / "Steam",
        ]
    )
    return candidates


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
    candidates = _windows_steam_candidates() if _is_windows() else _linux_steam_candidates()

    for candidate in candidates:
        candidate = _normalize_steam_candidate(candidate)
        if is_valid_steam_path(candidate):
            return candidate.resolve()
    return None


def is_valid_steam_path(path: Path) -> bool:
    path = path.expanduser()
    if not path.exists() or not path.is_dir() or not (path / "userdata").exists():
        return False
    launchers = [
        path / "steam.exe",
        path / "steam.sh",
        path / "steam",
        path / "ubuntu12_32" / "steam",
    ]
    return any(launcher.exists() for launcher in launchers) or (path / "steamapps").exists()


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
    if _is_windows() and shutil.which("tasklist"):
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
    for process_name in ("steam", "steamwebhelper"):
        if shutil.which("pgrep"):
            try:
                result = subprocess.run(
                    ["pgrep", "-x", process_name],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
                if result.returncode == 0:
                    return True
            except Exception:
                continue
        if shutil.which("pidof"):
            try:
                result = subprocess.run(
                    ["pidof", process_name],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
                if result.returncode == 0:
                    return True
            except Exception:
                continue
    return False


def wait_for_steam_exit(timeout_seconds: int = 30) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if not is_steam_running():
            return True
        time.sleep(0.5)
    return not is_steam_running()


def _popen_kwargs(detached: bool = False) -> dict[str, object]:
    kwargs: dict[str, object] = {
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
    }
    if _is_windows():
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
    elif detached:
        kwargs["start_new_session"] = True
    return kwargs


def _steam_launcher_commands(steam_path: Path) -> list[list[str]]:
    steam_path = steam_path.expanduser()
    if _is_windows():
        steam_exe = steam_path / "steam.exe"
        return [[str(steam_exe)]] if steam_exe.exists() else []

    commands: list[list[str]] = []
    from_path = shutil.which("steam")
    if from_path:
        commands.append([from_path])
    for candidate in [steam_path / "steam.sh", steam_path / "steam", steam_path / "ubuntu12_32" / "steam"]:
        if candidate.exists():
            commands.append([str(candidate)])
    return commands


def shutdown_steam_for_write(steam_path: Path, timeout_seconds: int = 30) -> bool:
    """Close Steam before writing shortcuts.

    Returns True when Steam was running and this function attempted to close it.
    Raises RuntimeError if Steam is still running after graceful and forceful attempts.
    """
    if not is_steam_running():
        return False
    for command in _steam_launcher_commands(steam_path):
        try:
            subprocess.Popen([*command, "-shutdown"], **_popen_kwargs(detached=True))
            break
        except Exception as exc:
            LOGGER.warning("Could not ask Steam to shut down gracefully: %s", exc)
    if wait_for_steam_exit(timeout_seconds):
        return True

    if _is_windows():
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
    elif shutil.which("pkill"):
        for signal in ("-TERM", "-KILL"):
            try:
                subprocess.run(["pkill", signal, "-x", "steam"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10, check=False)
                subprocess.run(
                    ["pkill", signal, "-x", "steamwebhelper"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=10,
                    check=False,
                )
            except Exception as exc:
                LOGGER.warning("Could not force close Steam: %s", exc)
            if wait_for_steam_exit(5):
                break
    if not wait_for_steam_exit(10):
        raise RuntimeError("Steam is still running, so shortcuts were not written.")
    return True


def reopen_steam(steam_path: Path) -> bool:
    commands = _steam_launcher_commands(steam_path)
    if not commands:
        return False
    subprocess.Popen(commands[0], **_popen_kwargs(detached=True))
    return True
