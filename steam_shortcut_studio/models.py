from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class SteamProfile:
    user_id: str
    config_dir: Path
    shortcuts_path: Path
    grid_dir: Path
    account_name: str = ""
    persona_name: str = ""
    most_recent: bool = False

    @property
    def display_name(self) -> str:
        pieces = []
        if self.persona_name:
            pieces.append(self.persona_name)
        if self.account_name and self.account_name not in pieces:
            pieces.append(self.account_name)
        label = " / ".join(pieces) if pieces else f"Steam user {self.user_id}"
        if self.most_recent:
            label += " (most recent)"
        return label


@dataclass(slots=True)
class ExecutableCandidate:
    path: Path
    score: float
    confidence: int
    size_bytes: int
    depth: int
    reasons: list[str] = field(default_factory=list)
    version_info: dict[str, str] = field(default_factory=dict)

    @property
    def size_mb(self) -> float:
        return self.size_bytes / (1024 * 1024)


@dataclass(slots=True)
class ArtworkAsset:
    kind: str
    asset_id: str
    url: str
    thumb_url: str = ""
    width: int = 0
    height: int = 0
    mime: str = ""
    score: int = 0
    style: str = ""
    local_path: Path | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def dimensions(self) -> str:
        if self.width and self.height:
            return f"{self.width}x{self.height}"
        return ""


@dataclass(slots=True)
class ArtworkSelection:
    grid: ArtworkAsset | None = None
    wide: ArtworkAsset | None = None
    hero: ArtworkAsset | None = None
    logo: ArtworkAsset | None = None
    icon: ArtworkAsset | None = None

    @staticmethod
    def slot_names() -> tuple[str, ...]:
        return ("grid", "wide", "hero", "logo", "icon")

    def slot_ready(self, name: str) -> bool:
        direct = getattr(self, name, None)
        if direct:
            return True
        if name == "wide":
            return bool(self.hero or self.grid)
        if name == "hero":
            return bool(self.wide or self.grid)
        if name == "icon":
            return bool(self.grid or self.wide or self.hero)
        if name == "grid":
            return bool(self.wide or self.hero)
        return False

    def selected_count(self) -> int:
        return sum(1 for name in self.slot_names() if self.slot_ready(name))

    def status_text(self) -> str:
        count = self.selected_count()
        if not count:
            return "Not fetched"
        missing = [name for name in self.slot_names() if not self.slot_ready(name)]
        if missing:
            return f"{count}/5 selected; missing {', '.join(missing)}"
        return "5/5 slots ready"


@dataclass(slots=True)
class GameMetadata:
    clean_title: str = ""
    title_locked: bool = False
    release_year: str = ""
    developer: str = ""
    publisher: str = ""
    genres: list[str] = field(default_factory=list)
    description: str = ""
    source: str = ""
    sgdb_id: int | None = None
    steam_appid: int | None = None
    notes: str = ""
    extra: dict[str, str] = field(default_factory=dict)

    def status_text(self) -> str:
        bits = []
        if self.clean_title:
            bits.append("title")
        if self.release_year:
            bits.append("year")
        if self.developer:
            bits.append("developer")
        if self.publisher:
            bits.append("publisher")
        if self.genres:
            bits.append("tags")
        if self.description:
            bits.append("description")
        if self.notes:
            bits.append("notes")
        return ", ".join(bits) if bits else "Not enriched"


@dataclass(slots=True)
class DetectedGame:
    title: str
    root_path: Path
    source_title: str = ""
    candidates: list[ExecutableCandidate] = field(default_factory=list)
    selected_exe: Path | None = None
    selected: bool = True
    launch_options: str = ""
    metadata: GameMetadata = field(default_factory=GameMetadata)
    artwork: ArtworkSelection = field(default_factory=ArtworkSelection)
    existing_appid: int | None = None
    existing_match: str = ""
    duplicate_action: str = "add"
    source_type: str = "folder"
    source_note: str = ""
    steam_appid: int | None = None

    @property
    def confidence(self) -> int:
        if not self.selected_exe:
            return 0
        for candidate in self.candidates:
            if candidate.path == self.selected_exe:
                return candidate.confidence
        return 0

    @property
    def selected_candidate(self) -> ExecutableCandidate | None:
        if not self.selected_exe:
            return None
        for candidate in self.candidates:
            if candidate.path == self.selected_exe:
                return candidate
        return None

    @property
    def display_title(self) -> str:
        return self.metadata.clean_title or self.title

    @property
    def metadata_status(self) -> str:
        return self.metadata.status_text()

    @property
    def artwork_status(self) -> str:
        return self.artwork.status_text()

    @property
    def is_native_steam_game(self) -> bool:
        return self.source_type == "steam" and self.steam_appid is not None

    @property
    def is_managed_non_steam(self) -> bool:
        return not self.is_native_steam_game and self.selected_exe is not None
