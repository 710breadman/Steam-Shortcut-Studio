from __future__ import annotations

import json
import os
import shutil
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from . import __app_name__
from .artwork_sources import DEFAULT_ARTWORK_SOURCES


def _appdata_dir() -> Path:
    if os.name == "nt":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / __app_name__.replace(" ", "")


def _local_cache_dir() -> Path:
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    else:
        base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(base) / __app_name__.replace(" ", "") / "cache"


@dataclass(slots=True)
class CacheDeletionResult:
    files_deleted: int = 0
    bytes_deleted: int = 0
    paths_deleted: list[str] = field(default_factory=list)


@dataclass(slots=True)
class AppSettings:
    steam_path: str = ""
    active_user_id: str = ""
    collection_root: str = ""
    steamgriddb_api_key: str = ""
    rawg_api_key: str = ""
    sgdboop_path: str = ""
    steam_play_compat_tool: str = ""
    cache_dir: str = field(default_factory=lambda: str(_local_cache_dir()))
    update_existing_shortcuts: bool = True
    default_tags: list[str] = field(default_factory=lambda: ["Non Steam", "Imported"])
    last_export_dir: str = ""
    dark_mode: bool = False
    theme_name: str = "Follow System"
    visible_game_columns: list[str] = field(default_factory=lambda: ["add", "title", "source", "platform", "status", "exe", "artwork", "existing"])
    game_column_order: list[str] = field(default_factory=lambda: ["add", "title", "source", "platform", "status", "exe", "artwork", "existing"])
    view_filter: str = "All"
    sort_preset: str = "Title A-Z"
    artwork_preview_limit: int = 16
    artwork_sources: dict[str, bool] = field(default_factory=lambda: dict(DEFAULT_ARTWORK_SOURCES))
    metadata_sources: dict[str, bool] = field(
        default_factory=lambda: {
            "executable": True,
            "steamgriddb": True,
            "steam": True,
            "pcgamingwiki": True,
            "wikipedia": True,
        }
    )

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "AppSettings":
        allowed = {field.name for field in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        cleaned = {key: value for key, value in data.items() if key in allowed}
        settings = cls(**cleaned)
        legacy_columns = ["add", "title", "exe", "artwork", "existing"]
        modern_columns = ["add", "title", "source", "platform", "status", "exe", "artwork", "existing"]
        if settings.visible_game_columns == legacy_columns:
            settings.visible_game_columns = list(modern_columns)
        if settings.game_column_order == legacy_columns:
            settings.game_column_order = list(modern_columns)
        if not settings.cache_dir:
            settings.cache_dir = str(_local_cache_dir())
        if settings.artwork_preview_limit < 4:
            settings.artwork_preview_limit = 4
        if settings.artwork_preview_limit > 80:
            settings.artwork_preview_limit = 80
        if not settings.theme_name:
            settings.theme_name = "Midnight" if settings.dark_mode else "Follow System"
        settings.steam_play_compat_tool = str(settings.steam_play_compat_tool or "").strip()
        if not isinstance(settings.artwork_sources, dict):
            settings.artwork_sources = dict(DEFAULT_ARTWORK_SOURCES)
        else:
            settings.artwork_sources = {key: bool(settings.artwork_sources.get(key, value)) for key, value in DEFAULT_ARTWORK_SOURCES.items()}
        if not isinstance(settings.metadata_sources, dict):
            settings.metadata_sources = cls().metadata_sources
        else:
            defaults = cls().metadata_sources
            settings.metadata_sources = {key: bool(settings.metadata_sources.get(key, value)) for key, value in defaults.items()}
        return settings


class SettingsStore:
    def __init__(self, settings_path: Path | None = None) -> None:
        self.settings_dir = _appdata_dir()
        self.settings_path = settings_path or self.settings_dir / "settings.json"

    def load(self) -> AppSettings:
        if not self.settings_path.exists():
            return AppSettings()
        try:
            data = json.loads(self.settings_path.read_text(encoding="utf-8"))
            return AppSettings.from_json(data)
        except Exception:
            return AppSettings()

    def save(self, settings: AppSettings) -> None:
        self.settings_dir.mkdir(parents=True, exist_ok=True)
        Path(settings.cache_dir).mkdir(parents=True, exist_ok=True)
        self.settings_path.write_text(
            json.dumps(asdict(settings), indent=2, sort_keys=True),
            encoding="utf-8",
        )

    def export_to(self, settings: AppSettings, destination: Path) -> None:
        destination.write_text(
            json.dumps(asdict(settings), indent=2, sort_keys=True),
            encoding="utf-8",
        )

    def import_from(self, source: Path) -> AppSettings:
        data = json.loads(source.read_text(encoding="utf-8"))
        return AppSettings.from_json(data)

    def reset_to_defaults(self) -> AppSettings:
        settings = AppSettings()
        self.save(settings)
        return settings

    def clear_cached_artwork(self, settings: AppSettings) -> CacheDeletionResult:
        return clear_cached_artwork(settings.cache_dir)


def _cache_child(cache_dir: Path, name: str) -> Path:
    cache_root = cache_dir.expanduser().resolve(strict=False)
    child = (cache_root / name).resolve(strict=False)
    if child == cache_root or not child.is_relative_to(cache_root):
        raise ValueError(f"Refusing to clear cache path outside cache folder: {child}")
    return child


def _file_size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def _count_tree(path: Path) -> tuple[int, int]:
    if path.is_symlink() or path.is_file():
        return 1, _file_size(path)
    files = 0
    bytes_deleted = 0
    if path.is_dir():
        for child in path.rglob("*"):
            if child.is_file() or child.is_symlink():
                files += 1
                bytes_deleted += _file_size(child)
    return files, bytes_deleted


def clear_cached_artwork(cache_dir: str | Path) -> CacheDeletionResult:
    cache_root = Path(cache_dir).expanduser().resolve(strict=False)
    result = CacheDeletionResult()
    for name in ("artwork", "artwork_search_cache.json", "sgdb_search_cache.json"):
        path = _cache_child(cache_root, name)
        if not path.exists() and not path.is_symlink():
            continue
        files, bytes_deleted = _count_tree(path)
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
        else:
            path.unlink()
        result.files_deleted += files
        result.bytes_deleted += bytes_deleted
        result.paths_deleted.append(str(path))
    cache_root.mkdir(parents=True, exist_ok=True)
    return result
