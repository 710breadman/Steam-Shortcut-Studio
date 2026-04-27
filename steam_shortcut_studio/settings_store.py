from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from . import __app_name__
from .artwork_sources import DEFAULT_ARTWORK_SOURCES


def _appdata_dir() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    return Path(base) / __app_name__.replace(" ", "")


def _local_cache_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(base) / __app_name__.replace(" ", "") / "cache"


@dataclass(slots=True)
class AppSettings:
    steam_path: str = ""
    active_user_id: str = ""
    collection_root: str = ""
    steamgriddb_api_key: str = ""
    rawg_api_key: str = ""
    sgdboop_path: str = ""
    cache_dir: str = field(default_factory=lambda: str(_local_cache_dir()))
    update_existing_shortcuts: bool = True
    default_tags: list[str] = field(default_factory=lambda: ["Non Steam", "Imported"])
    last_export_dir: str = ""
    dark_mode: bool = False
    theme_name: str = "Follow System"
    visible_game_columns: list[str] = field(default_factory=lambda: ["add", "title", "exe", "confidence", "artwork", "existing"])
    game_column_order: list[str] = field(default_factory=lambda: ["add", "title", "exe", "confidence", "artwork", "existing"])
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
        if not settings.cache_dir:
            settings.cache_dir = str(_local_cache_dir())
        if settings.artwork_preview_limit < 4:
            settings.artwork_preview_limit = 4
        if settings.artwork_preview_limit > 80:
            settings.artwork_preview_limit = 80
        if not settings.theme_name:
            settings.theme_name = "Midnight" if settings.dark_mode else "Follow System"
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
