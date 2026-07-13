from __future__ import annotations

import logging
import json
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import tkinter as tk
import webbrowser
from dataclasses import replace
from logging.handlers import RotatingFileHandler
from pathlib import Path, PureWindowsPath
from tkinter import filedialog, messagebox, ttk
from typing import Any, Callable

try:
    import winreg
except ImportError:  # pragma: no cover - Windows-only system theme lookup
    winreg = None

from . import __app_name__, __version__
from .artwork import asset_download_cache_path, copy_all_artwork_to_steam, download_asset, load_existing_artwork_for_games
from .artwork_provider_adapter import validated_artwork_assets_to_search_outcome
from .artwork_queue_status import (
    artwork_cleared_message,
    artwork_editor_opened_message,
    artwork_preview_refreshed_message,
    artwork_queue_item_status,
    artwork_queue_submission_message,
    custom_artwork_selected_message,
)
from .artwork_review_workspace import (
    ArtworkReviewRow,
    artwork_rejection_clear_message,
    artwork_review_action_message,
    build_artwork_review_rows,
    build_artwork_review_summary,
    review_result_slot_count,
    source_review_clear_message,
)
from .artwork_search_service import ArtworkProviderSearchService
from .artwork_sources import ARTWORK_SOURCE_LABELS
from .bulk_artwork import ArtworkSearchMode, BulkArtworkCoordinator
from .jobs import TERMINAL_JOB_STATES
from .library_controller import LibraryController, LibraryControllerEvent
from .library_store import LibraryStore
from .metadata import build_metadata_notes, MetadataService
from .metadata_service_factory import build_metadata_service
from .metadata_targets import metadata_refresh_indices, selected_or_current_indices
from .models import ArtworkAsset, DetectedGame, ExecutableCandidate, SteamProfile
from .modern_library_view import (
    game_matches_view_filter,
    library_sort_key,
    library_sort_preset_key,
    modern_library_row_for_game,
    view_filter_status_message,
    visible_library_indices,
)
from .reporting import export_csv, export_json
from .scanner import GameScanner, clean_display_title, is_specific_title_match, similarity
from .scan_plan import (
    CombinedScanCounts,
    build_combined_scan_plan,
    build_folder_scan_plan,
    build_steam_scan_plan,
    combined_scan_done_message,
    combined_scan_folder_cross_check_message,
    combined_scan_folder_start_message,
    combined_scan_initial_message,
    combined_scan_ready_message,
    combined_scan_steam_found_message,
    combined_scan_steam_start_message,
    folder_scan_cross_check_message,
    folder_scan_done_message,
    folder_scan_initial_message,
    folder_scan_ready_message,
    folder_scan_start_message,
    steam_scan_done_message,
    steam_scan_found_message,
    steam_scan_live_found_message,
    steam_scan_ready_message,
    steam_scan_start_message,
)
from .selection_actions import selection_action_result, selection_target_label
from .selection_summary import build_selection_summary
from .selection_targets import apply_selection_target_plan, build_selection_target_plan
from .settings_store import AppSettings, SettingsStore
from .sgdboop import detect_sgdboop
from .source_scan_ui_state import SourceScanUiState
from .steam_detection import detect_steam_install, find_steam_profiles, is_steam_running, is_valid_steam_path, reopen_steam, shutdown_steam_for_write
from .steam_compat import CompatToolWriteResult, write_compat_tool_mappings
from .steam_library import games_from_nonsteam_shortcuts, scan_installed_steam_games
from .steam_notes import write_metadata_notes
from .steam_shortcuts import load_shortcuts, mark_existing_shortcuts, matching_record_for_game, preview_changes, upsert_games
from .steamgrid import SteamGridDbClient, SteamGridDbError
from .transaction_history_controller import TransactionHistoryController
from .ui_library_adapter import (
    LIBRARY_SOURCE_META,
    LIBRARY_STATUS_META,
    apply_library_selection_to_games,
    games_from_library_snapshot,
    is_persistent_library_game,
    library_item_ids_for_games,
    library_item_id_for_game,
    library_games_by_item_id,
    library_launch_target_for_game,
    selected_visible_library_item_ids,
)
from .vdf import VdfParseError

GAME_COLUMNS = ("add", "title", "source", "platform", "status", "exe", "artwork", "existing")
GAME_COLUMN_LABELS = {
    "add": "Add",
    "title": "Game Title",
    "source": "Source",
    "platform": "Platform / Size",
    "status": "Status",
    "exe": "Detected Executable",
    "artwork": "Artwork",
    "existing": "Steam",
}
GAME_COLUMN_WIDTHS = {
    "add": 56,
    "title": 180,
    "source": 92,
    "platform": 128,
    "status": 116,
    "exe": 360,
    "artwork": 110,
    "existing": 110,
}

VIEW_FILTERS = [
    "All",
    "Checked",
    "Needs artwork",
    "New non-Steam",
    "Existing non-Steam",
    "Installed Steam",
    "Stored Library",
    "Needs review",
    "Missing",
    "Skipped",
]

SORT_PRESETS = [
    "Title A-Z",
    "Library status",
    "Source",
    "Selected first",
    "Needs artwork",
    "Steam status",
    "Installed Steam first",
    "New shortcuts first",
]

ARTWORK_KINDS = ("grid", "wide", "hero", "logo", "icon")
ARTWORK_SEARCH_CACHE_VERSION = 3
STEAMGRIDDB_API_URL = "https://www.steamgriddb.com/profile/preferences"
RAWG_API_URL = "https://rawg.io/apidocs"
TK_SHIFT_MASK = 0x0001
TK_CONTROL_MASK = 0x0004
APP_ICON_PNG = "sss.png"
APP_ICON_ICO = "sss.ico"
DEFAULT_COMPAT_TOOL_LABEL = "Steam default (clear forced tool)"
COMPAT_TOOL_CHOICES = {
    DEFAULT_COMPAT_TOOL_LABEL: "",
    "Proton Experimental": "proton_experimental",
    "Proton Hotfix": "proton_hotfix",
    "Proton 9.0": "proton_9",
    "Proton 8.0": "proton_8",
}
COMPAT_TOOL_LABELS_BY_VALUE = {value: label for label, value in COMPAT_TOOL_CHOICES.items()}


def normalized_artwork_cache_key(title: str) -> str:
    return " ".join(str(title or "").casefold().strip().split())


def normalize_windows_path_text(path_text: str) -> str:
    text = str(path_text or "").strip()
    if not text:
        return ""
    if "://" in text:
        return text
    if os.name != "nt":
        return text
    return str(PureWindowsPath(text))


def launch_filetypes() -> list[tuple[str, str]]:
    if os.name == "nt":
        return [("Windows executables", "*.exe"), ("All files", "*.*")]
    return [
        ("Launch files", "*.exe *.sh *.AppImage *.appimage *.x86_64 *.x86 *.bin *.run"),
        ("All files", "*.*"),
    ]


def app_asset_path(filename: str) -> Path | None:
    candidates: list[Path] = []
    bundled_root = Path(getattr(sys, "_MEIPASS", ""))
    if bundled_root:
        candidates.append(bundled_root / "steam_shortcut_studio" / "assets" / filename)
    candidates.extend(
        [
            Path(__file__).resolve().parent / "assets" / filename,
            Path.cwd() / "steam_shortcut_studio" / "assets" / filename,
        ]
    )
    for path in candidates:
        try:
            if path.exists():
                return path
        except OSError:
            continue
    return None


def artwork_title_aliases(title: str) -> list[str]:
    cleaned = " ".join(str(title or "").replace("_", " ").split()).strip()
    if not cleaned:
        return []
    aliases: list[str] = []
    lowered = cleaned.casefold()
    normalized = re.sub(r"[^a-z0-9]+", " ", lowered).strip()

    def add(alias: str) -> None:
        alias = " ".join(alias.split()).strip()
        if alias and alias.casefold() != cleaned.casefold() and alias not in aliases:
            aliases.append(alias)

    if " - " in cleaned:
        add(cleaned.replace(" - ", ": ", 1))
    if normalized.endswith(" dc"):
        base = cleaned[: -2].strip(" -_:")
        add(f"{base} Director's Cut")
        add(f"{base} DIRECTOR'S CUT")
    if normalized.endswith(" directors cut") or normalized.endswith(" director s cut"):
        base = re.sub(r"(?i)\s+director'?s?\s+cut$", "", cleaned).strip(" -_:")
        add(f"{base} Director's Cut")
        add(f"{base} DIRECTOR'S CUT")
    subtitle_patterns = [
        (" fallen feathers", "Fallen Feathers"),
        (" legacy of thieves collection", "Legacy of Thieves Collection"),
        (" rebrushed", "Rebrushed"),
        (" mirage", "Mirage"),
    ]
    for suffix, subtitle in subtitle_patterns:
        if normalized.endswith(suffix):
            word_count = len(suffix.strip().split())
            head = " ".join(cleaned.split()[: -word_count]).strip(" -_:")
            if head:
                add(f"{head}: {subtitle}")
                if head.casefold().startswith("disney "):
                    add(f"{head[7:]}: {subtitle}")
    if cleaned.casefold().startswith("disney "):
        add(cleaned[7:])
    return aliases


def build_artwork_search_terms(game: DetectedGame, preferred: str = "") -> list[str]:
    terms: list[str] = []
    release_year = str(game.metadata.release_year or "").strip()
    title_for_exe_match = game.display_title or game.title or game.source_title
    exe_term = game.selected_exe.stem if game.selected_exe else ""
    if exe_term and title_for_exe_match and similarity(title_for_exe_match, exe_term) < 0.45:
        exe_term = ""
    raw_terms = [
        preferred,
        game.source_title,
        game.title,
        game.display_title,
        exe_term,
    ]
    if not game.source_title and game.root_path:
        raw_terms.insert(0, game.root_path.name)
    expanded: list[str] = []
    for term in raw_terms:
        cleaned = " ".join(str(term or "").replace("_", " ").split())
        if not cleaned:
            continue
        expanded.append(cleaned)
        logical = clean_display_title(cleaned)
        if logical:
            expanded.append(logical)
            if release_year:
                expanded.append(f"{logical} {release_year}")
            expanded.extend(artwork_title_aliases(logical))
        if " - " in cleaned:
            expanded.append(cleaned.replace(" - ", ": ", 1))
            expanded.append(clean_display_title(cleaned.split(" - ")[0]))
        expanded.extend(artwork_title_aliases(cleaned))
    seen: set[str] = set()
    for term in expanded:
        cleaned = " ".join(term.split())
        folded = cleaned.casefold()
        if cleaned and folded not in seen:
            terms.append(cleaned)
            seen.add(folded)
    return terms


def release_year_from_text(value: object) -> str:
    text = str(value or "")
    for index in range(max(0, len(text) - 3)):
        chunk = text[index : index + 4]
        if chunk.isdigit() and 1970 <= int(chunk) <= 2100:
            return chunk
    return ""


def artwork_candidate_score(game: DetectedGame, search_term: str, item: dict[str, Any]) -> float:
    name = str(item.get("name") or "")
    score = similarity(search_term, name)
    clean_term = clean_display_title(search_term)
    if clean_term and clean_term != search_term:
        score = max(score, similarity(clean_term, name))
    release_year = release_year_from_text(game.metadata.release_year)
    if release_year:
        candidate_year = (
            release_year_from_text(item.get("release_date"))
            or release_year_from_text(item.get("released"))
            or release_year_from_text(item.get("year"))
        )
        if candidate_year == release_year:
            score += 0.18
        elif candidate_year:
            score -= 0.08
    return score


def artwork_asset_is_ready(asset: ArtworkAsset | None) -> bool:
    return bool(asset and asset.local_path and asset.local_path.exists())

THEMES = [
    "Follow System",
    "Steam Deck Blue",
    "Neon Grid",
    "Vaporwave Dream",
    "Cyberpunk Hazard",
    "Monochrome Steel",
    "High Contrast",
    "Amber Arcade",
    "Glacier Blue",
    "Purple Glow",
    "Green Terminal",
    "Candy Pop",
    "Classic Light",
]

THEME_ALIASES = {
    "Light": "Classic Light",
    "Midnight": "Steam Deck Blue",
    "Slate Blue": "Glacier Blue",
    "Classic": "Classic Light",
    "Nebula Purple": "Purple Glow",
    "Bubblegum Circuit": "Candy Pop",
    "Solar Flare": "Amber Arcade",
    "Rainbow Arcade": "Neon Grid",
    "Primary Pop": "Glacier Blue",
    "Emerald City": "Green Terminal",
    "Rose Gold": "Candy Pop",
}

THEME_PALETTES: dict[str, dict[str, str]] = {
    "Steam Deck Blue": {
        "bg": "#101722",
        "panel": "#182335",
        "entry": "#111c2c",
        "text": "#dce8f8",
        "strong": "#f6fbff",
        "muted": "#8ca2bd",
        "border": "#2f4360",
        "header_bg": "#1e2d44",
        "selected": "#1a9fff",
        "selected_text": "#06111f",
        "button_bg": "#21324a",
        "canvas": "#0e1622",
        "accent": "#66c0f4",
        "accent_text": "#06111f",
        "success": "#38d996",
        "warning": "#ffd166",
        "error": "#ff6b6b",
    },
    "Neon Grid": {
        "bg": "#090a14",
        "panel": "#141527",
        "entry": "#0f1020",
        "text": "#ecf4ff",
        "strong": "#ffffff",
        "muted": "#9aa0c4",
        "border": "#31345f",
        "header_bg": "#1d1f3d",
        "selected": "#00e5ff",
        "selected_text": "#05060d",
        "button_bg": "#1a1c34",
        "canvas": "#090a14",
        "accent": "#ff2bd6",
        "accent_text": "#ffffff",
        "success": "#00ff99",
        "warning": "#ffe45e",
        "error": "#ff3864",
    },
    "Vaporwave Dream": {
        "bg": "#24133f",
        "panel": "#351f58",
        "entry": "#2a1748",
        "text": "#f8eaff",
        "strong": "#ffffff",
        "muted": "#d6a8e8",
        "border": "#71449a",
        "header_bg": "#45256c",
        "selected": "#ff8bd8",
        "selected_text": "#24102e",
        "button_bg": "#462a68",
        "canvas": "#211036",
        "accent": "#56f0ff",
        "accent_text": "#111827",
        "success": "#8dffcf",
        "warning": "#ffd36e",
        "error": "#ff6fae",
    },
    "Cyberpunk Hazard": {
        "bg": "#11130b",
        "panel": "#1d2010",
        "entry": "#15180d",
        "text": "#f4ffd2",
        "strong": "#fffff2",
        "muted": "#aeb77c",
        "border": "#5c641d",
        "header_bg": "#292e10",
        "selected": "#f5ff00",
        "selected_text": "#151803",
        "button_bg": "#2b3015",
        "canvas": "#101306",
        "accent": "#00ffd1",
        "accent_text": "#06110f",
        "success": "#7dff68",
        "warning": "#f5ff00",
        "error": "#ff3158",
    },
    "Monochrome Steel": {
        "bg": "#151719",
        "panel": "#222529",
        "entry": "#1b1e22",
        "text": "#e4e7eb",
        "strong": "#ffffff",
        "muted": "#a5abb3",
        "border": "#3c424a",
        "header_bg": "#2b3036",
        "selected": "#d6dde6",
        "selected_text": "#111418",
        "button_bg": "#2a2f35",
        "canvas": "#171a1e",
        "accent": "#f5f7fa",
        "accent_text": "#111418",
        "success": "#b6f0cc",
        "warning": "#ffe2a8",
        "error": "#ffb4b4",
    },
    "High Contrast": {
        "bg": "#000000",
        "panel": "#101010",
        "entry": "#000000",
        "text": "#ffffff",
        "strong": "#ffffff",
        "muted": "#d0d0d0",
        "border": "#ffffff",
        "header_bg": "#202020",
        "selected": "#ffff00",
        "selected_text": "#000000",
        "button_bg": "#202020",
        "canvas": "#000000",
        "accent": "#00ffff",
        "accent_text": "#000000",
        "success": "#00ff66",
        "warning": "#ffff00",
        "error": "#ff3366",
    },
    "Amber Arcade": {
        "bg": "#26160a",
        "panel": "#38210f",
        "entry": "#2d190c",
        "text": "#ffe9c7",
        "strong": "#fff8ea",
        "muted": "#d8aa72",
        "border": "#7b4a1d",
        "header_bg": "#4a2b13",
        "selected": "#ff9f1c",
        "selected_text": "#241104",
        "button_bg": "#4a2a12",
        "canvas": "#221207",
        "accent": "#ffbf69",
        "accent_text": "#241104",
        "success": "#a8e063",
        "warning": "#ffd166",
        "error": "#ff6b35",
    },
    "Glacier Blue": {
        "bg": "#eef7ff",
        "panel": "#ffffff",
        "entry": "#ffffff",
        "text": "#17324d",
        "strong": "#071b2d",
        "muted": "#5c748c",
        "border": "#b7d3ea",
        "header_bg": "#dff0ff",
        "selected": "#b9e6ff",
        "selected_text": "#082033",
        "button_bg": "#f5fbff",
        "canvas": "#ffffff",
        "accent": "#0078d4",
        "accent_text": "#ffffff",
        "success": "#16855d",
        "warning": "#9a6700",
        "error": "#c62828",
    },
    "Purple Glow": {
        "bg": "#1b102a",
        "panel": "#28183d",
        "entry": "#211332",
        "text": "#eee2ff",
        "strong": "#ffffff",
        "muted": "#bda8d9",
        "border": "#563a78",
        "header_bg": "#34204d",
        "selected": "#9b5cff",
        "selected_text": "#ffffff",
        "button_bg": "#34214c",
        "canvas": "#1a0f29",
        "accent": "#d877ff",
        "accent_text": "#1b102a",
        "success": "#7fffd4",
        "warning": "#ffd36e",
        "error": "#ff6b9a",
    },
    "Green Terminal": {
        "bg": "#06110b",
        "panel": "#0d1c13",
        "entry": "#07140c",
        "text": "#c7ffd8",
        "strong": "#ecfff2",
        "muted": "#7cc991",
        "border": "#245532",
        "header_bg": "#12301d",
        "selected": "#35ff70",
        "selected_text": "#031006",
        "button_bg": "#153621",
        "canvas": "#06110b",
        "accent": "#00d26a",
        "accent_text": "#031006",
        "success": "#35ff70",
        "warning": "#d7ff4f",
        "error": "#ff5c7a",
    },
    "Candy Pop": {
        "bg": "#fff3f8",
        "panel": "#ffffff",
        "entry": "#ffffff",
        "text": "#332033",
        "strong": "#1f1120",
        "muted": "#805f79",
        "border": "#e8bed5",
        "header_bg": "#ffe1f0",
        "selected": "#ffc2e4",
        "selected_text": "#261027",
        "button_bg": "#fff8fc",
        "canvas": "#fffafd",
        "accent": "#eb3fa9",
        "accent_text": "#ffffff",
        "success": "#1b9a77",
        "warning": "#a76300",
        "error": "#c2185b",
    },
    "Classic Light": {
        "bg": "#f5f6f8",
        "panel": "#ffffff",
        "entry": "#ffffff",
        "text": "#1d2733",
        "strong": "#17202a",
        "muted": "#667085",
        "border": "#cfd5dd",
        "header_bg": "#e9edf3",
        "selected": "#dbeafe",
        "selected_text": "#111827",
        "button_bg": "#ffffff",
        "canvas": "#ffffff",
        "accent": "#2563eb",
        "accent_text": "#ffffff",
        "success": "#16855d",
        "warning": "#a16207",
        "error": "#b42318",
    },
}

METADATA_SOURCE_LABELS = {
    "executable": "Executable metadata",
    "steamgriddb": "SteamGridDB",
    "steam": "Steam Store",
    "pcgamingwiki": "PCGamingWiki",
    "wikipedia": "Wikipedia",
}


class JobCancelled(Exception):
    pass

try:
    from PIL import Image, ImageTk
except Exception:  # pragma: no cover - optional GUI nicety
    Image = None
    ImageTk = None


class QueueLogHandler(logging.Handler):
    def __init__(self, messages: queue.Queue[str]) -> None:
        super().__init__()
        self.messages = messages
        self.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%H:%M:%S"))

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.messages.put(self.format(record))
        except Exception:
            pass


class ToolTip:
    def __init__(self, widget: tk.Widget, text: str, delay_ms: int = 500) -> None:
        self.widget = widget
        self.text = text
        self.delay_ms = delay_ms
        self.after_id: str | None = None
        self.window: tk.Toplevel | None = None
        widget.bind("<Enter>", self.schedule, add="+")
        widget.bind("<Leave>", self.hide, add="+")
        widget.bind("<ButtonPress>", self.hide, add="+")

    def schedule(self, _event: tk.Event[Any] | None = None) -> None:
        self.cancel()
        self.after_id = self.widget.after(self.delay_ms, self.show)

    def cancel(self) -> None:
        if self.after_id:
            self.widget.after_cancel(self.after_id)
            self.after_id = None

    def show(self) -> None:
        if self.window or not self.text:
            return
        x = self.widget.winfo_rootx() + 18
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 8
        self.window = tk.Toplevel(self.widget)
        self.window.wm_overrideredirect(True)
        self.window.wm_geometry(f"+{x}+{y}")
        label = tk.Label(
            self.window,
            text=self.text,
            justify=tk.LEFT,
            wraplength=360,
            background="#111827",
            foreground="#ffffff",
            relief=tk.SOLID,
            borderwidth=1,
            padx=8,
            pady=6,
            font=("Segoe UI", 9),
        )
        label.pack()

    def hide(self, _event: tk.Event[Any] | None = None) -> None:
        self.cancel()
        if self.window:
            self.window.destroy()
            self.window = None


def game_identity_keys(game: DetectedGame) -> set[tuple[str, str]]:
    keys: set[tuple[str, str]] = set()
    if game.steam_appid:
        keys.add(("steam", str(game.steam_appid)))
    if not game.is_native_steam_game and game.existing_appid is not None:
        keys.add(("shortcut-appid", str(game.existing_appid)))
    if game.selected_exe:
        keys.add(("exe", str(game.selected_exe).casefold()))
    if not keys:
        keys.add((game.source_type, game.display_title.casefold()))
    return keys


def same_known_nonsteam_shortcut(existing: DetectedGame, incoming: DetectedGame) -> bool:
    if existing.is_native_steam_game or incoming.is_native_steam_game:
        return False
    if existing.existing_appid is not None and existing.existing_appid == incoming.existing_appid:
        return True
    if existing.source_type != "shortcut" and incoming.source_type != "shortcut":
        return False
    existing_title = normalized_artwork_cache_key(existing.display_title)
    incoming_title = normalized_artwork_cache_key(incoming.display_title)
    return bool(existing_title and incoming_title and existing_title == incoming_title)


def merge_shortcut_state(target: DetectedGame, shortcut_game: DetectedGame) -> DetectedGame:
    target.existing_appid = shortcut_game.existing_appid or target.existing_appid
    target.existing_match = shortcut_game.existing_match or target.existing_match or "shortcut"
    target.duplicate_action = shortcut_game.duplicate_action or target.duplicate_action
    target.selected = target.selected or shortcut_game.selected
    if shortcut_game.selected_exe:
        shortcut_exe = shortcut_game.selected_exe
        target.selected_exe = shortcut_exe
        if not any(candidate.path == shortcut_exe for candidate in target.candidates):
            try:
                rel = shortcut_exe.relative_to(target.root_path)
                depth = max(0, len(rel.parts) - 1)
            except ValueError:
                depth = 0
            target.candidates.insert(
                0,
                ExecutableCandidate(
                    path=shortcut_exe,
                    score=100,
                    confidence=100,
                    size_bytes=shortcut_exe.stat().st_size if shortcut_exe.exists() else 0,
                    depth=depth,
                    reasons=["Remembered from the existing non-Steam shortcut."],
                ),
            )
    if not target.launch_options and shortcut_game.launch_options:
        target.launch_options = shortcut_game.launch_options
    for genre in shortcut_game.metadata.genres:
        if genre and genre.casefold() not in {existing.casefold() for existing in target.metadata.genres}:
            target.metadata.genres.append(genre)
    for key, value in shortcut_game.metadata.extra.items():
        target.metadata.extra.setdefault(key, value)
    for slot in target.artwork.slot_names():
        if getattr(target.artwork, slot) is None:
            setattr(target.artwork, slot, getattr(shortcut_game.artwork, slot))
    if shortcut_game.source_note and shortcut_game.source_note not in target.source_note:
        target.source_note = " / ".join(part for part in [target.source_note, shortcut_game.source_note] if part)
    return target


def merge_duplicate_game(existing: DetectedGame, incoming: DetectedGame) -> DetectedGame:
    if existing.is_native_steam_game or incoming.is_native_steam_game:
        return existing
    if existing.source_type == "shortcut" and incoming.source_type == "folder":
        return merge_shortcut_state(incoming, existing)
    if existing.source_type == "folder" and incoming.source_type == "shortcut":
        return merge_shortcut_state(existing, incoming)
    if not existing.selected_exe and incoming.selected_exe:
        existing.selected_exe = incoming.selected_exe
    if not existing.candidates and incoming.candidates:
        existing.candidates = incoming.candidates
    existing.selected = existing.selected or incoming.selected
    if incoming.existing_appid and not existing.existing_appid:
        existing.existing_appid = incoming.existing_appid
        existing.existing_match = incoming.existing_match
    return existing


def merge_detected_game_lists(existing: list[DetectedGame], incoming: list[DetectedGame]) -> list[DetectedGame]:
    merged = list(existing)
    key_to_index: dict[tuple[str, str], int] = {}
    for index, game in enumerate(merged):
        for key in game_identity_keys(game):
            key_to_index[key] = index
    for game in incoming:
        keys = game_identity_keys(game)
        duplicate_indices = [key_to_index[key] for key in keys if key in key_to_index]
        if not duplicate_indices:
            duplicate_indices = [
                index
                for index, existing_game in enumerate(merged)
                if same_known_nonsteam_shortcut(existing_game, game)
            ]
        if duplicate_indices:
            merge_index = duplicate_indices[0]
            merged[merge_index] = merge_duplicate_game(merged[merge_index], game)
            for key in game_identity_keys(merged[merge_index]):
                key_to_index[key] = merge_index
            continue
        merged.append(game)
        new_index = len(merged) - 1
        for key in keys:
            key_to_index[key] = new_index
    return merged


class MainWindow(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(f"{__app_name__} {__version__}")
        self.geometry("1320x850")
        self.minsize(1120, 700)
        self.app_icon_image: tk.PhotoImage | None = None

        self.settings_store = SettingsStore()
        self.settings = self.settings_store.load()
        self.log_path = self.settings_store.settings_dir / "logs" / "steam_shortcut_studio.log"
        self.library_store = LibraryStore()
        self.library_controller = LibraryController(self.library_store)
        self.transaction_history_controller = TransactionHistoryController()
        self.games: list[DetectedGame] = []
        self.profiles: list[SteamProfile] = []
        self.current_game_index: int | None = None
        self.current_artwork_results: list[ArtworkAsset] = []
        self.artwork_search_cache: dict[int, dict[str, list[ArtworkAsset]]] = {}
        self.preview_images: list[Any] = []
        self.artwork_result_images: list[Any] = []
        self.log_queue: queue.Queue[str] = queue.Queue()
        self.ui_queue: queue.Queue[Callable[[], None]] = queue.Queue()
        self.busy = False
        self.cancel_event = threading.Event()
        self.cancel_events: set[threading.Event] = set()
        self.active_job_count = 0
        self.exclusive_job_running = False
        self.suppress_game_select_events = False
        self.sort_column = "title"
        self.sort_reverse = False
        self.displayed_game_indices: list[int] = []
        self.artwork_refresh_after_id: str | None = None
        self.image_cache: dict[tuple[str, tuple[int, int], int], Any] = {}
        self.artwork_title_cache: dict[str, dict[str, list[ArtworkAsset]]] = {}
        self.artwork_cache_path = Path(self.settings.cache_dir) / "artwork_search_cache.json"
        self.artwork_reflow_after_id: str | None = None
        self.artwork_refresh_after_ids: dict[int, str] = {}
        self.artwork_render_after_id: str | None = None
        self.artwork_render_token = 0
        self.artwork_job_keys: set[str] = set()
        self.library_scan_poll_after_id: str | None = None
        self.source_scan_state = SourceScanUiState(self.library_controller)
        self.library_selection_anchor_id = ""
        self.persistent_artwork_job_ids: set[str] = set()
        self.persistent_artwork_review_results: dict[str, dict[str, object]] = {}
        self.artwork_job_status: dict[int, str] = {}
        self.manual_artwork_slots: set[tuple[int, str]] = set()
        self.detail_dirty = False
        self.notes_dirty = False
        self.suppress_detail_dirty = False
        self.logger = logging.getLogger("SteamShortcutStudio")
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False
        self.logger.handlers.clear()
        self.logger.addHandler(QueueLogHandler(self.log_queue))
        self._add_file_log_handler()
        self.load_persistent_artwork_search_cache()
        self.apply_app_icon()

        self._build_vars()
        self._build_style()
        self._build_ui()
        self.after(120, self._poll_logs)
        self.after(180, self._poll_library_controller_events)
        self.after(150, self._load_initial_state)

    def apply_app_icon(self) -> None:
        png_path = app_asset_path(APP_ICON_PNG)
        ico_path = app_asset_path(APP_ICON_ICO)
        if png_path:
            try:
                self.app_icon_image = tk.PhotoImage(file=str(png_path))
                self.iconphoto(True, self.app_icon_image)
            except tk.TclError as exc:
                self.logger.warning("Could not load app PNG icon from %s: %s", png_path, exc)
        if ico_path:
            try:
                self.iconbitmap(default=str(ico_path))
            except tk.TclError as exc:
                self.logger.warning("Could not load app ICO icon from %s: %s", ico_path, exc)

    def artwork_cache_key(self, game: DetectedGame | str) -> str:
        if isinstance(game, DetectedGame):
            return self.artwork_cache_keys(game)[0]
        return normalized_artwork_cache_key(game)

    def artwork_cache_keys(self, game: DetectedGame, preferred: str = "") -> list[str]:
        raw_keys = [
            preferred,
            game.source_title,
            game.title,
            game.display_title,
            game.metadata.clean_title,
            f"sgdb:{game.metadata.sgdb_id}" if game.metadata.sgdb_id else "",
        ]
        keys: list[str] = []
        for item in raw_keys:
            key = normalized_artwork_cache_key(str(item or ""))
            if key and key not in keys:
                keys.append(key)
        return keys or [normalized_artwork_cache_key(game.display_title)]

    def cached_artwork_for_game(self, game: DetectedGame, preferred: str = "") -> dict[str, list[ArtworkAsset]] | None:
        for key in self.artwork_cache_keys(game, preferred):
            cached = self.artwork_title_cache.get(key)
            if cached is not None:
                return cached
        return None

    def artwork_download_cache_root(self) -> Path:
        return (Path(self.settings.cache_dir).expanduser() / "artwork").resolve(strict=False)

    def cached_artwork_file_path(self, path: Path | None) -> Path | None:
        if path is None:
            return None
        cache_root = self.artwork_download_cache_root()
        resolved = Path(path).expanduser().resolve(strict=False)
        try:
            if not resolved.is_relative_to(cache_root):
                return None
        except ValueError:
            return None
        if not resolved.exists() and not resolved.is_symlink():
            return None
        return resolved

    def cached_artwork_paths_for_game(self, game: DetectedGame, preferred: str = "", sgdb_game_id: int | None = None) -> set[Path]:
        paths: set[Path] = set()
        cache_dir = Path(self.settings.cache_dir)

        def add_asset(asset: ArtworkAsset | None) -> None:
            if not asset:
                return
            path = self.cached_artwork_file_path(asset.local_path)
            if path is not None:
                paths.add(path)
            generated_path = self.cached_artwork_file_path(asset_download_cache_path(asset, cache_dir))
            if generated_path is not None:
                paths.add(generated_path)

        for kind in game.artwork.slot_names():
            add_asset(getattr(game.artwork, kind))

        cached_sets: list[dict[str, list[ArtworkAsset]] | None] = []
        game_index = self.game_index_for_object(game)
        if game_index is not None:
            cached_sets.append(self.artwork_search_cache.get(game_index))
        cache_keys = set(self.artwork_cache_keys(game, preferred))
        if preferred:
            cache_keys.add(self.artwork_cache_key(preferred))
        if sgdb_game_id:
            cache_keys.add(f"sgdb:{sgdb_game_id}")
        for cache_key in cache_keys:
            cached_sets.append(self.artwork_title_cache.get(cache_key))

        for cached in cached_sets:
            if not cached:
                continue
            for assets in cached.values():
                for asset in assets:
                    add_asset(asset)
        return paths

    def delete_cached_artwork_files_for_game(self, game: DetectedGame, preferred: str = "", sgdb_game_id: int | None = None) -> int:
        deleted = 0
        for path in self.cached_artwork_paths_for_game(game, preferred, sgdb_game_id):
            try:
                path.unlink()
                deleted += 1
                try:
                    path.parent.rmdir()
                except OSError:
                    pass
            except OSError as exc:
                self.logger.info("Could not delete cached artwork file %s: %s", path, exc)
        return deleted

    def clear_individual_artwork_cache(self, game: DetectedGame, preferred: str = "", sgdb_game_id: int | None = None) -> None:
        deleted_files = self.delete_cached_artwork_files_for_game(game, preferred, sgdb_game_id)
        game_index = self.game_index_for_object(game)
        if game_index is not None:
            self.artwork_search_cache.pop(game_index, None)
        cache_keys = set(self.artwork_cache_keys(game, preferred))
        if preferred:
            cache_keys.add(self.artwork_cache_key(preferred))
        if sgdb_game_id:
            cache_keys.add(f"sgdb:{sgdb_game_id}")
        for cache_key in cache_keys:
            self.artwork_title_cache.pop(cache_key, None)
        for kind in game.artwork.slot_names():
            setattr(game.artwork, kind, None)
            self.manual_artwork_slots.discard((id(game), kind))
        if game_index is not None:
            self.artwork_job_status[id(game)] = "Searching artwork"
            self.refresh_game_row(game_index)
        if self.current_game_index == game_index:
            self.current_artwork_results.clear()
            self.image_cache.clear()
            self.update_artwork_previews()
            self.populate_artwork_results([])
        self.save_persistent_artwork_search_cache()
        self.logger.info(
            "Cleared cached artwork state and deleted %s cached artwork file(s) for %s before artwork search.",
            deleted_files,
            game.display_title,
        )

    def asset_to_cache(self, asset: ArtworkAsset) -> dict[str, Any]:
        return {
            "kind": asset.kind,
            "asset_id": asset.asset_id,
            "url": asset.url,
            "thumb_url": asset.thumb_url,
            "width": asset.width,
            "height": asset.height,
            "mime": asset.mime,
            "score": asset.score,
            "style": asset.style,
            "local_path": str(asset.local_path) if asset.local_path else "",
            "raw": asset.raw,
        }

    def asset_from_cache(self, data: dict[str, Any]) -> ArtworkAsset | None:
        try:
            local_path = Path(str(data.get("local_path") or "")) if data.get("local_path") else None
            return ArtworkAsset(
                kind=str(data.get("kind") or ""),
                asset_id=str(data.get("asset_id") or data.get("url") or "cached"),
                url=str(data.get("url") or ""),
                thumb_url=str(data.get("thumb_url") or ""),
                width=int(data.get("width") or 0),
                height=int(data.get("height") or 0),
                mime=str(data.get("mime") or ""),
                score=int(data.get("score") or 0),
                style=str(data.get("style") or ""),
                local_path=local_path,
                raw=dict(data.get("raw") or {}),
            )
        except Exception:
            return None

    def load_persistent_artwork_search_cache(self) -> None:
        if not self.artwork_cache_path.exists():
            return
        try:
            data = json.loads(self.artwork_cache_path.read_text(encoding="utf-8"))
        except Exception as exc:
            self.logger.info("Artwork search cache could not be loaded: %s", exc)
            return
        cache_entries = data.get("entries") if isinstance(data, dict) and data.get("__version") == ARTWORK_SEARCH_CACHE_VERSION else None
        if cache_entries is None:
            self.logger.info("Ignoring old artwork search cache after artwork matching logic changed.")
            return
        cache: dict[str, dict[str, list[ArtworkAsset]]] = {}
        if isinstance(cache_entries, dict):
            for key, kinds in cache_entries.items():
                if not isinstance(kinds, dict):
                    continue
                cache[str(key)] = {}
                for kind, assets in kinds.items():
                    if not isinstance(assets, list):
                        continue
                    cache[str(key)][str(kind)] = [asset for item in assets if isinstance(item, dict) and (asset := self.asset_from_cache(item))]
        self.artwork_title_cache = cache
        self.logger.info("Loaded artwork search cache for %s title(s).", len(cache))

    def save_persistent_artwork_search_cache(self) -> None:
        try:
            self.artwork_cache_path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "__version": ARTWORK_SEARCH_CACHE_VERSION,
                "entries": {
                    key: {
                        kind: [self.asset_to_cache(asset) for asset in assets[:80]]
                        for kind, assets in kinds.items()
                    }
                    for key, kinds in self.artwork_title_cache.items()
                },
            }
            self.artwork_cache_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception as exc:
            self.logger.info("Artwork search cache could not be saved: %s", exc)

    def _add_file_log_handler(self) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(self.log_path, maxBytes=1_000_000, backupCount=4, encoding="utf-8")
        file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
        self.logger.addHandler(file_handler)
        self.logger.info("Logging to %s", self.log_path)

    def compat_tool_display_name(self, value: str | None) -> str:
        return COMPAT_TOOL_LABELS_BY_VALUE.get(str(value or "").strip(), str(value or "").strip() or DEFAULT_COMPAT_TOOL_LABEL)

    def selected_compat_tool_name(self) -> str:
        text = self.compat_tool_var.get().strip()
        if text in COMPAT_TOOL_CHOICES:
            return COMPAT_TOOL_CHOICES[text]
        if text.casefold().startswith("steam default"):
            return ""
        return text

    def _build_vars(self) -> None:
        self.steam_path_var = tk.StringVar(value=normalize_windows_path_text(self.settings.steam_path))
        self.collection_path_var = tk.StringVar(value=normalize_windows_path_text(self.settings.collection_root))
        self.api_key_var = tk.StringVar(value=self.settings.steamgriddb_api_key)
        self.rawg_api_key_var = tk.StringVar(value=self.settings.rawg_api_key)
        self.sgdboop_path_var = tk.StringVar(value=self.settings.sgdboop_path)
        self.profile_var = tk.StringVar()
        self.profile_status_var = tk.StringVar(value="Profile: none")
        self.status_var = tk.StringVar(value="Ready.")
        self.bulk_status_var = tk.StringVar(value="0 selected")
        self.settings_location_var = tk.StringVar(value=str(self.settings_store.settings_path))
        self.cache_location_var = tk.StringVar(value=str(Path(self.settings.cache_dir)))
        self.update_existing_var = tk.BooleanVar(value=self.settings.update_existing_shortcuts)
        self.default_tags_var = tk.StringVar(value=", ".join(self.settings.default_tags))
        self.compat_tool_var = tk.StringVar(value=self.compat_tool_display_name(self.settings.steam_play_compat_tool))
        self.artwork_kind_var = tk.StringVar(value="all")
        self.artwork_search_var = tk.StringVar()
        initial_theme = self.normalized_theme_name(self.settings.theme_name)
        self.theme_var = tk.StringVar(value=initial_theme)
        self.dark_mode_var = tk.BooleanVar(value=self.theme_is_dark(initial_theme))
        self.column_choice_var = tk.StringVar(value="Game Title")
        self.column_visible_var = tk.BooleanVar(value=True)
        self.view_filter_var = tk.StringVar(value=self.settings.view_filter if self.settings.view_filter in VIEW_FILTERS else "All")
        self.sort_preset_var = tk.StringVar(value=self.settings.sort_preset if self.settings.sort_preset in SORT_PRESETS else "Title A-Z")
        self.preview_limit_var = tk.IntVar(value=self.settings.artwork_preview_limit)
        self.artwork_source_vars = {
            key: tk.BooleanVar(value=bool(self.settings.artwork_sources.get(key, True)))
            for key in ARTWORK_SOURCE_LABELS
        }
        self.metadata_source_vars = {
            key: tk.BooleanVar(value=bool(self.settings.metadata_sources.get(key, True)))
            for key in METADATA_SOURCE_LABELS
        }

    def _build_style(self) -> None:
        palette = self.palette()
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        self.configure(bg=palette["bg"])
        style.configure("TFrame", background=palette["bg"])
        style.configure("TLabelframe", background=palette["bg"], bordercolor=palette["border"])
        style.configure("TLabelframe.Label", background=palette["bg"], foreground=palette["text"], font=("Segoe UI", 10, "bold"))
        style.configure("TLabel", background=palette["bg"], foreground=palette["text"], font=("Segoe UI", 9))
        style.configure("Header.TLabel", font=("Segoe UI", 17, "bold"), foreground=palette["strong"], background=palette["bg"])
        style.configure("Subtle.TLabel", foreground=palette["muted"], background=palette["bg"])
        style.configure("TButton", background=palette["button_bg"], foreground=palette["text"], bordercolor=palette["border"])
        style.configure("Accent.TButton", font=("Segoe UI", 9, "bold"), background=palette["accent"], foreground=palette["accent_text"])
        style.configure("TCheckbutton", background=palette["bg"], foreground=palette["text"])
        style.configure("TRadiobutton", background=palette["bg"], foreground=palette["text"])
        style.configure("TNotebook", background=palette["bg"], bordercolor=palette["border"])
        style.configure("TNotebook.Tab", background=palette["header_bg"], foreground=palette["text"])
        style.configure("Treeview", rowheight=28, font=("Segoe UI", 9), background=palette["panel"], fieldbackground=palette["panel"], foreground=palette["text"])
        style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"), background=palette["header_bg"], foreground=palette["text"])
        style.configure("TEntry", fieldbackground=palette["entry"], foreground=palette["text"])
        style.configure("TCombobox", fieldbackground=palette["entry"], foreground=palette["text"])
        style.configure("TMenubutton", background=palette["button_bg"], foreground=palette["text"])
        style.configure("Horizontal.TProgressbar", troughcolor=palette["entry"], background=palette["accent"], bordercolor=palette["border"], lightcolor=palette["accent"], darkcolor=palette["accent"])
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", palette["entry"])],
            foreground=[("readonly", palette["text"])],
            selectbackground=[("readonly", palette["entry"])],
            selectforeground=[("readonly", palette["text"])],
        )
        style.map("TButton", background=[("active", palette["selected"])], foreground=[("active", palette["selected_text"])])
        style.map("Accent.TButton", background=[("active", palette["selected"])], foreground=[("active", palette["selected_text"])])
        style.map("TNotebook.Tab", background=[("selected", palette["panel"])], foreground=[("selected", palette["strong"])])
        style.map("TMenubutton", background=[("active", palette["selected"])], foreground=[("active", palette["selected_text"])])
        style.map("Treeview", background=[("selected", palette["selected"])], foreground=[("selected", palette["selected_text"])])

    def normalized_theme_name(self, theme: str | None) -> str:
        theme = THEME_ALIASES.get(str(theme), str(theme)) if theme else theme
        if theme in THEMES:
            return str(theme)
        if getattr(self, "settings", None) and self.settings.dark_mode:
            return "Steam Deck Blue"
        return "Follow System"

    def system_prefers_dark(self) -> bool:
        if winreg is None:
            return False
        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
            ) as key:
                value, _kind = winreg.QueryValueEx(key, "AppsUseLightTheme")
            return int(value) == 0
        except Exception:
            return False

    def effective_theme_name(self, theme: str | None = None) -> str:
        selected = theme or (self.theme_var.get() if hasattr(self, "theme_var") else self.settings.theme_name)
        selected = self.normalized_theme_name(selected)
        if selected == "Follow System":
            return "Steam Deck Blue" if self.system_prefers_dark() else "Classic Light"
        return selected

    def theme_is_dark(self, theme: str | None = None) -> bool:
        return self.effective_theme_name(theme) not in {"Classic Light", "Glacier Blue", "Candy Pop"}

    def palette(self) -> dict[str, str]:
        selected = self.theme_var.get() if hasattr(self, "theme_var") else self.settings.theme_name
        theme = self.effective_theme_name(selected)
        base = dict(THEME_PALETTES.get(theme, THEME_PALETTES["Classic Light"]))
        base.setdefault("accent", base["selected"])
        base.setdefault("accent_text", base["selected_text"])
        base.setdefault("success", "#16855d")
        base.setdefault("warning", "#a16207")
        base.setdefault("error", "#b42318")
        return base

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        for row in range(5):
            self.rowconfigure(row, weight=0)
        self.rowconfigure(1, weight=1)
        self.build_menu_bar()

        header = ttk.Frame(self, padding=(18, 10, 18, 4))
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text="Steam Shortcut Studio", style="Header.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            header,
            text="Scan game folders, choose the right launch file, fetch Steam-style art, and write safe non-Steam shortcuts.",
            style="Subtle.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(2, 0))
        ttk.Label(header, textvariable=self.profile_status_var, style="Subtle.TLabel").grid(row=1, column=1, sticky="e", padx=(0, 12))
        ttk.Label(header, text="Theme", style="Subtle.TLabel").grid(row=0, column=2, sticky="e", padx=(0, 6))
        self.theme_combo = ttk.Combobox(header, textvariable=self.theme_var, values=THEMES, state="readonly", width=18)
        self.theme_combo.grid(row=0, column=3, sticky="e")
        self.theme_combo.bind("<<ComboboxSelected>>", lambda _event: self.apply_theme_selection())
        ToolTip(self.theme_combo, "Pick a full app skin. Themes use stronger Steam-keyboard-inspired color identities and are saved in Settings.")

        main = ttk.Frame(self)
        main.grid(row=1, column=0, sticky="nsew", padx=18, pady=(2, 8))
        main.columnconfigure(0, weight=1, uniform="main")
        main.columnconfigure(1, weight=1, uniform="main")
        main.rowconfigure(0, weight=1)
        left_panel = ttk.Frame(main)
        self.detail_frame = ttk.Frame(main)
        left_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        self.detail_frame.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        left_panel.columnconfigure(0, weight=1)
        left_panel.rowconfigure(1, weight=1)

        setup = ttk.LabelFrame(left_panel, text="Library Location", padding=(10, 6))
        setup.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        setup.columnconfigure(1, weight=1)
        for col in (2, 3, 4):
            setup.columnconfigure(col, weight=0, minsize=78)
        button_width = 9

        ttk.Label(setup, text="1. Steam").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=1)
        steam_entry = ttk.Entry(setup, textvariable=self.steam_path_var)
        steam_entry.grid(row=0, column=1, sticky="ew", pady=1)
        ToolTip(steam_entry, "Steam install folder. The app looks for Steam's launcher and userdata here.")
        browse_steam_button = ttk.Button(setup, text="Browse", width=button_width, command=self.browse_steam)
        browse_steam_button.grid(row=0, column=2, padx=(8, 6), pady=1)
        ToolTip(browse_steam_button, "Manually choose the Steam folder if detection misses it.")
        detect_button = ttk.Button(setup, text="Detect", width=button_width, command=self.detect_steam)
        detect_button.grid(row=0, column=3, padx=(0, 6), pady=1)
        ToolTip(detect_button, "Auto-detect Steam from common install folders.")
        ttk.Label(setup, text="2. Games").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=1)
        collection_entry = ttk.Entry(setup, textvariable=self.collection_path_var)
        collection_entry.grid(row=1, column=1, sticky="ew", pady=1)
        ToolTip(collection_entry, "Root folder containing your non-Steam games. Each top-level child folder becomes the game title.")
        choose_button = ttk.Button(setup, text="Browse", width=button_width, command=self.browse_collection)
        choose_button.grid(row=1, column=2, padx=(8, 6), pady=1)
        ToolTip(choose_button, "Pick the folder to scan recursively for launch files.")
        scan_button = ttk.Button(setup, text="Scan", width=button_width, style="Accent.TButton", command=self.scan_all_libraries)
        scan_button.grid(row=0, column=4, rowspan=2, sticky="nsew", padx=(6, 0), pady=1)
        ToolTip(scan_button, "Scan installed Steam games, existing non-Steam shortcuts, and the chosen game folder in one pass.")

        self.table_frame = ttk.Frame(left_panel)
        self.table_frame.grid(row=1, column=0, sticky="nsew")
        self._build_table(self.table_frame)
        self._build_detail(self.detail_frame)

        actions = ttk.Frame(self, padding=(18, 0, 18, 8))
        actions.grid(row=2, column=0, sticky="ew")
        for col in (0, 1, 3, 4):
            actions.columnconfigure(col, weight=0)
        actions.columnconfigure(2, weight=1)
        action_width = 16
        match_button = ttk.Button(actions, text="Search Art", width=action_width, command=lambda: self.match_metadata_and_art_for_selected(force_refresh=True))
        match_button.grid(row=0, column=0, padx=(0, 8))
        ToolTip(match_button, "Rerun artwork search for checked games in the current view only.")
        preview_button = ttk.Button(actions, text="Preview", width=action_width, command=self.preview_write)
        preview_button.grid(row=0, column=1, padx=(0, 8))
        ToolTip(preview_button, "Show exactly what will be added or updated before touching Steam files.")
        source_actions = ttk.Frame(actions)
        source_actions.grid(row=0, column=2, sticky="w")
        library_button = ttk.Button(source_actions, text="Library", width=action_width, command=self.load_persistent_library)
        library_button.grid(row=0, column=0, padx=(0, 8))
        ToolTip(library_button, "Load the app-owned persistent library through the production controller.")
        sync_sources_button = ttk.Button(source_actions, text="Sync Sources", width=action_width, command=self.scan_persistent_sources)
        sync_sources_button.grid(row=0, column=1, padx=(0, 8))
        ToolTip(sync_sources_button, "Scan Epic, Steam, and the chosen folder into the app-owned persistent library through the production controller.")
        backups_button = ttk.Button(source_actions, text="Backups", width=action_width, command=self.show_transaction_history)
        backups_button.grid(row=0, column=2)
        ToolTip(backups_button, "Show verified transaction history and available restore backups.")
        write_button = ttk.Button(actions, text="Write to Steam", width=action_width, style="Accent.TButton", command=self.write_to_steam)
        write_button.grid(row=0, column=3, sticky="e", padx=(8, 8))
        ToolTip(write_button, "Closes running Steam when needed, writes shortcuts, artwork, and simple notes with backups, then reopens Steam only if this app closed it.")
        self.cancel_button = ttk.Button(actions, text="Cancel Operations", width=18, command=self.cancel_current_job, state=tk.DISABLED)
        self.cancel_button.grid(row=0, column=4, sticky="e")
        ToolTip(self.cancel_button, "Ask the current scan, notes, or artwork job to stop as soon as it reaches a safe checkpoint.")

        progress_frame = ttk.Frame(self, padding=(18, 0, 18, 8))
        progress_frame.grid(row=3, column=0, sticky="ew")
        progress_frame.columnconfigure(0, weight=1)
        ttk.Label(progress_frame, textvariable=self.status_var, style="Subtle.TLabel").grid(row=0, column=0, sticky="ew", pady=(0, 4))
        self.progress = ttk.Progressbar(progress_frame, mode="indeterminate")
        self.progress.grid(row=1, column=0, sticky="ew")

        log_frame = ttk.LabelFrame(self, text="Log", padding=8)
        log_frame.grid(row=4, column=0, sticky="ew", padx=18, pady=(0, 14))
        log_frame.columnconfigure(0, weight=1)
        self.log_text = tk.Text(log_frame, height=6, wrap="word", font=("Consolas", 9), relief="flat", bg="#ffffff")
        self.log_text.grid(row=0, column=0, sticky="ew")
        log_scroll = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        log_scroll.grid(row=0, column=1, sticky="ns")
        self.log_text.configure(yscrollcommand=log_scroll.set)
        self.apply_widget_theme()

    def toggle_dark_mode(self) -> None:
        self.theme_var.set("Steam Deck Blue" if self.dark_mode_var.get() else "Classic Light")
        self.apply_theme_selection()

    def apply_theme_selection(self) -> None:
        selected_theme = self.normalized_theme_name(self.theme_var.get())
        self.theme_var.set(selected_theme)
        self.dark_mode_var.set(self.theme_is_dark(selected_theme))
        self.settings.theme_name = selected_theme
        self.settings.dark_mode = self.theme_is_dark(selected_theme)
        self._build_style()
        self.build_menu_bar()
        self.apply_widget_theme()
        self.save_settings_from_ui(log=False)

    def apply_widget_theme(self) -> None:
        palette = self.palette()
        text_bg = palette["panel"]
        for widget in self.winfo_children():
            self._theme_child(widget, palette)
        if hasattr(self, "artwork_canvas"):
            self.artwork_canvas.configure(bg=palette["canvas"])
        if hasattr(self, "preview_boxes"):
            for box in self.preview_boxes.values():
                box.configure(bg=palette["canvas"], highlightbackground=palette["border"])
        if hasattr(self, "preview_labels"):
            for label in self.preview_labels.values():
                label.configure(bg=palette["canvas"], fg=palette["muted"])
        if hasattr(self, "games_tree"):
            self.configure_game_tree_tags()
        for text_widget_name in ("log_text", "description_text", "reason_text"):
            if hasattr(self, text_widget_name):
                widget = getattr(self, text_widget_name)
                try:
                    widget.configure(bg=text_bg, fg=palette["text"], insertbackground=palette["text"])
                except tk.TclError:
                    pass

    def _theme_child(self, widget: tk.Widget, palette: dict[str, str]) -> None:
        if isinstance(widget, tk.Text):
            widget.configure(bg=palette["panel"], fg=palette["text"], insertbackground=palette["text"])
        elif isinstance(widget, tk.Canvas):
            widget.configure(bg=palette["canvas"])
        elif isinstance(widget, tk.Label):
            widget.configure(bg=palette["panel"], fg=palette["text"])
        elif isinstance(widget, tk.Frame):
            widget.configure(bg=palette["bg"])
        elif isinstance(widget, tk.Button):
            widget.configure(bg=palette["button_bg"], fg=palette["text"], activebackground=palette["selected"], activeforeground=palette["selected_text"])
        for child in widget.winfo_children():
            self._theme_child(child, palette)

    def build_menu_bar(self) -> None:
        palette = self.palette()
        menu_config = {"bg": palette["panel"], "fg": palette["text"], "activebackground": palette["selected"], "activeforeground": palette["selected_text"]}
        menubar = tk.Menu(self, **menu_config)

        file_menu = tk.Menu(menubar, tearoff=False, **menu_config)
        file_menu.add_command(label="Preview Changes", command=self.preview_write)
        file_menu.add_command(label="Write to Steam", command=self.write_to_steam)
        file_menu.add_separator()
        file_menu.add_command(label="Export Report as JSON", command=lambda: self.export_report("json"))
        file_menu.add_command(label="Export Report as CSV", command=lambda: self.export_report("csv"))
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.destroy)
        menubar.add_cascade(label="File", menu=file_menu)

        self.settings_menu = tk.Menu(menubar, tearoff=False, **menu_config)
        self.profile_menu = tk.Menu(self.settings_menu, tearoff=False, **menu_config)
        self.settings_menu.add_command(label="Settings...", command=self.open_settings_dialog)
        self.settings_menu.add_cascade(label="Profile", menu=self.profile_menu)
        self.settings_menu.add_separator()
        self.settings_menu.add_command(label="Import Settings...", command=self.import_settings)
        self.settings_menu.add_command(label="Export Settings...", command=self.export_settings)
        self.settings_menu.add_separator()
        self.settings_menu.add_command(label="Show Log File Path", command=self.show_log_file_path)
        self.settings_menu.add_command(label="Clear Log", command=self.clear_log)
        menubar.add_cascade(label="Settings", menu=self.settings_menu)

        self.configure(menu=menubar)
        self.rebuild_profile_menu()

    def rebuild_profile_menu(self) -> None:
        if not hasattr(self, "profile_menu"):
            return
        self.profile_menu.delete(0, tk.END)
        if not self.profiles:
            self.profile_menu.add_command(label="No Steam profiles detected", state=tk.DISABLED)
            self.profile_status_var.set("Profile: none")
            return
        for profile in self.profiles:
            self.profile_menu.add_radiobutton(
                label=profile.display_name,
                variable=self.profile_var,
                value=profile.display_name,
                command=lambda selected=profile.display_name: self.select_profile_by_label(selected),
            )
        self.update_profile_status()

    def select_profile_by_label(self, label: str) -> None:
        self.profile_var.set(label)
        self.update_profile_status()
        self.save_settings_from_ui()

    def update_profile_status(self) -> None:
        profile = self.current_profile()
        self.profile_status_var.set(f"Profile: {profile.display_name}" if profile else "Profile: none")

    def reset_game_columns(self) -> None:
        self.settings.game_column_order = list(GAME_COLUMNS)
        self.settings.visible_game_columns = list(GAME_COLUMNS)
        self.apply_game_columns()
        self.save_settings_from_ui(log=False)

    def make_menu_button(self, parent: tk.Widget, text: str, items: list[tuple[str, Callable[[], None]] | None]) -> ttk.Menubutton:
        button = ttk.Menubutton(parent, text=text)
        palette = self.palette()
        menu = tk.Menu(
            button,
            tearoff=False,
            bg=palette["panel"],
            fg=palette["text"],
            activebackground=palette["selected"],
            activeforeground=palette["selected_text"],
        )
        button["menu"] = menu
        for item in items:
            if item is None:
                menu.add_separator()
                continue
            label, command = item
            menu.add_command(label=label, command=command)
        return button

    def clear_log(self) -> None:
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", tk.END)

    def show_log_file_path(self) -> None:
        messagebox.showinfo(__app_name__, f"Log file:\n\n{self.log_path}")

    def apply_settings_to_ui(self) -> None:
        self.steam_path_var.set(normalize_windows_path_text(self.settings.steam_path))
        self.collection_path_var.set(normalize_windows_path_text(self.settings.collection_root))
        self.api_key_var.set(self.settings.steamgriddb_api_key)
        self.rawg_api_key_var.set(self.settings.rawg_api_key)
        self.sgdboop_path_var.set(normalize_windows_path_text(self.settings.sgdboop_path))
        self.update_existing_var.set(self.settings.update_existing_shortcuts)
        self.default_tags_var.set(", ".join(self.settings.default_tags))
        self.compat_tool_var.set(self.compat_tool_display_name(self.settings.steam_play_compat_tool))
        theme = self.normalized_theme_name(self.settings.theme_name)
        self.theme_var.set(theme)
        self.dark_mode_var.set(self.theme_is_dark(theme))
        self.view_filter_var.set(self.settings.view_filter if self.settings.view_filter in VIEW_FILTERS else "All")
        self.sort_preset_var.set(self.settings.sort_preset if self.settings.sort_preset in SORT_PRESETS else "Title A-Z")
        self.preview_limit_var.set(self.settings.artwork_preview_limit)
        for key, var in self.artwork_source_vars.items():
            var.set(bool(self.settings.artwork_sources.get(key, True)))
        for key, var in self.metadata_source_vars.items():
            var.set(bool(self.settings.metadata_sources.get(key, True)))
        self.artwork_cache_path = Path(self.settings.cache_dir) / "artwork_search_cache.json"
        self.settings_location_var.set(str(self.settings_store.settings_path))
        self.cache_location_var.set(str(Path(self.settings.cache_dir)))

    def path_is_inside(self, path: Path, parent: Path) -> bool:
        try:
            return path.expanduser().resolve(strict=False).is_relative_to(parent.expanduser().resolve(strict=False))
        except OSError:
            return False

    def clear_cached_artwork_references(self, cache_dir: Path) -> int:
        cleared = 0
        for game in self.games:
            for kind in ARTWORK_KINDS:
                asset = getattr(game.artwork, kind)
                if not asset or not asset.local_path:
                    continue
                if self.path_is_inside(asset.local_path, cache_dir) or not asset.local_path.exists():
                    setattr(game.artwork, kind, None)
                    self.manual_artwork_slots.discard((id(game), kind))
                    cleared += 1
        return cleared

    def delete_cached_artwork(self) -> None:
        cache_dir = Path(self.settings.cache_dir)
        confirmed = messagebox.askyesno(
            __app_name__,
            f"Delete cached artwork downloads and artwork search caches?\n\n{cache_dir}\n\nSteam artwork already written to Steam will not be removed.",
        )
        if not confirmed:
            return
        try:
            result = self.settings_store.clear_cached_artwork(self.settings)
        except Exception as exc:
            self.logger.exception("Could not delete cached artwork: %s", exc)
            messagebox.showerror(__app_name__, f"Could not delete cached artwork:\n\n{exc}")
            return
        self.artwork_search_cache.clear()
        self.artwork_title_cache.clear()
        self.current_artwork_results.clear()
        self.image_cache.clear()
        cleared_slots = self.clear_cached_artwork_references(cache_dir)
        if self.games:
            self.refresh_game_table(select_index=self.current_game_index)
        if self.current_game_index is not None:
            self.update_artwork_previews()
            self.populate_artwork_results([])
        self.cache_location_var.set(str(Path(self.settings.cache_dir)))
        self.status_var.set("Cached artwork deleted.")
        self.logger.info(
            "Deleted cached artwork from %s: %s file(s), %s byte(s), %s active slot(s) cleared.",
            cache_dir,
            result.files_deleted,
            result.bytes_deleted,
            cleared_slots,
        )
        messagebox.showinfo(
            __app_name__,
            f"Cached artwork deleted.\n\nFiles deleted: {result.files_deleted}\nActive artwork slots cleared: {cleared_slots}",
        )

    def reset_settings_to_defaults(self) -> None:
        confirmed = messagebox.askyesno(
            __app_name__,
            "Reset all app settings to defaults?\n\nThis clears saved paths, API keys, source toggles, filters, theme, profile choice, and column layout. Cached artwork and Steam files are not deleted.",
        )
        if not confirmed:
            return
        self.settings = self.settings_store.reset_to_defaults()
        self.apply_settings_to_ui()
        self.artwork_search_cache.clear()
        self.artwork_title_cache.clear()
        self.load_persistent_artwork_search_cache()
        self.refresh_profiles()
        self.apply_game_columns()
        self.apply_sort_preset()
        self.apply_view_filter()
        self._build_style()
        self.build_menu_bar()
        self.apply_widget_theme()
        self.status_var.set("Settings reset to defaults.")
        self.logger.info("Settings reset to defaults at %s", self.settings_store.settings_path)
        messagebox.showinfo(__app_name__, "Settings were reset to defaults.")

    def open_settings_dialog(self) -> None:
        window = tk.Toplevel(self)
        window.title("Steam Shortcut Studio Settings")
        window.geometry("660x520")
        window.transient(self)
        window.grab_set()
        window.columnconfigure(0, weight=1)
        window.rowconfigure(0, weight=1)

        notebook = ttk.Notebook(window)
        notebook.grid(row=0, column=0, sticky="nsew", padx=12, pady=12)

        general = ttk.Frame(notebook, padding=12)
        artwork = ttk.Frame(notebook, padding=12)
        maintenance = ttk.Frame(notebook, padding=12)
        notebook.add(general, text="General")
        notebook.add(artwork, text="Artwork")
        notebook.add(maintenance, text="Maintenance")

        general.columnconfigure(1, weight=1)
        ttk.Label(general, text="Steam profile").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=4)
        profile_combo = ttk.Combobox(general, textvariable=self.profile_var, values=[profile.display_name for profile in self.profiles], state="readonly")
        profile_combo.grid(row=0, column=1, sticky="ew", pady=4)
        profile_combo.bind("<<ComboboxSelected>>", lambda _event: self.update_profile_status())
        ttk.Checkbutton(general, text="Update matching non-Steam shortcuts instead of duplicating them", variable=self.update_existing_var).grid(
            row=1,
            column=0,
            columnspan=2,
            sticky="w",
            pady=(6, 10),
        )
        ttk.Label(general, text="Default shortcut tags").grid(row=2, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Entry(general, textvariable=self.default_tags_var).grid(row=2, column=1, sticky="ew", pady=4)
        ttk.Label(general, text="Theme").grid(row=3, column=0, sticky="w", padx=(0, 8), pady=4)
        theme_dialog_combo = ttk.Combobox(general, textvariable=self.theme_var, values=THEMES, state="readonly")
        theme_dialog_combo.grid(row=3, column=1, sticky="ew", pady=4)
        theme_preview = tk.Canvas(general, width=150, height=26, highlightthickness=1, highlightbackground=self.palette()["border"])
        theme_preview.grid(row=3, column=2, sticky="w", padx=(8, 0), pady=4)

        def draw_theme_preview() -> None:
            palette = self.palette()
            theme_preview.configure(bg=palette["panel"], highlightbackground=palette["border"])
            theme_preview.delete("all")
            colors = [palette["bg"], palette["panel"], palette["button_bg"], palette["accent"], palette["selected"], palette["success"], palette["warning"], palette["error"]]
            width = 150 // len(colors)
            for index, color in enumerate(colors):
                theme_preview.create_rectangle(index * width, 0, (index + 1) * width, 26, fill=color, outline="")

        theme_dialog_combo.bind("<<ComboboxSelected>>", lambda _event: draw_theme_preview())
        draw_theme_preview()
        ttk.Label(general, text="Default view").grid(row=4, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Combobox(general, textvariable=self.view_filter_var, values=VIEW_FILTERS, state="readonly").grid(row=4, column=1, sticky="ew", pady=4)
        ttk.Label(general, text="Default sort").grid(row=5, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Combobox(general, textvariable=self.sort_preset_var, values=SORT_PRESETS, state="readonly").grid(row=5, column=1, sticky="ew", pady=4)
        ttk.Label(general, text="Steam Play compatibility").grid(row=6, column=0, sticky="w", padx=(0, 8), pady=4)
        compat_combo = ttk.Combobox(general, textvariable=self.compat_tool_var, values=list(COMPAT_TOOL_CHOICES), state="normal")
        compat_combo.grid(row=6, column=1, sticky="ew", pady=4)
        ttk.Label(
            general,
            text="Linux only. Pick a Proton option or type the exact Steam compatibility tool id.",
            style="Subtle.TLabel",
            wraplength=470,
        ).grid(row=7, column=1, sticky="w", pady=(0, 8))
        ttk.Button(general, text="Reset Table Columns", command=self.reset_game_columns).grid(row=8, column=1, sticky="w", pady=(8, 0))

        artwork.columnconfigure(1, weight=1)
        ttk.Label(artwork, text="SteamGridDB API key").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=4)
        sgdb_key_row = ttk.Frame(artwork)
        sgdb_key_row.grid(row=0, column=1, sticky="ew", pady=4)
        sgdb_key_row.columnconfigure(0, weight=1)
        ttk.Entry(sgdb_key_row, textvariable=self.api_key_var, show="*").grid(row=0, column=0, sticky="ew")
        ttk.Button(sgdb_key_row, text="Get Key", command=lambda: self.open_external_url(STEAMGRIDDB_API_URL)).grid(row=0, column=1, padx=(6, 0))
        ttk.Label(artwork, text="RAWG API key").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=4)
        rawg_key_row = ttk.Frame(artwork)
        rawg_key_row.grid(row=1, column=1, sticky="ew", pady=4)
        rawg_key_row.columnconfigure(0, weight=1)
        ttk.Entry(rawg_key_row, textvariable=self.rawg_api_key_var, show="*").grid(row=0, column=0, sticky="ew")
        ttk.Button(rawg_key_row, text="RAWG Docs", command=lambda: self.open_external_url(RAWG_API_URL)).grid(row=0, column=1, padx=(6, 0))
        ttk.Label(artwork, text="SGDBoop path").grid(row=2, column=0, sticky="w", padx=(0, 8), pady=4)
        sgdboop_row = ttk.Frame(artwork)
        sgdboop_row.grid(row=2, column=1, sticky="ew", pady=4)
        sgdboop_row.columnconfigure(0, weight=1)
        ttk.Entry(sgdboop_row, textvariable=self.sgdboop_path_var).grid(row=0, column=0, sticky="ew")
        ttk.Button(sgdboop_row, text="Detect", command=self.detect_sgdboop).grid(row=0, column=1, padx=(6, 0))
        ttk.Label(artwork, text="Previews per artwork type").grid(row=3, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Spinbox(artwork, from_=4, to=80, increment=4, textvariable=self.preview_limit_var, width=8).grid(row=3, column=1, sticky="w", pady=4)
        source_frame = ttk.LabelFrame(artwork, text="Artwork Sources", padding=8)
        source_frame.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(10, 4))
        for row, (key, label) in enumerate(ARTWORK_SOURCE_LABELS.items()):
            ttk.Checkbutton(source_frame, text=label, variable=self.artwork_source_vars[key]).grid(row=row // 2, column=row % 2, sticky="w", padx=(0, 18), pady=2)
        ttk.Label(
            artwork,
            text="Official Steam and Wikimedia work without extra keys. SteamGridDB and RAWG are used when their keys are saved and the source is checked.",
            style="Subtle.TLabel",
            wraplength=560,
        ).grid(row=5, column=0, columnspan=2, sticky="w", pady=(12, 0))

        maintenance.columnconfigure(1, weight=1)
        ttk.Label(maintenance, text="Settings file").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Label(maintenance, textvariable=self.settings_location_var, style="Subtle.TLabel", wraplength=470).grid(row=0, column=1, sticky="ew", pady=4)
        ttk.Label(maintenance, text="Cache folder").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Label(maintenance, textvariable=self.cache_location_var, style="Subtle.TLabel", wraplength=470).grid(row=1, column=1, sticky="ew", pady=4)

        maintenance_actions = ttk.LabelFrame(maintenance, text="App Data", padding=10)
        maintenance_actions.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(14, 0))
        maintenance_actions.columnconfigure(1, weight=1)
        ttk.Button(maintenance_actions, text="Delete Cached Artwork", command=self.delete_cached_artwork).grid(row=0, column=0, sticky="w", pady=4)
        ttk.Label(maintenance_actions, text="Removes downloaded artwork previews and artwork search caches.", style="Subtle.TLabel").grid(row=0, column=1, sticky="w", padx=(10, 0), pady=4)
        ttk.Button(maintenance_actions, text="Reset Settings to Defaults", command=self.reset_settings_to_defaults).grid(row=1, column=0, sticky="w", pady=4)
        ttk.Label(maintenance_actions, text="Restores paths, keys, Steam Play choice, theme, filters, source toggles, and columns.", style="Subtle.TLabel").grid(row=1, column=1, sticky="w", padx=(10, 0), pady=4)

        buttons = ttk.Frame(window, padding=(12, 0, 12, 12))
        buttons.grid(row=1, column=0, sticky="ew")
        buttons.columnconfigure(0, weight=1)
        ttk.Button(buttons, text="Cancel", command=window.destroy).grid(row=0, column=1, padx=(0, 8))
        ttk.Button(
            buttons,
            text="Save",
            style="Accent.TButton",
            command=lambda: (self.update_profile_status(), self.rebuild_profile_menu(), self.apply_theme_selection(), self.save_settings_from_ui(), self.apply_view_filter(), window.destroy()),
        ).grid(
            row=0,
            column=2,
        )
        self.apply_widget_theme()

    def _build_table(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)
        table_actions = ttk.Frame(parent)
        table_actions.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 6))
        selection_menu = self.make_menu_button(
            table_actions,
            "Selection",
            [
                ("Select all", lambda: self.set_games_selected(True, visible_only=False)),
                ("Clear all", lambda: self.set_games_selected(False, visible_only=False)),
                ("Select inverse", self.invert_all_selection),
                None,
                ("Select visible", lambda: self.set_games_selected(True, visible_only=True)),
                ("Clear visible", lambda: self.set_games_selected(False, visible_only=True)),
                ("Invert visible", self.invert_visible_selection),
                ("Select current filter", lambda: self.set_current_filter_selected(True)),
                ("Clear current filter", lambda: self.set_current_filter_selected(False)),
                ("Invert current filter", self.invert_current_filter_selection),
                None,
                ("Select games needing artwork", self.select_needing_artwork),
                ("Select new non-Steam shortcuts", self.select_new_nonsteam),
            ],
        )
        selection_menu.pack(side=tk.LEFT, padx=(0, 8))
        ToolTip(selection_menu, "Selection tools inspired by parser preview workflows: work on visible rows or target likely follow-up work.")
        ttk.Label(table_actions, text="View").pack(side=tk.LEFT, padx=(4, 4))
        self.view_filter_combo = ttk.Combobox(
            table_actions,
            textvariable=self.view_filter_var,
            values=VIEW_FILTERS,
            state="readonly",
            width=18,
        )
        self.view_filter_combo.pack(side=tk.LEFT, padx=(0, 10))
        self.view_filter_combo.bind("<<ComboboxSelected>>", lambda _event: self.apply_view_filter())
        ToolTip(self.view_filter_combo, "Filter the list without changing the underlying scan results.")
        ttk.Label(table_actions, text="Sort").pack(side=tk.LEFT, padx=(0, 4))
        self.sort_preset_combo = ttk.Combobox(
            table_actions,
            textvariable=self.sort_preset_var,
            values=SORT_PRESETS,
            state="readonly",
            width=20,
        )
        self.sort_preset_combo.pack(side=tk.LEFT, padx=(0, 10))
        self.sort_preset_combo.bind("<<ComboboxSelected>>", lambda _event: self.apply_sort_preset())
        ToolTip(self.sort_preset_combo, "Use common sort recipes, or click column headers for one-off sorting.")
        refresh_selected_button = ttk.Button(table_actions, text="Refresh Selected Sources", command=self.scan_selected_persistent_sources)
        refresh_selected_button.pack(side=tk.LEFT, padx=(0, 10))
        ToolTip(refresh_selected_button, "Rescan only the launcher/source types represented by selected persistent library rows.")
        plan_art_button = ttk.Button(table_actions, text="Plan Selected Art", command=self.queue_persistent_artwork_searches)
        plan_art_button.pack(side=tk.LEFT, padx=(0, 10))
        ToolTip(plan_art_button, "Queue selected persistent rows through real provider search and review-safe artwork planning.")
        art_decisions_button = ttk.Button(table_actions, text="Art Decisions", command=self.show_selected_artwork_decisions)
        art_decisions_button.pack(side=tk.LEFT, padx=(0, 10))
        ToolTip(art_decisions_button, "Show persisted accepted/rejected artwork provider decisions for selected persistent rows.")
        accept_art_button = ttk.Button(table_actions, text="Accept Art Review", command=self.accept_selected_artwork_reviews)
        accept_art_button.pack(side=tk.LEFT, padx=(0, 10))
        ToolTip(accept_art_button, "Persist latest review-needed provider candidates as accepted artwork choices for selected rows.")
        reject_art_button = ttk.Button(table_actions, text="Reject Art Review", command=self.reject_selected_artwork_reviews)
        reject_art_button.pack(side=tk.LEFT, padx=(0, 10))
        ToolTip(reject_art_button, "Persist latest review-needed provider candidates as rejected for selected rows.")
        skip_art_button = ttk.Button(table_actions, text="Skip Art Review", command=self.skip_selected_artwork_reviews)
        skip_art_button.pack(side=tk.LEFT, padx=(0, 10))
        ToolTip(skip_art_button, "Dismiss latest review-needed provider candidates for selected rows without persisting a decision.")
        retry_art_button = ttk.Button(table_actions, text="Retry Art Review", command=self.retry_selected_artwork_reviews)
        retry_art_button.pack(side=tk.LEFT, padx=(0, 10))
        ToolTip(retry_art_button, "Retry selected pending artwork reviews without rerunning already accepted rows.")
        clear_art_rejections_button = ttk.Button(table_actions, text="Clear Art Rejections", command=self.clear_selected_artwork_rejections)
        clear_art_rejections_button.pack(side=tk.LEFT, padx=(0, 10))
        ToolTip(clear_art_rejections_button, "Clear persisted rejected artwork candidates for selected persistent rows after review.")
        retry_sources_button = ttk.Button(table_actions, text="Retry Source Reviews", command=self.retry_reviewed_source_scans)
        retry_sources_button.pack(side=tk.LEFT, padx=(0, 10))
        ToolTip(retry_sources_button, "Retry source refresh jobs that ended in review or failure.")
        clear_reviews_button = ttk.Button(table_actions, text="Clear Source Reviews", command=self.clear_reviewed_source_scans)
        clear_reviews_button.pack(side=tk.LEFT, padx=(0, 10))
        ToolTip(clear_reviews_button, "Dismiss remembered source refresh review/failure jobs after you have handled them.")
        ttk.Label(table_actions, textvariable=self.bulk_status_var, style="Subtle.TLabel").pack(side=tk.RIGHT)
        ttk.Label(table_actions, text="Right-click headers for columns.", style="Subtle.TLabel").pack(side=tk.LEFT, padx=(8, 0))
        self.games_tree = ttk.Treeview(parent, columns=GAME_COLUMNS, show="headings", selectmode="browse")
        for column in GAME_COLUMNS:
            self.games_tree.heading(column, text=GAME_COLUMN_LABELS[column], command=lambda selected=column: self.sort_games_by_column(selected))
            self.games_tree.column(column, width=GAME_COLUMN_WIDTHS[column], minwidth=40, anchor=tk.W)
        self.configure_game_tree_tags()
        self.apply_game_columns()
        self.games_tree.grid(row=1, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=self.games_tree.yview)
        scrollbar.grid(row=1, column=1, sticky="ns")
        self.games_tree.configure(yscrollcommand=scrollbar.set)
        self.games_tree.bind("<<TreeviewSelect>>", self.on_game_selected)
        self.games_tree.bind("<ButtonRelease-1>", self.on_game_table_click)
        self.games_tree.bind("<space>", self.on_game_table_space)
        self.games_tree.bind("<Button-3>", self.show_column_context_menu)

    def configure_game_tree_tags(self) -> None:
        if not hasattr(self, "games_tree"):
            return
        palette = self.palette()
        self.games_tree.tag_configure("unselected", foreground=palette["muted"])

    def game_row_tags(self, game: DetectedGame) -> tuple[str, ...]:
        return () if game.selected else ("unselected",)

    def normalized_column_order(self) -> list[str]:
        order = [column for column in self.settings.game_column_order if column in GAME_COLUMNS]
        order.extend(column for column in GAME_COLUMNS if column not in order)
        return order

    def normalized_visible_columns(self) -> list[str]:
        visible = [column for column in self.settings.visible_game_columns if column in GAME_COLUMNS]
        if not visible:
            visible = ["add", "title", "exe"]
        return visible

    def selected_column_id(self) -> str:
        label = self.column_choice_var.get()
        for column, column_label in GAME_COLUMN_LABELS.items():
            if column_label == label:
                return column
        return "title"

    def sync_column_visible_var(self) -> None:
        self.column_visible_var.set(self.selected_column_id() in self.normalized_visible_columns())

    def apply_game_columns(self) -> None:
        order = self.normalized_column_order()
        visible = set(self.normalized_visible_columns())
        display = [column for column in order if column in visible]
        if not display:
            display = ["title"]
        if hasattr(self, "games_tree"):
            self.games_tree["displaycolumns"] = display
        self.settings.game_column_order = order
        self.settings.visible_game_columns = display
        self.sync_column_visible_var()

    def toggle_selected_column_visible(self) -> None:
        column = self.selected_column_id()
        self.toggle_column_by_id(column, self.column_visible_var.get())

    def toggle_column_by_id(self, column: str, visible_state: bool | None = None) -> None:
        if column not in GAME_COLUMNS:
            return
        visible = self.normalized_visible_columns()
        should_show = (column not in visible) if visible_state is None else visible_state
        if should_show:
            if column not in visible:
                visible.append(column)
        else:
            visible = [item for item in visible if item != column]
        if not visible:
            visible = [column]
            self.column_visible_var.set(True)
        self.settings.visible_game_columns = visible
        self.apply_game_columns()
        self.save_settings_from_ui(log=False)

    def move_selected_column(self, direction: int) -> None:
        self.move_column_by_id(self.selected_column_id(), direction)

    def move_column_by_id(self, column: str, direction: int) -> None:
        if column not in GAME_COLUMNS:
            return
        order = self.normalized_column_order()
        index = order.index(column)
        new_index = max(0, min(len(order) - 1, index + direction))
        if new_index == index:
            return
        order.pop(index)
        order.insert(new_index, column)
        self.settings.game_column_order = order
        self.apply_game_columns()
        self.save_settings_from_ui(log=False)

    def show_column_context_menu(self, event: tk.Event[Any]) -> None:
        if self.games_tree.identify_region(event.x, event.y) != "heading":
            return
        display_columns = list(self.games_tree["displaycolumns"])
        clicked_column = "title"
        identified = self.games_tree.identify_column(event.x)
        if identified.startswith("#"):
            try:
                index = int(identified[1:]) - 1
                if 0 <= index < len(display_columns):
                    clicked_column = display_columns[index]
            except ValueError:
                pass
        palette = self.palette()
        menu = tk.Menu(
            self,
            tearoff=False,
            bg=palette["panel"],
            fg=palette["text"],
            activebackground=palette["selected"],
            activeforeground=palette["selected_text"],
        )
        self.column_menu_vars = []
        menu.add_command(label=f"Sort by {GAME_COLUMN_LABELS[clicked_column]}", command=lambda: self.sort_games_by_column(clicked_column))
        menu.add_separator()
        for column in GAME_COLUMNS:
            visible = tk.BooleanVar(value=column in self.normalized_visible_columns())
            self.column_menu_vars.append(visible)
            menu.add_checkbutton(
                label=GAME_COLUMN_LABELS[column],
                variable=visible,
                command=lambda c=column, v=visible: self.toggle_column_by_id(c, v.get()),
            )
        menu.add_separator()
        menu.add_command(label="Move left", command=lambda: self.move_column_by_id(clicked_column, -1))
        menu.add_command(label="Move right", command=lambda: self.move_column_by_id(clicked_column, 1))
        menu.tk_popup(event.x_root, event.y_root)

    def _build_detail(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)
        notebook = ttk.Notebook(parent)
        notebook.grid(row=0, column=0, sticky="nsew")

        review = ttk.Frame(notebook, padding=10)
        artwork = ttk.Frame(notebook, padding=10)
        notebook.add(review, text="Shortcut")
        notebook.add(artwork, text="Artwork")
        self._build_review_tab(review)
        self._build_artwork_tab(artwork)

    def _build_review_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(1, weight=1)
        parent.rowconfigure(5, weight=1)
        labels = [
            ("Title", "title_entry"),
            ("Launch options", "launch_entry"),
            ("Release", "year_entry"),
        ]
        self.detail_vars: dict[str, tk.StringVar] = {}
        self.detail_entries: dict[str, ttk.Entry] = {}
        for row, (label, name) in enumerate(labels):
            ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=3, padx=(0, 8))
            var = tk.StringVar()
            var.trace_add("write", lambda *_args: self.on_detail_modified())
            self.detail_vars[name] = var
            entry = ttk.Entry(parent, textvariable=var)
            entry.grid(row=row, column=1, sticky="ew", pady=3)
            self.detail_entries[name] = entry
        ttk.Label(parent, text="Executable").grid(row=3, column=0, sticky="w", pady=3, padx=(0, 8))
        exe_row = ttk.Frame(parent)
        exe_row.grid(row=3, column=1, sticky="ew", pady=3)
        exe_row.columnconfigure(0, weight=1)
        self.selected_exe_var = tk.StringVar()
        self.selected_exe_entry = ttk.Entry(exe_row, textvariable=self.selected_exe_var, state="readonly")
        self.selected_exe_entry.grid(row=0, column=0, sticky="ew")
        ttk.Button(exe_row, text="Use Highlighted", command=self.use_selected_candidate, width=14).grid(row=0, column=1, padx=(6, 0))
        ttk.Button(exe_row, text="Browse EXE", command=self.choose_manual_exe, width=11).grid(row=0, column=2, padx=(6, 0))
        self.save_edits_button = ttk.Button(parent, text="Save Edits", command=self.save_current_detail)
        self.save_edits_button.grid(row=4, column=1, sticky="e", pady=(2, 6))

        hidden_detail_state = ttk.Frame(parent)
        self.description_text = tk.Text(hidden_detail_state, height=1, wrap="word", font=("Segoe UI", 9), relief="flat", borderwidth=0)
        self.description_text.bind("<<Modified>>", self.on_notes_modified)
        self.reason_text = tk.Text(hidden_detail_state, height=1, wrap="word", font=("Segoe UI", 9), relief="flat", borderwidth=0)

        candidate_frame = ttk.LabelFrame(parent, text="Executable Candidates", padding=8)
        candidate_frame.grid(row=5, column=0, columnspan=2, sticky="nsew")
        candidate_frame.columnconfigure(0, weight=1)
        candidate_frame.rowconfigure(0, weight=1)
        self.candidate_tree = ttk.Treeview(candidate_frame, columns=("score", "path"), show="headings", height=12)
        self.candidate_tree.heading("score", text="Score")
        self.candidate_tree.heading("path", text="Path")
        self.candidate_tree.column("score", width=62, minwidth=50)
        self.candidate_tree.column("path", width=620)
        self.candidate_tree.grid(row=0, column=0, sticky="nsew")
        self.candidate_tree.bind("<Double-1>", self.use_selected_candidate)
        candidate_scroll = ttk.Scrollbar(candidate_frame, orient=tk.VERTICAL, command=self.candidate_tree.yview)
        candidate_scroll.grid(row=0, column=1, sticky="ns")
        candidate_xscroll = ttk.Scrollbar(candidate_frame, orient=tk.HORIZONTAL, command=self.candidate_tree.xview)
        candidate_xscroll.grid(row=1, column=0, sticky="ew")
        self.candidate_tree.configure(yscrollcommand=candidate_scroll.set, xscrollcommand=candidate_xscroll.set)
        candidate_buttons = ttk.Frame(candidate_frame)
        candidate_buttons.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        candidate_buttons.columnconfigure(1, weight=1)
        ttk.Button(candidate_buttons, text="Use Highlighted", command=self.use_selected_candidate).grid(row=0, column=0, sticky="w")
        ttk.Button(candidate_buttons, text="Choose Different EXE", command=self.choose_manual_exe).grid(row=0, column=2, sticky="e")

    def _build_artwork_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)

        search = ttk.LabelFrame(parent, text="Artwork Search", padding=8)
        search.grid(row=0, column=0, sticky="ew")
        search.columnconfigure(1, weight=1)
        ttk.Label(search, text="Type").grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.artwork_kind_combo = ttk.Combobox(
            search,
            textvariable=self.artwork_kind_var,
            values=["all", "grid", "wide", "hero", "logo", "icon"],
            state="readonly",
            width=10,
        )
        self.artwork_kind_combo.grid(row=0, column=1, sticky="w")
        self.artwork_kind_combo.bind("<<ComboboxSelected>>", lambda _event: self.display_cached_artwork_kind())
        ToolTip(self.artwork_kind_combo, "Show all collected artwork, or filter to grid, hero, logo, or icon results from the same saved game search.")
        ttk.Label(search, text="Search").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=(6, 0))
        artwork_search_entry = ttk.Entry(search, textvariable=self.artwork_search_var)
        artwork_search_entry.grid(row=1, column=1, sticky="ew", pady=(6, 0))
        artwork_search_entry.bind("<Return>", lambda _event: self.find_art_for_current(force_refresh=True))
        ToolTip(artwork_search_entry, "Type the exact game title to search for this selected row. Press Enter or Search Art.")
        search_button = ttk.Button(search, text="Search Art", command=lambda: self.find_art_for_current(force_refresh=True))
        search_button.grid(row=1, column=2, padx=(8, 0), pady=(6, 0))
        ToolTip(search_button, "Rerun artwork search for this game and refresh the collected artwork grid.")

        self.artwork_tree = ttk.Treeview(parent, columns=("kind", "dimensions", "score", "style", "url"), show="headings", height=7)
        for column, width in [("kind", 58), ("dimensions", 94), ("score", 64), ("style", 90), ("url", 360)]:
            self.artwork_tree.heading(column, text=column.title())
            self.artwork_tree.column(column, width=width)
        self.artwork_tree.bind("<Double-1>", self.use_highlighted_artwork)

        results_frame = ttk.LabelFrame(parent, text="Collected Artwork Grid", padding=8)
        results_frame.grid(row=1, column=0, sticky="nsew", pady=(8, 8))
        results_frame.columnconfigure(0, weight=1)
        results_frame.rowconfigure(0, weight=1)
        self.artwork_canvas = tk.Canvas(results_frame, height=260, bg=self.palette()["canvas"], highlightthickness=0)
        self.artwork_canvas.grid(row=0, column=0, sticky="nsew")
        artwork_scroll = ttk.Scrollbar(results_frame, orient=tk.VERTICAL, command=self.artwork_canvas.yview)
        artwork_scroll.grid(row=0, column=1, sticky="ns")
        self.artwork_canvas.configure(yscrollcommand=artwork_scroll.set)
        self.artwork_thumb_frame = ttk.Frame(self.artwork_canvas)
        self.artwork_canvas_window = self.artwork_canvas.create_window((0, 0), window=self.artwork_thumb_frame, anchor="nw")
        self.artwork_thumb_frame.bind("<Configure>", lambda _event: self.artwork_canvas.configure(scrollregion=self.artwork_canvas.bbox("all")))
        self.artwork_canvas.bind("<Configure>", self.on_artwork_canvas_configure)

        preview_frame = ttk.LabelFrame(parent, text="Selected Artwork Preview", padding=8)
        preview_frame.grid(row=2, column=0, sticky="ew")
        preview_frame.rowconfigure(0, weight=1)
        for col in range(5):
            preview_frame.columnconfigure(col, weight=1)
        self.preview_labels: dict[str, tk.Label] = {}
        self.preview_boxes: dict[str, tk.Frame] = {}
        for col, kind in enumerate(["grid", "wide", "hero", "logo", "icon"]):
            frame = ttk.Frame(preview_frame)
            frame.grid(row=0, column=col, padx=5, sticky="n")
            ttk.Label(frame, text=kind.title()).grid(row=0, column=0, pady=(0, 4))
            box = tk.Frame(
                frame,
                width=176,
                height=132,
                bg=self.palette()["canvas"],
                highlightthickness=1,
                highlightbackground=self.palette()["border"],
                cursor="hand2",
            )
            box.grid(row=1, column=0)
            box.grid_propagate(False)
            label = tk.Label(
                box,
                text="No image",
                anchor=tk.CENTER,
                justify=tk.CENTER,
                bg=self.palette()["canvas"],
                fg=self.palette()["muted"],
                wraplength=154,
                font=("Segoe UI", 8),
                cursor="hand2",
            )
            label.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
            box.bind("<Double-1>", lambda _event, artwork_kind=kind: self.open_selected_artwork_preview(artwork_kind))
            label.bind("<Double-1>", lambda _event, artwork_kind=kind: self.open_selected_artwork_preview(artwork_kind))
            box.bind("<Button-3>", lambda event, artwork_kind=kind: self.show_artwork_preview_menu(event, artwork_kind))
            label.bind("<Button-3>", lambda event, artwork_kind=kind: self.show_artwork_preview_menu(event, artwork_kind))
            ToolTip(label, "Double-click to open a larger preview. Right-click for artwork options.")
            self.preview_boxes[kind] = box
            self.preview_labels[kind] = label


    def _load_initial_state(self) -> None:
        steam_path_text = self.steam_path_var.get().strip()
        sgdboop_path_text = self.sgdboop_path_var.get().strip()

        def task() -> tuple[Path | None, list[SteamProfile], Path | None]:
            steam_path = Path(steam_path_text) if steam_path_text else detect_steam_install()
            profiles: list[SteamProfile] = []
            if steam_path and is_valid_steam_path(steam_path):
                profiles = find_steam_profiles(steam_path)
            boop_path = None if sgdboop_path_text else detect_sgdboop()
            return steam_path, profiles, boop_path

        def done(result: tuple[Path | None, list[SteamProfile], Path | None]) -> None:
            steam_path, profiles, boop_path = result
            if steam_path:
                self.steam_path_var.set(normalize_windows_path_text(str(steam_path)))
                self.logger.info("Detected Steam at %s", steam_path)
            self.set_profiles(profiles)
            if boop_path:
                self.sgdboop_path_var.set(str(boop_path))
                self.logger.info("Detected SGDBoop at %s", boop_path)
            self.save_settings_from_ui(log=False)

        self.run_background("Detecting Steam setup", task, done)

    def _poll_logs(self) -> None:
        callbacks_processed = 0
        while callbacks_processed < 35:
            try:
                callback = self.ui_queue.get_nowait()
            except queue.Empty:
                break
            try:
                callback()
            except Exception as exc:
                self.logger.exception("UI callback failed: %s", exc)
            callbacks_processed += 1
        logs_processed = 0
        while logs_processed < 120:
            try:
                line = self.log_queue.get_nowait()
            except queue.Empty:
                break
            self.log_text.configure(state="normal")
            self.log_text.insert(tk.END, line + "\n")
            self.log_text.see(tk.END)
            logs_processed += 1
        self.after(120, self._poll_logs)

    def post_ui(self, callback: Callable[[], None]) -> None:
        self.ui_queue.put(callback)

    def set_task_progress(self, message: str, value: int | None = None, maximum: int | None = None) -> None:
        def apply() -> None:
            self.status_var.set(message)
            if maximum is not None:
                self.progress.stop()
                self.progress.configure(mode="determinate", maximum=max(maximum, 1))
            if value is not None:
                self.progress["value"] = value

        self.post_ui(apply)

    def raise_if_cancelled(self) -> None:
        if self.cancel_event.is_set() or any(event.is_set() for event in tuple(self.cancel_events)):
            raise JobCancelled("Cancelled by user.")

    def cancel_current_job(self) -> None:
        active_controller_jobs = [
            job_id
            for job_id in (self.source_scan_state.job_ids | self.persistent_artwork_job_ids)
            if (record := self.library_controller.job_queue.get(job_id)) is not None
            and record.state not in TERMINAL_JOB_STATES
        ]
        if not self.active_job_count and not active_controller_jobs:
            return
        for event in tuple(self.cancel_events):
            event.set()
        for job_id in active_controller_jobs:
            self.library_controller.job_queue.cancel(job_id)
        self.status_var.set("Cancel requested. Stopping at the next safe checkpoint...")
        self.logger.info("Cancel requested by user.")
        if hasattr(self, "cancel_button"):
            self.cancel_button.configure(state=tk.DISABLED)

    def set_busy_controls(self, busy: bool | None = None) -> None:
        controller_active = any(
            (record := self.library_controller.job_queue.get(job_id)) is not None
            and record.state not in TERMINAL_JOB_STATES
            for job_id in (self.source_scan_state.job_ids | self.persistent_artwork_job_ids)
        )
        active = (self.active_job_count > 0 or controller_active) if busy is None else busy
        if hasattr(self, "cancel_button"):
            self.cancel_button.configure(state=tk.NORMAL if active else tk.DISABLED)

    def run_background(
        self,
        label: str,
        task: Callable[[], Any],
        on_success: Callable[[Any], None] | None = None,
        *,
        exclusive: bool = False,
        show_error: bool = True,
    ) -> None:
        if self.exclusive_job_running or (exclusive and self.active_job_count):
            messagebox.showinfo(__app_name__, "A write or scan-safe task is still finishing. Let that finish first.")
            return
        cancel_event = threading.Event()
        self.cancel_event = cancel_event
        self.cancel_events.add(cancel_event)
        self.active_job_count += 1
        self.busy = True
        if exclusive:
            self.exclusive_job_running = True
        self.set_busy_controls()
        self.status_var.set(label)
        if self.active_job_count == 1:
            self.progress.start(12)

        def worker() -> None:
            try:
                result = task()
            except JobCancelled as exc:
                self.post_ui(lambda exc=exc: self._task_cancelled(label, exc, cancel_event, exclusive))
            except Exception as exc:
                self.post_ui(lambda exc=exc: self._task_failed(label, exc, cancel_event, exclusive, show_error))
            else:
                self.post_ui(lambda: self._task_done(label, result, on_success, cancel_event, exclusive))

        threading.Thread(target=worker, daemon=True).start()

    def _finish_background_job(self, cancel_event: threading.Event, exclusive: bool) -> None:
        self.cancel_events.discard(cancel_event)
        self.active_job_count = max(0, self.active_job_count - 1)
        self.busy = self.active_job_count > 0
        if exclusive:
            self.exclusive_job_running = False
        if not self.active_job_count:
            self.progress.stop()
            self.progress.configure(mode="indeterminate", value=0)
            self.status_var.set("Ready.")
        self.set_busy_controls()

    def _task_cancelled(self, label: str, exc: JobCancelled, cancel_event: threading.Event, exclusive: bool) -> None:
        self._finish_background_job(cancel_event, exclusive)
        self.status_var.set("Cancelled." if not self.active_job_count else f"Cancelled. {self.active_job_count} background job(s) still running.")
        self.logger.info("%s cancelled: %s", label, exc)

    def _task_failed(self, label: str, exc: Exception, cancel_event: threading.Event, exclusive: bool, show_error: bool) -> None:
        self._finish_background_job(cancel_event, exclusive)
        self.logger.exception("%s failed: %s", label, exc)
        if show_error:
            messagebox.showerror(__app_name__, f"{label} failed:\n\n{exc}")

    def _task_done(
        self,
        label: str,
        result: Any,
        on_success: Callable[[Any], None] | None,
        cancel_event: threading.Event,
        exclusive: bool,
    ) -> None:
        self._finish_background_job(cancel_event, exclusive)
        if on_success:
            on_success(result)
        self.logger.info("%s complete.", label)

    def detect_steam(self) -> None:
        def task() -> tuple[Path | None, list[SteamProfile]]:
            detected = detect_steam_install()
            profiles = find_steam_profiles(detected) if detected and is_valid_steam_path(detected) else []
            return detected, profiles

        def done(result: tuple[Path | None, list[SteamProfile]]) -> None:
            detected, profiles = result
            if not detected:
                messagebox.showwarning(__app_name__, "Steam was not found automatically. Choose the Steam folder manually.")
                return
            self.steam_path_var.set(normalize_windows_path_text(str(detected)))
            self.logger.info("Detected Steam at %s", detected)
            self.set_profiles(profiles)
            self.save_settings_from_ui()

        self.run_background("Detecting Steam", task, done)

    def browse_steam(self) -> None:
        initial = self.steam_path_var.get() or str(Path.home())
        folder = filedialog.askdirectory(title="Choose Steam installation folder", initialdir=initial)
        if folder:
            self.steam_path_var.set(normalize_windows_path_text(folder))
            self.refresh_profiles()
            self.save_settings_from_ui()

    def browse_collection(self) -> None:
        initial = self.collection_path_var.get() or str(Path.home())
        folder = filedialog.askdirectory(title="Choose non-Steam game collection folder", initialdir=initial)
        if folder:
            self.collection_path_var.set(normalize_windows_path_text(folder))
            self.save_settings_from_ui()

    def refresh_profiles(self) -> None:
        steam_path_text = self.steam_path_var.get().strip()
        if not steam_path_text:
            self.set_profiles([])
            return
        steam_path = Path(steam_path_text)
        if not is_valid_steam_path(steam_path):
            self.logger.warning("Steam path does not look valid yet: %s", steam_path)
            self.set_profiles([])
            return
        self.set_profiles(find_steam_profiles(steam_path))

    def set_profiles(self, profiles: list[SteamProfile]) -> None:
        self.profiles = profiles
        labels = [profile.display_name for profile in self.profiles]
        selected_index = 0
        if self.settings.active_user_id:
            for index, profile in enumerate(self.profiles):
                if profile.user_id == self.settings.active_user_id:
                    selected_index = index
                    break
        if labels:
            self.profile_var.set(labels[selected_index])
            self.logger.info("Detected %s Steam profile(s). Active: %s", len(labels), labels[selected_index])
        else:
            self.profile_var.set("")
        self.rebuild_profile_menu()
        self.update_profile_status()

    def current_profile(self) -> SteamProfile | None:
        current = self.profile_var.get()
        for profile in self.profiles:
            if profile.display_name == current:
                return profile
        if self.profiles:
            return self.profiles[0]
        return None

    def save_settings_from_ui(self, log: bool = True) -> None:
        normalized_steam = normalize_windows_path_text(self.steam_path_var.get())
        normalized_collection = normalize_windows_path_text(self.collection_path_var.get())
        self.steam_path_var.set(normalized_steam)
        self.collection_path_var.set(normalized_collection)
        self.settings.steam_path = normalized_steam
        self.settings.collection_root = normalized_collection
        self.settings.steamgriddb_api_key = self.api_key_var.get().strip()
        self.settings.rawg_api_key = self.rawg_api_key_var.get().strip()
        self.settings.sgdboop_path = self.sgdboop_path_var.get().strip()
        self.settings.update_existing_shortcuts = self.update_existing_var.get()
        self.settings.default_tags = [tag.strip() for tag in self.default_tags_var.get().split(",") if tag.strip()]
        self.settings.steam_play_compat_tool = self.selected_compat_tool_name()
        self.settings.theme_name = self.normalized_theme_name(self.theme_var.get())
        self.settings.dark_mode = self.theme_is_dark(self.settings.theme_name)
        self.settings.view_filter = self.view_filter_var.get() if self.view_filter_var.get() in VIEW_FILTERS else "All"
        self.settings.sort_preset = self.sort_preset_var.get() if self.sort_preset_var.get() in SORT_PRESETS else "Title A-Z"
        try:
            self.settings.artwork_preview_limit = max(4, min(80, int(self.preview_limit_var.get())))
        except (tk.TclError, ValueError):
            self.settings.artwork_preview_limit = 16
            self.preview_limit_var.set(16)
        self.settings.artwork_sources = {key: var.get() for key, var in self.artwork_source_vars.items()}
        self.settings.metadata_sources = {key: var.get() for key, var in self.metadata_source_vars.items()}
        self.settings.visible_game_columns = self.normalized_visible_columns()
        self.settings.game_column_order = self.normalized_column_order()
        profile = self.current_profile()
        self.settings.active_user_id = profile.user_id if profile else ""
        self.settings_store.save(self.settings)
        if log:
            self.logger.info("Settings saved to %s", self.settings_store.settings_path)

    def open_external_url(self, url: str) -> None:
        opened = False
        try:
            if sys.platform.startswith("linux"):
                for command in ("xdg-open", "gio"):
                    executable = shutil.which(command)
                    if not executable:
                        continue
                    args = [executable, "open", url] if command == "gio" else [executable, url]
                    subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    opened = True
                    break
            if not opened:
                opened = webbrowser.open(url, new=2)
        except Exception as exc:
            self.logger.warning("Could not open browser link %s: %s", url, exc)
            self.copy_link_to_clipboard(url)
            messagebox.showerror(__app_name__, f"Could not open the browser link.\n\nThe link was copied instead:\n{url}")
            return
        if not opened:
            self.logger.warning("Browser did not accept link: %s", url)
            self.copy_link_to_clipboard(url)
            messagebox.showerror(__app_name__, f"Could not open the browser link.\n\nThe link was copied instead:\n{url}")

    def open_filesystem_path(self, path_text: str) -> None:
        path = Path(path_text).expanduser()
        if not path.exists():
            messagebox.showerror(__app_name__, f"Path does not exist:\n\n{path}")
            return
        try:
            if os.name == "nt":
                os.startfile(path)  # type: ignore[attr-defined]
                return
            opener = shutil.which("xdg-open") or shutil.which("gio")
            if opener is None:
                raise OSError("Could not find xdg-open or gio.")
            command = [opener, "open", str(path)] if Path(opener).name == "gio" else [opener, str(path)]
            subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        except OSError as exc:
            self.logger.warning("Could not open filesystem path %s: %s", path, exc)
            messagebox.showerror(__app_name__, f"Could not open path:\n\n{exc}")

    def show_transaction_history(self) -> None:
        view = self.transaction_history_controller.history_view()
        window = tk.Toplevel(self)
        window.title("Backups")
        window.geometry("1080x460")
        window.transient(self)
        window.columnconfigure(0, weight=1)
        window.rowconfigure(1, weight=1)

        ttk.Label(window, text=view.summary, style="Subtle.TLabel").grid(
            row=0,
            column=0,
            sticky="ew",
            padx=10,
            pady=(10, 6),
        )

        tree = ttk.Treeview(
            window,
            columns=("updated", "status", "target", "restore", "id", "error"),
            show="headings",
            selectmode="browse",
        )
        tree.heading("updated", text="Updated")
        tree.heading("status", text="Status")
        tree.heading("target", text="Target")
        tree.heading("restore", text="Restore")
        tree.heading("id", text="Transaction")
        tree.heading("error", text="Error")
        tree.column("updated", width=160, anchor=tk.W)
        tree.column("status", width=100, anchor=tk.W)
        tree.column("target", width=180, anchor=tk.W)
        tree.column("restore", width=140, anchor=tk.W)
        tree.column("id", width=180, anchor=tk.W)
        tree.column("error", width=300, anchor=tk.W)
        tree.grid(row=1, column=0, sticky="nsew", padx=10)
        scrollbar = ttk.Scrollbar(window, orient=tk.VERTICAL, command=tree.yview)
        scrollbar.grid(row=1, column=1, sticky="ns", padx=(0, 10))
        tree.configure(yscrollcommand=scrollbar.set)

        rows_by_id = {str(index): row for index, row in enumerate(view.rows)}
        for row_id, row in rows_by_id.items():
            tree.insert(
                "",
                tk.END,
                iid=row_id,
                values=(
                    row.updated_at,
                    row.status,
                    row.target,
                    row.restore_state,
                    row.transaction_id,
                    row.error,
                ),
            )
        if not rows_by_id:
            tree.insert("", tk.END, values=("", "", "", "", "", "No transaction history found."))

        detail = ttk.Label(window, text="", style="Subtle.TLabel", justify=tk.LEFT, wraplength=1040)
        detail.grid(row=2, column=0, columnspan=2, sticky="ew", padx=10, pady=(8, 0))

        def selected_row() -> Any:
            selection = tree.selection()
            return rows_by_id.get(selection[0]) if selection else None

        def update_detail(_event: tk.Event[Any] | None = None) -> None:
            row = selected_row()
            if row is None:
                detail.configure(text="")
                return
            detail.configure(
                text=(
                    f"Backup: {row.backup_path or 'none'}\n"
                    f"Manifest: {row.manifest_path}"
                )
            )

        def open_backup() -> None:
            row = selected_row()
            target = self.transaction_history_controller.backup_folder_target(row) if row is not None else None
            if target is None:
                messagebox.showinfo(__app_name__, "Selected transaction has no restore backup.")
                return
            self.open_filesystem_path(str(target.path))

        def open_manifest() -> None:
            row = selected_row()
            if row is None:
                return
            target = self.transaction_history_controller.manifest_target(row)
            self.open_filesystem_path(str(target.path))

        tree.bind("<<TreeviewSelect>>", update_detail)
        if rows_by_id:
            tree.selection_set("0")
            tree.focus("0")
            update_detail()

        buttons = ttk.Frame(window, padding=10)
        buttons.grid(row=3, column=0, columnspan=2, sticky="ew")
        buttons.columnconfigure(0, weight=1)
        ttk.Button(buttons, text="Open Backup Folder", command=open_backup).grid(row=0, column=1, padx=(0, 8))
        ttk.Button(buttons, text="Open Manifest", command=open_manifest).grid(row=0, column=2, padx=(0, 8))
        ttk.Button(buttons, text="Close", command=window.destroy).grid(row=0, column=3)
        self._theme_child(window, self.palette())
        self.status_var.set(view.summary)

    def copy_link_to_clipboard(self, url: str) -> None:
        try:
            self.clipboard_clear()
            self.clipboard_append(url)
        except tk.TclError:
            self.logger.warning("Could not copy browser link to clipboard: %s", url)

    def detect_sgdboop(self) -> None:
        def done(detected: Path | None) -> None:
            if detected:
                self.sgdboop_path_var.set(str(detected))
                self.save_settings_from_ui()
                self.logger.info("Detected SGDBoop at %s", detected)
                return
            path = filedialog.askopenfilename(
                title="Choose SGDBoop",
                filetypes=[("SGDBoop", "SGDBoop.exe sgdboop SGDBoop"), ("Executables", "*.exe"), ("All files", "*.*")],
            )
            if path:
                self.sgdboop_path_var.set(path)
                self.save_settings_from_ui()

        self.run_background("Detecting SGDBoop", detect_sgdboop, done)

    def load_persistent_library(self) -> None:
        self.save_current_detail()
        snapshot = self.library_controller.refresh()
        self.apply_library_snapshot(snapshot)

    def apply_library_snapshot(self, snapshot: Any) -> None:
        games = games_from_library_snapshot(snapshot)
        self.replace_live_scan_games(
            games,
            f"Loaded {len(games)} stored library item(s).",
        )

    def scan_persistent_sources(self) -> None:
        self.save_current_detail()
        self.save_settings_from_ui(log=False)
        steam_text = self.steam_path_var.get().strip()
        root_text = self.collection_path_var.get().strip()
        adapters = self.source_scan_state.configured_adapters(
            steam_path=steam_text or None,
            collection_root=root_text or None,
            include_epic=True,
        )
        if not adapters:
            messagebox.showwarning(__app_name__, "No persistent source scans are available.")
            return
        for queued in self.source_scan_state.queue_adapters(adapters):
            self.logger.info("Queued persistent %s source scan: %s", queued.source, queued.job_id)
        self.status_var.set(self.source_scan_state.progress_summary())
        self.set_busy_controls()
        self._schedule_library_controller_poll()

    def scan_selected_persistent_sources(self) -> None:
        self.save_current_detail()
        self.save_settings_from_ui(log=False)
        sources = set(self.library_controller.selected_sources())
        if not sources:
            messagebox.showinfo(__app_name__, "Select stored library rows before refreshing selected sources.")
            return
        steam_text = self.steam_path_var.get().strip()
        root_text = self.collection_path_var.get().strip()
        plan = self.source_scan_state.selected_source_plan(
            sources,
            steam_path=steam_text or None,
            collection_root=root_text or None,
            include_epic=True,
        )
        if plan.unavailable_sources:
            self.logger.info(
                "Selected source scan skipped unavailable source(s): %s",
                ", ".join(plan.unavailable_sources),
            )
        if not plan.adapters:
            messagebox.showinfo(
                __app_name__,
                "Selected rows need a configured Steam folder or game collection folder before their source can be refreshed.",
            )
            return
        for queued in self.source_scan_state.queue_adapters(plan.adapters):
            self.logger.info("Queued selected persistent %s source scan: %s", queued.source, queued.job_id)
        self.status_var.set(self.source_scan_state.progress_summary())
        self.set_busy_controls()
        self._schedule_library_controller_poll()

    def queue_persistent_artwork_searches(self) -> None:
        self.save_settings_from_ui(log=False)
        item_ids = self.selected_persistent_item_ids()
        if not item_ids:
            messagebox.showinfo(__app_name__, "Select stored library rows before planning artwork.")
            return
        self._queue_persistent_artwork_searches_for_ids(item_ids, "persistent artwork plan")

    def _queue_persistent_artwork_searches_for_ids(self, item_ids: tuple[str, ...], status_label: str) -> None:
        client = self.make_sgdb_client()
        enabled_sources = self.active_artwork_sources()
        self.show_missing_artwork_api_prompt(enabled_sources)
        rawg_api_key = self.rawg_api_key_var.get().strip()
        cache_dir = Path(self.settings.cache_dir)
        provider_service = ArtworkProviderSearchService(self.logger)
        game_by_item_id = library_games_by_item_id(self.games)

        def provider_searcher(item, requested_slots, token, report_progress):
            token.raise_if_cancelled()
            game = game_by_item_id.get(item.item_id)
            if game is None:
                return validated_artwork_assets_to_search_outcome(
                    {},
                    requested_slots,
                    cache_dir=cache_dir,
                    provider="real-providers",
                    identity_score=0,
                    set_coherence_score=0,
                    reasons=("Stored row is no longer visible in the production table.",),
                    logger=self.logger,
                )
            report_progress(0.15, f"Searching providers for {item.title}")
            term = game.source_title or game.title or game.display_title
            assets_by_kind = provider_service.collect_assets(
                game,
                term,
                client,
                use_sgdb_cache=True,
                enabled_sources=enabled_sources,
                rawg_api_key=rawg_api_key,
                allow_metadata_updates=False,
                cancellation_checkpoint=token.raise_if_cancelled,
            )
            token.raise_if_cancelled()
            report_progress(0.65, f"Validating artwork candidates for {item.title}")
            return validated_artwork_assets_to_search_outcome(
                assets_by_kind,
                requested_slots,
                cache_dir=cache_dir,
                provider="real-providers",
                identity_score=70,
                set_coherence_score=60,
                reasons=("Provider candidates are decoded and cached; identity scoring still requires review.",),
                logger=self.logger,
            )

        submission = BulkArtworkCoordinator(self.library_controller.job_queue).submit_selected(
            self.library_controller.selection,
            item_ids,
            self.library_controller.bulk_artwork_items(),
            provider_searcher,
            mode=ArtworkSearchMode.ALL_UNLOCKED,
        )
        if not submission.jobs:
            messagebox.showinfo(__app_name__, "No selected persistent artwork rows were available to queue.")
            return
        for job in submission.jobs:
            self.persistent_artwork_job_ids.add(job.job_id)
            self.set_persistent_artwork_status(job.item_id, artwork_queue_item_status(status_label))
        self.status_var.set(artwork_queue_submission_message(len(submission.jobs), status_label))
        self.set_busy_controls()
        self._schedule_library_controller_poll()

    def retry_reviewed_source_scans(self) -> None:
        if not self.source_scan_state.retry_job_ids:
            messagebox.showinfo(__app_name__, "No reviewed or failed source refresh jobs are available to retry.")
            return
        try:
            queued = self.source_scan_state.retry_available()
        except Exception as exc:
            self.logger.warning("Could not retry source scans: %s", exc)
            queued = ()
        for scan in queued:
            self.logger.info("Retried persistent source scan: %s", scan.job_id)
        if not queued:
            messagebox.showinfo(__app_name__, "No source refresh jobs could be retried.")
            return
        self.status_var.set(self.source_scan_state.progress_summary())
        self.set_busy_controls()
        self._schedule_library_controller_poll()

    def clear_reviewed_source_scans(self) -> None:
        count = self.source_scan_state.clear_retry_jobs()
        self.status_var.set(source_review_clear_message(count))
        self.logger.info("Cleared %s source review job(s).", count)

    def selected_persistent_item_ids(self) -> tuple[str, ...]:
        return selected_visible_library_item_ids(
            self.games,
            self.displayed_game_indices,
            self.library_controller.snapshot().selected_ids,
        )

    def show_selected_artwork_decisions(self) -> None:
        item_ids = self.selected_persistent_item_ids()
        if not item_ids:
            messagebox.showinfo(__app_name__, "Select stored library rows before reviewing artwork decisions.")
            return
        summary = self.library_controller.artwork_decision_summary(item_ids)
        review_summary = build_artwork_review_summary(item_ids, self.persistent_artwork_review_results)
        row_titles = {row.item_id: row.title for row in self.library_controller.snapshot().rows}
        review_rows = build_artwork_review_rows(
            item_ids,
            row_titles,
            self.persistent_artwork_review_results,
        )
        window = tk.Toplevel(self)
        window.title("Artwork Decisions")
        window.geometry("1080x560")
        window.transient(self)
        window.columnconfigure(0, weight=1)
        window.columnconfigure(1, weight=0)
        window.columnconfigure(2, weight=0)
        window.rowconfigure(1, weight=1)

        ttk.Label(
            window,
            text=(
                f"Selected rows: {summary.item_count}    "
                f"Accepted/locked slots: {summary.locked_slots}    "
                f"Rejected candidates: {summary.rejected_matches}    "
                f"Pending review slots: {review_summary.pending_slot_count}"
            ),
            style="Subtle.TLabel",
        ).grid(row=0, column=0, columnspan=3, sticky="ew", padx=10, pady=(10, 6))

        tree = ttk.Treeview(window, columns=("item", "slot", "candidate", "size", "path"), show="headings")
        tree.heading("item", text="Item")
        tree.heading("slot", text="Slot")
        tree.heading("candidate", text="Candidate")
        tree.heading("size", text="Size")
        tree.heading("path", text="Validated File")
        tree.column("item", width=220, anchor=tk.W)
        tree.column("slot", width=80, anchor=tk.W)
        tree.column("candidate", width=180, anchor=tk.W)
        tree.column("size", width=84, anchor=tk.W)
        tree.column("path", width=280, anchor=tk.W)
        tree.grid(row=1, column=0, sticky="nsew", padx=10)
        scrollbar = ttk.Scrollbar(window, orient=tk.VERTICAL, command=tree.yview)
        scrollbar.grid(row=1, column=1, sticky="ns", padx=(0, 10))
        tree.configure(yscrollcommand=scrollbar.set)

        preview = ttk.Frame(window, padding=(0, 0, 10, 0))
        preview.grid(row=1, column=2, sticky="nsew")
        preview.rowconfigure(0, weight=1)
        image_label = tk.Label(
            preview,
            width=280,
            height=180,
            bg=self.palette()["panel"],
            fg=self.palette()["text"],
            text="Select slot",
            anchor=tk.CENTER,
        )
        image_label.grid(row=0, column=0, sticky="nsew")
        detail_label = ttk.Label(preview, text="", style="Subtle.TLabel", justify=tk.LEFT, wraplength=280)
        detail_label.grid(row=1, column=0, sticky="ew", pady=(8, 0))

        review_row_by_id: dict[str, ArtworkReviewRow] = {}
        preview_images: list[Any] = []
        for index, row in enumerate(review_rows):
            row_id = str(index)
            review_row_by_id[row_id] = row
            tree.insert(
                "",
                tk.END,
                iid=row_id,
                values=(
                    row.title,
                    row.slot,
                    row.candidate_id,
                    row.dimensions_label,
                    row.path,
                ),
            )
        if not review_rows:
            tree.insert(
                "",
                tk.END,
                values=("(none)", "", "", "", "No pending artwork review candidates for selected rows."),
            )

        def update_preview(_event: tk.Event[Any] | None = None) -> None:
            selected = tree.selection()
            row = review_row_by_id.get(selected[0]) if selected else None
            if row is None:
                image_label.configure(image="", text="Select slot")
                detail_label.configure(text="")
                return
            path = Path(row.path) if row.path else None
            image = self._load_preview_image(path, (280, 180)) if path and path.exists() else None
            if image is not None:
                preview_images[:] = [image]
                image_label.configure(image=image, text="")
            else:
                preview_images.clear()
                image_label.configure(image="", text="Preview unavailable")
            reasons = "; ".join(row.reasons)
            detail_label.configure(
                text=(
                    f"{row.title}\n"
                    f"{row.slot} / {row.provider or 'provider'} / {row.candidate_id}\n"
                    f"Identity {row.identity_score}    Set {row.set_coherence_score}\n"
                    f"{row.path}\n"
                    f"{reasons}"
                ).strip()
            )

        tree.bind("<<TreeviewSelect>>", update_preview)
        if review_rows:
            tree.selection_set("0")
            tree.focus("0")
            update_preview()

        buttons = ttk.Frame(window, padding=10)
        buttons.grid(row=2, column=0, columnspan=3, sticky="ew")
        buttons.columnconfigure(0, weight=1)
        ttk.Button(
            buttons,
            text="Accept Selected Review",
            command=lambda: (self.accept_selected_artwork_reviews(), window.destroy()),
        ).grid(row=0, column=1, padx=(0, 8))
        ttk.Button(
            buttons,
            text="Reject Selected Review",
            command=lambda: (self.reject_selected_artwork_reviews(), window.destroy()),
        ).grid(row=0, column=2, padx=(0, 8))
        ttk.Button(
            buttons,
            text="Skip Selected Review",
            command=lambda: (self.skip_selected_artwork_reviews(), window.destroy()),
        ).grid(row=0, column=3, padx=(0, 8))
        ttk.Button(
            buttons,
            text="Retry Selected Review",
            command=lambda: (self.retry_selected_artwork_reviews(), window.destroy()),
        ).grid(row=0, column=4, padx=(0, 8))
        ttk.Button(
            buttons,
            text="Clear Rejections",
            command=lambda: (self.clear_selected_artwork_rejections(), window.destroy()),
        ).grid(row=0, column=5, padx=(0, 8))
        ttk.Button(buttons, text="Close", command=window.destroy).grid(row=0, column=6)
        self._theme_child(window, self.palette())
        self.status_var.set(
            f"Artwork decisions: {summary.locked_slots} accepted/locked, {summary.rejected_matches} rejected, {review_summary.pending_slot_count} pending slot(s)."
        )

    def clear_selected_artwork_rejections(self) -> None:
        item_ids = self.selected_persistent_item_ids()
        if not item_ids:
            messagebox.showinfo(__app_name__, "Select stored library rows before clearing artwork rejections.")
            return
        cleared = self.library_controller.clear_rejected_artwork_matches(item_ids)
        self.status_var.set(artwork_rejection_clear_message(cleared))
        self.logger.info("Cleared %s rejected artwork candidate(s) for %s selected item(s).", cleared, len(item_ids))

    def _selected_artwork_review_results(self) -> list[dict[str, object]]:
        return [
            result
            for item_id in self.selected_persistent_item_ids()
            if (result := self.persistent_artwork_review_results.get(item_id)) is not None
        ]

    def accept_selected_artwork_reviews(self) -> None:
        results = self._selected_artwork_review_results()
        if not results:
            messagebox.showinfo(__app_name__, "No selected rows have pending artwork review results.")
            return
        accepted = 0
        for result in results:
            persistence = self.library_controller.accept_artwork_review_result(result)
            accepted += persistence.accepted
            self.persistent_artwork_review_results.pop(str(result.get("item_id") or ""), None)
        self.apply_library_snapshot(self.library_controller.snapshot())
        self.status_var.set(artwork_review_action_message("accept", accepted))
        self.logger.info("Accepted %s artwork candidate(s) from review.", accepted)

    def reject_selected_artwork_reviews(self) -> None:
        results = self._selected_artwork_review_results()
        if not results:
            messagebox.showinfo(__app_name__, "No selected rows have pending artwork review results.")
            return
        rejected = 0
        for result in results:
            persistence = self.library_controller.reject_artwork_review_result(result)
            rejected += persistence.rejected
            self.persistent_artwork_review_results.pop(str(result.get("item_id") or ""), None)
        self.status_var.set(artwork_review_action_message("reject", rejected))
        self.logger.info("Rejected %s artwork candidate(s) from review.", rejected)

    def skip_selected_artwork_reviews(self) -> None:
        results = self._selected_artwork_review_results()
        if not results:
            messagebox.showinfo(__app_name__, "No selected rows have pending artwork review results.")
            return
        skipped = 0
        for result in results:
            skipped += review_result_slot_count(result)
            self.persistent_artwork_review_results.pop(str(result.get("item_id") or ""), None)
        self.status_var.set(artwork_review_action_message("skip", skipped))
        self.logger.info("Skipped %s artwork review candidate(s).", skipped)

    def retry_selected_artwork_reviews(self) -> None:
        review_summary = build_artwork_review_summary(
            self.selected_persistent_item_ids(),
            self.persistent_artwork_review_results,
        )
        item_ids = review_summary.pending_item_ids
        if not item_ids:
            messagebox.showinfo(__app_name__, "No selected rows have pending artwork review results to retry.")
            return
        for item_id in item_ids:
            self.persistent_artwork_review_results.pop(item_id, None)
        self._queue_persistent_artwork_searches_for_ids(item_ids, "artwork review retry")
        self.logger.info("Retried %s selected artwork review item(s).", len(item_ids))

    def _schedule_library_controller_poll(self) -> None:
        if self.library_scan_poll_after_id is None:
            self.library_scan_poll_after_id = self.after(180, self._poll_library_controller_events)

    def _controller_scan_records(self) -> list[Any]:
        return list(self.source_scan_state.records())

    def _controller_scans_active(self) -> bool:
        return self.source_scan_state.active()

    def _poll_library_controller_events(self) -> None:
        self.library_scan_poll_after_id = None
        for controller_event in self.library_controller.poll_events():
            self._handle_library_controller_event(controller_event)
        if self._controller_scans_active() or self._persistent_artwork_jobs_active():
            self._schedule_library_controller_poll()
            self.set_busy_controls()
            return
        if self.source_scan_state.job_ids:
            self._finish_controller_source_scans()

    def _handle_library_controller_event(self, controller_event: LibraryControllerEvent) -> None:
        event = controller_event.event
        if event.job_id in self.persistent_artwork_job_ids:
            self._handle_persistent_artwork_event(controller_event)
            return
        update = self.source_scan_state.handle_event(controller_event)
        if not update.handled:
            return
        if update.terminal:
            if controller_event.snapshot is not None:
                self.apply_library_snapshot(controller_event.snapshot)
            self.logger.info(update.message)
            self.status_var.set(update.message)
            return
        if update.message:
            self.status_var.set(update.message)

    def _persistent_artwork_jobs_active(self) -> bool:
        return any(
            (record := self.library_controller.job_queue.get(job_id)) is not None
            and record.state not in TERMINAL_JOB_STATES
            for job_id in self.persistent_artwork_job_ids
        )

    def _handle_persistent_artwork_event(self, controller_event: LibraryControllerEvent) -> None:
        event = controller_event.event
        if event.state in TERMINAL_JOB_STATES:
            persistence = self.library_controller.persist_artwork_job_result(event.result)
            requested = ", ".join(event.result.get("requested_slots", [])) if event.result else ""
            decision = str(event.result.get("decision") or event.state.value) if event.result else event.state.value
            if decision == "review" and event.result:
                self.persistent_artwork_review_results[event.item_id] = dict(event.result)
            status = f"Artwork {decision}"
            if requested:
                status += f" ({requested})"
            if persistence.accepted or persistence.rejected:
                status += f"; saved {persistence.accepted} accepted/{persistence.rejected} rejected"
            self.set_persistent_artwork_status(event.item_id, status)
            self.logger.info("Persistent artwork job %s finished: %s", event.job_id, status)
            self.persistent_artwork_job_ids.discard(event.job_id)
            self.status_var.set(status)
            return
        self.set_persistent_artwork_status(event.item_id, event.message or event.state.value)
        self.status_var.set(event.message or event.state.value)

    def _finish_controller_source_scans(self) -> None:
        summary = self.source_scan_state.finish_summary()
        self.library_scan_poll_after_id = None
        self.set_busy_controls()
        self.progress.stop()
        self.progress.configure(mode="indeterminate", value=0)
        snapshot = self.library_controller.snapshot()
        self.apply_library_snapshot(snapshot)
        self.status_var.set(summary)
        self.logger.info(summary)

    def scan_all_libraries(self) -> None:
        self.save_current_detail()
        self.save_settings_from_ui(log=False)
        plan = build_combined_scan_plan(
            self.steam_path_var.get(),
            self.collection_path_var.get(),
            is_valid_steam_path=is_valid_steam_path,
        )
        if not plan.has_work:
            messagebox.showwarning(__app_name__, "Choose a valid Steam folder, a game collection folder, or both before scanning.")
            return
        profile = self.current_profile()
        self.replace_live_scan_games([], combined_scan_initial_message())

        def task() -> tuple[list[DetectedGame], int, int, int]:
            games: list[DetectedGame] = []
            steam_count = 0
            shortcut_count = 0
            folder_count = 0
            total_steps = plan.total_steps
            step = 0
            records = None
            if plan.steam_ready and plan.steam_path is not None:
                self.set_task_progress(combined_scan_steam_start_message(), step, total_steps)
                self.raise_if_cancelled()
                steam_games = scan_installed_steam_games(plan.steam_path)
                steam_count = len(steam_games)
                step += 1
                self.set_task_progress(combined_scan_steam_found_message(steam_count), step, total_steps)
                if profile:
                    try:
                        records = load_shortcuts(profile.shortcuts_path)
                        nonsteam_games = games_from_nonsteam_shortcuts(records)
                        shortcut_count = len(nonsteam_games)
                        steam_games = self.merge_game_lists(steam_games, nonsteam_games)
                        mark_existing_shortcuts(steam_games, records)
                        self.apply_existing_shortcut_choices(steam_games, records)
                        loaded = load_existing_artwork_for_games(steam_games, profile)
                        if loaded:
                            self.logger.info("Loaded %s existing Steam artwork file(s) while scanning Steam.", loaded)
                    except Exception as exc:
                        self.logger.warning("Could not read existing shortcuts/artwork while scanning Steam: %s", exc)
                games = self.merge_game_lists(games, steam_games)
                self.post_ui(lambda data=list(games), count=steam_count: self.replace_live_scan_games(data, steam_scan_live_found_message(count)))
                step += 1

            if plan.folder_ready and plan.collection_root is not None:
                self.set_task_progress(combined_scan_folder_start_message(), step, total_steps)
                scanner = GameScanner(
                    self.logger,
                    cancel_check=self.raise_if_cancelled,
                    progress_callback=lambda message: self.set_task_progress(message),
                    game_callback=lambda game: self.post_ui(lambda g=game: self.add_live_scan_game(g)),
                )
                folder_games = scanner.scan(plan.collection_root)
                folder_count = len(folder_games)
                self.raise_if_cancelled()
                step += 1
                self.set_task_progress(combined_scan_folder_cross_check_message(folder_count), step, total_steps)
                if profile:
                    try:
                        if records is None:
                            records = load_shortcuts(profile.shortcuts_path)
                        mark_existing_shortcuts(folder_games, records)
                        self.apply_existing_shortcut_choices(folder_games, records)
                        loaded = load_existing_artwork_for_games(folder_games, profile)
                        if loaded:
                            self.logger.info("Loaded %s existing Steam artwork file(s) for folder games.", loaded)
                    except Exception as exc:
                        self.logger.warning("Could not read existing shortcuts for folder duplicate detection: %s", exc)
                games = self.merge_game_lists(games, folder_games)
                step += 1

            counts = CombinedScanCounts(steam=steam_count, shortcuts=shortcut_count, folders=folder_count)
            self.set_task_progress(combined_scan_ready_message(counts), total_steps, total_steps)
            return games, steam_count, shortcut_count, folder_count

        def done(result: tuple[list[DetectedGame], int, int, int]) -> None:
            games, steam_count, shortcut_count, folder_count = result
            self.games = self.merge_game_lists([], games)
            self.current_game_index = None
            if self.games:
                self.refresh_game_table(select_index=0)
                if self.displayed_game_indices:
                    self.load_game_detail(self.displayed_game_indices[0])
            else:
                self.refresh_game_table()
            counts = CombinedScanCounts(steam=steam_count, shortcuts=shortcut_count, folders=folder_count)
            self.status_var.set(combined_scan_done_message(counts))
            self.prefetch_artwork_for_games(self.games, reason="combined scan")

        self.run_background("Scanning Steam and folders", task, done)

    def scan_games(self) -> None:
        self.save_current_detail()
        self.save_settings_from_ui(log=False)
        plan = build_folder_scan_plan(self.collection_path_var.get())
        if not plan.has_work or plan.collection_root is None:
            messagebox.showwarning(__app_name__, "Choose a game collection folder first.")
            return
        profile = self.current_profile()
        preserved_games = [game for game in self.games if game.source_type in {"steam", "shortcut"}]
        self.replace_live_scan_games(preserved_games, folder_scan_initial_message())

        def task() -> list[DetectedGame]:
            self.set_task_progress(folder_scan_start_message(), 0, 2)
            scanner = GameScanner(
                self.logger,
                cancel_check=self.raise_if_cancelled,
                progress_callback=lambda message: self.set_task_progress(message),
                game_callback=lambda game: self.post_ui(lambda g=game: self.add_live_scan_game(g)),
            )
            games = scanner.scan(plan.collection_root)
            self.raise_if_cancelled()
            self.set_task_progress(folder_scan_cross_check_message(len(games)), 1, 2)
            if profile:
                try:
                    records = load_shortcuts(profile.shortcuts_path)
                    mark_existing_shortcuts(games, records)
                    self.apply_existing_shortcut_choices(games, records)
                    loaded = load_existing_artwork_for_games(games, profile)
                    if loaded:
                        self.logger.info("Loaded %s existing Steam artwork file(s) for scanned folder games.", loaded)
                except Exception as exc:
                    self.logger.warning("Could not read existing shortcuts for duplicate detection: %s", exc)
            self.set_task_progress(folder_scan_ready_message(len(games)), 2, 2)
            return games

        def done(games: list[DetectedGame]) -> None:
            self.games = self.merge_game_lists(preserved_games, games)
            self.current_game_index = None
            if self.games:
                self.refresh_game_table(select_index=0)
                if self.displayed_game_indices:
                    self.load_game_detail(self.displayed_game_indices[0])
            else:
                self.refresh_game_table()
            self.status_var.set(folder_scan_done_message(len(games)))
            self.prefetch_artwork_for_games(games, reason="folder scan")

        self.run_background("Scanning games", task, done)

    def scan_steam_games(self) -> None:
        self.save_current_detail()
        self.save_settings_from_ui(log=False)
        plan = build_steam_scan_plan(
            self.steam_path_var.get(),
            is_valid_steam_path=is_valid_steam_path,
        )
        if not plan.has_path or plan.steam_path is None:
            messagebox.showwarning(__app_name__, "Detect or choose your Steam folder first.")
            return
        if not plan.steam_ready:
            messagebox.showwarning(__app_name__, "The Steam folder does not look valid yet.")
            return
        profile = self.current_profile()

        def task() -> list[DetectedGame]:
            self.set_task_progress(steam_scan_start_message(), 0, 3)
            self.raise_if_cancelled()
            games = scan_installed_steam_games(plan.steam_path)
            self.post_ui(
                lambda data=list(games): self.replace_live_scan_games(
                    self.merge_game_lists(self.games, data),
                    steam_scan_live_found_message(len(data)),
                )
            )
            self.raise_if_cancelled()
            self.set_task_progress(steam_scan_found_message(len(games)), 1, 3)
            if profile:
                try:
                    records = load_shortcuts(profile.shortcuts_path)
                    nonsteam_games = games_from_nonsteam_shortcuts(records)
                    games = self.merge_game_lists(games, nonsteam_games)
                    mark_existing_shortcuts(games, records)
                    self.apply_existing_shortcut_choices(games, records)
                    loaded = load_existing_artwork_for_games(games, profile)
                    if loaded:
                        self.logger.info("Loaded %s existing Steam artwork file(s) while scanning Steam library.", loaded)
                except Exception as exc:
                    self.logger.warning("Could not read existing shortcuts for Steam library comparison: %s", exc)
            self.set_task_progress(steam_scan_ready_message(), 3, 3)
            return games

        def done(games: list[DetectedGame]) -> None:
            before = len(self.games)
            self.games = self.merge_game_lists(self.games, games)
            self.current_game_index = None
            if self.games:
                select_index = 0 if before == 0 else min(before, len(self.games) - 1)
                self.refresh_game_table(select_index=select_index)
                if self.displayed_game_indices:
                    self.load_game_detail(select_index if select_index in self.displayed_game_indices else self.displayed_game_indices[0])
            else:
                self.refresh_game_table()
            added = len(self.games) - before
            self.status_var.set(steam_scan_done_message(added))
            self.prefetch_artwork_for_games(games, reason="Steam library scan")

        self.run_background("Scanning Steam library", task, done)

    def merge_game_lists(self, existing: list[DetectedGame], incoming: list[DetectedGame]) -> list[DetectedGame]:
        return merge_detected_game_lists(existing, incoming)

    def apply_existing_shortcut_choices(self, games: list[DetectedGame], records: list[Any]) -> None:
        for game in games:
            if game.is_native_steam_game:
                continue
            record = matching_record_for_game(records, game)
            if not record:
                continue
            shortcut_row = games_from_nonsteam_shortcuts([record])[0]
            merge_shortcut_state(game, shortcut_row)

    def replace_live_scan_games(self, games: list[DetectedGame], status: str = "") -> None:
        self.games = list(games)
        self.current_game_index = None
        self.sync_library_selection_state()
        self.refresh_game_table(select_index=0 if self.games else None)
        if self.displayed_game_indices:
            self.load_game_detail(self.displayed_game_indices[0])
        if status:
            self.status_var.set(status)

    def add_live_scan_game(self, game: DetectedGame) -> None:
        current_game = self.games[self.current_game_index] if self.current_game_index is not None and 0 <= self.current_game_index < len(self.games) else None
        self.games = self.merge_game_lists(self.games, [game])
        self.sync_library_selection_state()
        new_index = self.game_index_for_object(game)
        select_index = self.games.index(current_game) if current_game in self.games else new_index
        self.refresh_game_table(select_index=select_index)
        if self.current_game_index is None and new_index is not None and new_index in self.displayed_game_indices:
            self.load_game_detail(new_index)

    def game_identity_keys(self, game: DetectedGame) -> set[tuple[str, str]]:
        return game_identity_keys(game)

    def game_row_values(self, game: DetectedGame) -> tuple[str, str, str, str, str, str, str, str]:
        exe = str(game.selected_exe or "")
        source = game.source_type.replace("_", " ").title() if game.source_type else "Folder"
        platform = "PC"
        status = "Selected" if game.selected else "Ready"
        if is_persistent_library_game(game):
            row = modern_library_row_for_game(game)
            exe = library_launch_target_for_game(game) or exe
            source = row.source
            platform = row.platform_size_label
            status = row.status
        if game.is_native_steam_game:
            exe = f"Steam AppID {game.steam_appid}"
            source = "Steam"
            platform = "PC"
            status = "Installed"
        if is_persistent_library_game(game):
            existing = f"Stored {source} ({status})"
        elif game.is_native_steam_game:
            existing = "Installed Steam"
            if game.existing_appid is not None:
                existing += f" + non-Steam ({game.existing_match or 'title'})"
        elif game.existing_appid is not None:
            existing = "Existing non-Steam"
            if game.existing_match:
                existing += f" ({game.existing_match})"
        else:
            existing = "New non-Steam"
        return (
            "[x]" if game.selected else "[ ]",
            game.display_title,
            source,
            platform,
            status,
            exe,
            self.artwork_job_status.get(id(game), game.artwork_status),
            existing,
        )

    def sync_library_selection_state(self) -> None:
        active_id = ""
        if self.current_game_index is not None and 0 <= self.current_game_index < len(self.games):
            active_id = library_item_id_for_game(self.games[self.current_game_index])
        try:
            self.library_controller.set_active(active_id or None)
        except KeyError:
            pass
        for game in self.games:
            item_id = library_item_id_for_game(game)
            if not item_id:
                continue
            try:
                self.library_controller.set_selected(item_id, game.selected)
            except KeyError:
                continue

    def mirror_library_selection_state(self, snapshot: Any | None = None) -> None:
        snapshot = snapshot or self.library_controller.snapshot()
        apply_library_selection_to_games(self.games, snapshot.selected_ids)

    def set_library_items_selected(self, item_ids: tuple[str, ...], selected: bool) -> None:
        self.library_controller.set_items_selected(item_ids, selected)
        if item_ids:
            self.mirror_library_selection_state()

    def invert_library_item_selection(self, item_ids: tuple[str, ...]) -> None:
        if not item_ids:
            return
        self.library_controller.toggle_items(item_ids)
        self.mirror_library_selection_state()

    def metadata_score(self, game: DetectedGame) -> int:
        return sum(
            [
                bool(game.metadata.clean_title),
                bool(game.metadata.release_year),
                bool(game.metadata.developer),
                bool(game.metadata.publisher),
                bool(game.metadata.genres),
                bool(game.metadata.description),
                bool(game.metadata.notes),
            ]
        )

    def game_matches_filter(self, game: DetectedGame) -> bool:
        return game_matches_view_filter(game, self.view_filter_var.get())

    def visible_game_indices(self) -> list[int]:
        return visible_library_indices(self.games, self.view_filter_var.get())

    def apply_view_filter(self) -> None:
        self.settings.view_filter = self.view_filter_var.get()
        self.refresh_game_table(select_index=self.current_game_index)
        self.save_settings_from_ui(log=False)
        self.status_var.set(view_filter_status_message(len(self.displayed_game_indices), len(self.games)))

    def refresh_game_table(self, select_index: int | None = None) -> None:
        self.suppress_game_select_events = True
        self.games_tree.unbind("<<TreeviewSelect>>")
        for row in self.games_tree.get_children():
            self.games_tree.delete(row)
        self.displayed_game_indices = self.visible_game_indices()
        for index in self.displayed_game_indices:
            game = self.games[index]
            self.games_tree.insert(
                "",
                tk.END,
                iid=str(index),
                values=self.game_row_values(game),
                tags=self.game_row_tags(game),
            )
        if select_index is not None and select_index not in self.displayed_game_indices:
            select_index = self.displayed_game_indices[0] if self.displayed_game_indices else None
        if select_index is not None and 0 <= select_index < len(self.games) and self.games_tree.exists(str(select_index)):
            row_id = str(select_index)
            self.games_tree.selection_set(row_id)
            self.games_tree.focus(row_id)
            self.games_tree.see(row_id)
        self.games_tree.bind("<<TreeviewSelect>>", self.on_game_selected)
        self.suppress_game_select_events = False
        self.update_bulk_action_status()

    def refresh_game_row(self, index: int) -> None:
        if not (0 <= index < len(self.games)):
            return
        if not self.game_matches_filter(self.games[index]):
            if self.games_tree.exists(str(index)):
                self.refresh_game_table(select_index=self.current_game_index)
            return
        if self.games_tree.exists(str(index)):
            self.games_tree.item(str(index), values=self.game_row_values(self.games[index]), tags=self.game_row_tags(self.games[index]))
        else:
            self.refresh_game_table(select_index=self.current_game_index)
        self.update_bulk_action_status()

    def refresh_all_game_rows(self) -> None:
        if len(self.games_tree.get_children()) != len(self.visible_game_indices()):
            self.refresh_game_table(select_index=self.current_game_index)
            return
        for index in self.visible_game_indices():
            self.refresh_game_row(index)
        self.update_bulk_action_status()

    def update_bulk_action_status(self) -> None:
        summary = build_selection_summary(
            tuple(game.selected for game in self.games),
            tuple(self.displayed_game_indices),
        )
        self.bulk_status_var.set(summary.label)

    def set_all_games_selected(self, selected: bool) -> None:
        self.set_games_selected(selected, visible_only=False)

    def set_games_selected(self, selected: bool, visible_only: bool = False) -> None:
        indices = self.displayed_game_indices if visible_only else range(len(self.games))
        library_ids = library_item_ids_for_games(self.games, indices)
        self.set_library_items_selected(library_ids, selected)
        count = 0
        for index in indices:
            game = self.games[index]
            if not is_persistent_library_game(game):
                game.selected = selected
            count += 1
        self.refresh_all_game_rows()
        scope = "visible" if visible_only else "all"
        action = "select" if selected else "clear"
        self.status_var.set(selection_action_result(action, scope, count).label)

    def invert_visible_selection(self) -> None:
        self.invert_library_item_selection(library_item_ids_for_games(self.games, self.displayed_game_indices))
        for index in self.displayed_game_indices:
            if not is_persistent_library_game(self.games[index]):
                self.games[index].selected = not self.games[index].selected
        self.refresh_all_game_rows()
        self.status_var.set(selection_action_result("invert", "visible", len(self.displayed_game_indices)).label)

    def set_current_filter_selected(self, selected: bool) -> None:
        self.set_games_selected(selected, visible_only=True)
        action = "select" if selected else "clear"
        self.status_var.set(selection_action_result(action, "current_filter", len(self.displayed_game_indices)).label)

    def invert_current_filter_selection(self) -> None:
        self.invert_visible_selection()
        self.status_var.set(selection_action_result("invert", "current_filter", len(self.displayed_game_indices)).label)

    def invert_all_selection(self) -> None:
        self.invert_library_item_selection(library_item_ids_for_games(self.games))
        for game in self.games:
            if not is_persistent_library_game(game):
                game.selected = not game.selected
        self.refresh_all_game_rows()
        self.status_var.set(selection_action_result("invert", "all", len(self.games)).label)

    def select_needing_artwork(self) -> None:
        plan = build_selection_target_plan(self.games, "needing_artwork")
        apply_selection_target_plan(self.games, plan)
        self.set_library_items_selected(plan.persistent_item_ids_to_clear, False)
        self.refresh_all_game_rows()
        self.status_var.set(selection_target_label("needing_artwork", plan.selected_count))

    def select_new_nonsteam(self) -> None:
        plan = build_selection_target_plan(self.games, "new_nonsteam")
        apply_selection_target_plan(self.games, plan)
        self.set_library_items_selected(plan.persistent_item_ids_to_clear, False)
        self.refresh_all_game_rows()
        self.status_var.set(selection_target_label("new_nonsteam", plan.selected_count))

    def sort_key_for_game(self, game: DetectedGame, column: str) -> Any:
        return library_sort_key(game, column)

    def sort_games_by_column(self, column: str) -> None:
        if not self.games:
            return
        self.save_current_detail()
        current_game = self.games[self.current_game_index] if self.current_game_index is not None and 0 <= self.current_game_index < len(self.games) else None
        if self.sort_column == column:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_column = column
            self.sort_reverse = column == "artwork"
        self.games.sort(key=lambda game: self.sort_key_for_game(game, column), reverse=self.sort_reverse)
        select_index = self.games.index(current_game) if current_game in self.games else 0
        self.current_game_index = select_index
        self.refresh_game_table(select_index=select_index)
        self.load_game_detail(select_index)

    def apply_sort_preset(self) -> None:
        if not self.games:
            return
        self.save_current_detail()
        current_game = self.games[self.current_game_index] if self.current_game_index is not None and 0 <= self.current_game_index < len(self.games) else None
        preset = self.sort_preset_var.get()
        key = lambda game: library_sort_preset_key(game, preset)
        reverse = False
        self.games.sort(key=key, reverse=reverse)
        visible = self.visible_game_indices()
        select_index = self.games.index(current_game) if current_game in self.games else (visible[0] if visible else 0)
        if visible and select_index not in visible:
            select_index = visible[0]
        self.current_game_index = select_index if self.games else None
        self.settings.sort_preset = preset
        self.refresh_game_table(select_index=select_index)
        if self.games and 0 <= select_index < len(self.games):
            self.load_game_detail(select_index)
        self.save_settings_from_ui(log=False)

    def on_game_table_click(self, event: tk.Event[Any]) -> None:
        row_id = self.games_tree.identify_row(event.y)
        column_id = self.games_tree.identify_column(event.x)
        display_columns = list(self.games_tree["displaycolumns"])
        clicked_column = ""
        if column_id.startswith("#"):
            try:
                index = int(column_id[1:]) - 1
                if 0 <= index < len(display_columns):
                    clicked_column = display_columns[index]
            except ValueError:
                clicked_column = ""
        if row_id and clicked_column == "add":
            index = int(row_id)
            self.toggle_game_selection_at_index(index, range_select=bool(event.state & TK_SHIFT_MASK))
            self.games_tree.selection_set(row_id)
            self.games_tree.focus(row_id)
        elif row_id and (event.state & TK_CONTROL_MASK):
            index = int(row_id)
            self.toggle_game_selection_at_index(index)
            self.games_tree.selection_set(row_id)
            self.games_tree.focus(row_id)

    def on_game_table_space(self, event: tk.Event[Any]) -> str:
        row_id = self.games_tree.focus() or (self.games_tree.selection()[0] if self.games_tree.selection() else "")
        if row_id:
            self.toggle_game_selection_at_index(int(row_id), range_select=bool(event.state & TK_SHIFT_MASK))
        return "break"

    def toggle_game_selection_at_index(self, index: int, *, range_select: bool = False) -> None:
        if not (0 <= index < len(self.games)):
            return
        game = self.games[index]
        item_id = library_item_id_for_game(game)
        if item_id:
            selected_ids = self.library_controller.snapshot().selected_ids
            if range_select:
                ordered_ids = library_item_ids_for_games(self.games, self.displayed_game_indices)
                self.library_controller.select_range(ordered_ids, item_id, additive=True)
                self.mirror_library_selection_state()
            else:
                self.set_library_items_selected((item_id,), item_id not in selected_ids)
            self.library_selection_anchor_id = item_id
        else:
            game.selected = not game.selected
        self.sync_library_selection_state()
        self.refresh_game_row(index)

    def on_game_selected(self, _event: tk.Event[Any]) -> None:
        if self.suppress_game_select_events:
            return
        selection = self.games_tree.selection()
        if not selection:
            return
        index = int(selection[0])
        if self.current_game_index == index:
            return
        self.save_current_detail()
        self.load_game_detail(index)
        self.sync_library_selection_state()

    def notes_text_for_game(self, game: DetectedGame) -> str:
        if is_persistent_library_game(game):
            source = str(game.metadata.extra.get(LIBRARY_SOURCE_META) or "library").replace("_", " ").title()
            status = str(game.metadata.extra.get(LIBRARY_STATUS_META) or "stored").replace("_", " ").title()
            return (
                f"Persistent {source} library row - {status}.\n\n"
                "This legacy view is read-only for stored library rows. "
                "Use source scans to refresh library data; Steam writes remain disabled for these rows."
            )
        if game.is_native_steam_game:
            return (
                "Installed Steam game - protected reference row.\n\n"
                "Steam Shortcut Studio will not modify notes, artwork, categories, "
                "or shortcut data for games already owned in your Steam library."
            )
        if game.metadata.notes.strip():
            return game.metadata.notes
        has_note_source = any(
            [
                game.metadata.description,
                game.metadata.release_year,
            ]
        )
        return build_metadata_notes(game) if has_note_source else ""

    def refresh_notes_widget_if_current(self, game_index: int) -> None:
        if self.current_game_index != game_index or not (0 <= game_index < len(self.games)):
            return
        if self.notes_dirty:
            self.logger.info("Skipped automatic notes UI refresh because user edits are pending for %s.", self.games[game_index].display_title)
            return
        self.description_text.configure(state=tk.NORMAL)
        self.description_text.delete("1.0", tk.END)
        self.description_text.insert("1.0", self.notes_text_for_game(self.games[game_index]))
        self.description_text.edit_modified(False)
        self.notes_dirty = False
        self.set_detail_editable(not self.games[game_index].is_native_steam_game)
        self.logger.info("Updated Notes field for %s from release info and description.", self.games[game_index].display_title)

    def set_detail_editable(self, editable: bool) -> None:
        state = tk.NORMAL if editable else tk.DISABLED
        entry_state = "normal" if editable else "disabled"
        for entry in getattr(self, "detail_entries", {}).values():
            entry.configure(state=entry_state)
        self.description_text.configure(state=state)
        if hasattr(self, "save_edits_button"):
            self.save_edits_button.configure(state=tk.NORMAL if editable else tk.DISABLED)

    def on_notes_modified(self, _event: tk.Event[Any] | None = None) -> None:
        if not hasattr(self, "description_text") or not self.description_text.edit_modified():
            return
        self.notes_dirty = True
        self.description_text.edit_modified(False)

    def on_detail_modified(self) -> None:
        if not self.suppress_detail_dirty:
            self.detail_dirty = True

    def load_game_detail(self, index: int) -> None:
        if not (0 <= index < len(self.games)):
            return
        self.current_game_index = index
        game = self.games[index]
        item_id = library_item_id_for_game(game)
        if item_id:
            try:
                self.library_controller.set_active(item_id)
            except KeyError:
                pass
        self.set_detail_editable(True)
        self.suppress_detail_dirty = True
        self.detail_vars["title_entry"].set(game.display_title)
        self.detail_vars["launch_entry"].set(game.launch_options)
        self.detail_vars["year_entry"].set(game.metadata.release_year)
        if "developer_entry" in self.detail_vars:
            self.detail_vars["developer_entry"].set(game.metadata.developer)
        if "publisher_entry" in self.detail_vars:
            self.detail_vars["publisher_entry"].set(game.metadata.publisher)
        if "genres_entry" in self.detail_vars:
            self.detail_vars["genres_entry"].set(", ".join(game.metadata.genres))
        self.selected_exe_var.set(str(game.selected_exe or ""))
        self.suppress_detail_dirty = False
        self.detail_dirty = False
        self.notes_dirty = False
        self.description_text.delete("1.0", tk.END)
        self.description_text.insert("1.0", self.notes_text_for_game(game))
        self.description_text.edit_modified(False)
        self.notes_dirty = False
        self.set_detail_editable(not game.is_native_steam_game and not is_persistent_library_game(game))
        self.artwork_search_var.set(game.display_title)

        for row in self.candidate_tree.get_children():
            self.candidate_tree.delete(row)
        for candidate_index, candidate in enumerate(game.candidates):
            marker = "* " if game.selected_exe == candidate.path else ""
            self.candidate_tree.insert(
                "",
                tk.END,
                iid=str(candidate_index),
                values=(f"{candidate.confidence}%", marker + str(candidate.path)),
            )
        if game.candidates:
            self.candidate_tree.selection_set("0")
        self.update_reason_text()
        self.update_artwork_previews()
        self.display_cached_artwork_kind()

    def save_current_detail(self, force_notes: bool = False) -> None:
        if self.current_game_index is None or not (0 <= self.current_game_index < len(self.games)):
            return
        game = self.games[self.current_game_index]
        if is_persistent_library_game(game):
            self.logger.info("Skipped saving detail edits for stored library row: %s", game.display_title)
            return
        if game.is_native_steam_game:
            self.logger.info("Skipped saving detail edits for protected Steam game: %s", game.display_title)
            return
        should_save_fields = force_notes or self.detail_dirty
        should_save_notes = force_notes or self.notes_dirty
        if not should_save_fields and not should_save_notes:
            return
        if should_save_fields:
            title = self.detail_vars.get("title_entry", tk.StringVar()).get().strip()
            game.metadata.clean_title = title or game.title
            game.metadata.title_locked = bool(title and title != game.title)
            game.launch_options = self.detail_vars.get("launch_entry", tk.StringVar()).get().strip()
            game.metadata.release_year = self.detail_vars.get("year_entry", tk.StringVar()).get().strip()
            if "developer_entry" in self.detail_vars:
                game.metadata.developer = self.detail_vars["developer_entry"].get().strip()
            if "publisher_entry" in self.detail_vars:
                game.metadata.publisher = self.detail_vars["publisher_entry"].get().strip()
            if "genres_entry" in self.detail_vars:
                game.metadata.genres = [tag.strip() for tag in self.detail_vars["genres_entry"].get().split(",") if tag.strip()]
            self.detail_dirty = False
            self.logger.info("Saved reviewed shortcut fields for %s.", game.display_title)
        if should_save_notes:
            game.metadata.notes = self.description_text.get("1.0", tk.END).strip()
            if not game.metadata.notes and game.metadata.description:
                game.metadata.notes = build_metadata_notes(game)
            self.notes_dirty = False
            self.description_text.edit_modified(False)
            self.logger.info("Saved reviewed notes for %s (%s chars).", game.display_title, len(game.metadata.notes))
        self.refresh_game_row(self.current_game_index)

    def update_reason_text(self) -> None:
        self.reason_text.configure(state="normal")
        self.reason_text.delete("1.0", tk.END)
        if self.current_game_index is None:
            self.reason_text.configure(state="disabled")
            return
        game = self.games[self.current_game_index]
        candidate = game.selected_candidate
        if is_persistent_library_game(game):
            lines = [
                "Persistent library row.",
                f"Source: {game.metadata.extra.get(LIBRARY_SOURCE_META, 'library')}",
                f"Status: {game.metadata.extra.get(LIBRARY_STATUS_META, 'stored')}",
                f"Install folder: {game.root_path}",
            ]
            launch_target = library_launch_target_for_game(game)
            if launch_target:
                lines.append(f"Launch target: {launch_target}")
            lines.append("Read-only in the legacy view; no Steam writes are enabled for this row.")
            self.reason_text.insert("1.0", "\n".join(lines))
        elif game.is_native_steam_game:
            lines = [
                "Installed Steam game.",
                f"Steam AppID: {game.steam_appid}",
                f"Install folder: {game.root_path}",
                "Protected reference row: this app can replace local artwork, but will not modify notes, categories, or shortcut data for owned Steam games.",
            ]
            if game.existing_appid is not None:
                lines.append(f"Matching non-Steam shortcut already exists by {game.existing_match or 'title'}.")
            self.reason_text.insert("1.0", "\n".join(lines))
        elif not candidate:
            self.reason_text.insert("1.0", "No executable selected.")
        else:
            lines = [
                f"Selected: {candidate.path}",
                f"Score: {candidate.score:.1f} / confidence {candidate.confidence}%",
                f"Size: {candidate.size_mb:.1f} MB",
                "",
            ]
            lines.extend(f"- {reason}" for reason in candidate.reasons)
            if candidate.version_info:
                lines.append("")
                lines.append("Version info:")
                for key, value in candidate.version_info.items():
                    lines.append(f"- {key}: {value}")
            self.reason_text.insert("1.0", "\n".join(lines))
        self.reason_text.configure(state="disabled")

    def use_selected_candidate(self, _event: tk.Event[Any] | None = None) -> None:
        if self.current_game_index is None:
            return
        selection = self.candidate_tree.selection()
        if not selection:
            return
        game = self.games[self.current_game_index]
        if game.is_native_steam_game:
            messagebox.showinfo(__app_name__, "Installed Steam games are protected. Executable overrides only apply to non-Steam games.")
            return
        self.save_current_detail()
        candidate = game.candidates[int(selection[0])]
        game.selected_exe = candidate.path
        game.selected = True
        self.logger.info("Executable override selected from candidates for %s: %s", game.display_title, candidate.path)
        self.load_game_detail(self.current_game_index)
        self.refresh_game_row(self.current_game_index)

    def choose_manual_exe(self) -> None:
        if self.current_game_index is None:
            return
        game = self.games[self.current_game_index]
        if game.is_native_steam_game:
            messagebox.showinfo(__app_name__, "Installed Steam games are protected. Executable overrides only apply to non-Steam games.")
            return
        self.save_current_detail()
        path = filedialog.askopenfilename(
            title=f"Choose launch file for {game.title}",
            initialdir=str(game.root_path),
            filetypes=launch_filetypes(),
        )
        if not path:
            return
        exe = Path(path)
        candidate = ExecutableCandidate(
            path=exe,
            score=100,
            confidence=100,
            size_bytes=exe.stat().st_size if exe.exists() else 0,
            depth=0,
            reasons=["Manually selected by the user."],
        )
        game.candidates.insert(0, candidate)
        game.selected_exe = exe
        game.selected = True
        self.logger.info("Manual executable selected for %s: %s", game.display_title, exe)
        self.load_game_detail(self.current_game_index)
        self.refresh_game_row(self.current_game_index)

    def make_sgdb_client(self) -> SteamGridDbClient:
        self.save_settings_from_ui(log=False)
        return SteamGridDbClient(self.api_key_var.get().strip(), Path(self.settings.cache_dir), self.logger)

    def active_artwork_sources(self) -> dict[str, bool]:
        return {key: var.get() for key, var in self.artwork_source_vars.items()}

    def show_missing_artwork_api_prompt(self, sources: dict[str, bool]) -> None:
        missing = []
        if sources.get("steamgriddb", True) and not self.api_key_var.get().strip():
            missing.append("SteamGridDB")
        if sources.get("rawg", False) and not self.rawg_api_key_var.get().strip():
            missing.append("RAWG")
        if not missing:
            return
        message = f"{', '.join(missing)} key missing; using sources that do not need a key. Add keys in Settings > Artwork."
        self.status_var.set(message)
        self.logger.info(message)

    def make_metadata_service(self, client: SteamGridDbClient | None = None) -> MetadataService:
        client = client or self.make_sgdb_client()
        sources = {key: var.get() for key, var in self.metadata_source_vars.items()}
        return build_metadata_service(sources, client, self.logger)

    def selected_or_current_games(self) -> list[DetectedGame]:
        indices = selected_or_current_indices(
            tuple(game.selected for game in self.games),
            self.current_game_index,
        )
        return [self.games[index] for index in indices]

    def selected_games_in_current_view(self) -> list[DetectedGame]:
        return [self.games[index] for index in self.displayed_game_indices if 0 <= index < len(self.games) and self.games[index].selected]

    def game_index_for_object(self, game: DetectedGame, fallback: int | None = None) -> int | None:
        if fallback is not None and 0 <= fallback < len(self.games) and self.games[fallback] is game:
            return fallback
        for index, candidate in enumerate(self.games):
            if candidate is game:
                return index
        return None

    def set_artwork_job_status(self, game: DetectedGame, status: str, fallback_index: int | None = None) -> None:
        self.artwork_job_status[id(game)] = status
        game_index = self.game_index_for_object(game, fallback_index)
        if game_index is not None:
            self.refresh_game_row(game_index)

    def set_persistent_artwork_status(self, item_id: str, status: str) -> None:
        for index, game in enumerate(self.games):
            if library_item_id_for_game(game) == item_id:
                self.artwork_job_status[id(game)] = status
                self.refresh_game_row(index)
                return

    def clear_artwork_job_key(self, key: str) -> None:
        self.artwork_job_keys.discard(key)

    def can_auto_select_artwork(self, game: DetectedGame, kind: str, force_refresh: bool) -> bool:
        if force_refresh:
            return True
        if (id(game), kind) in self.manual_artwork_slots:
            return False
        return not artwork_asset_is_ready(getattr(game.artwork, kind))

    def preferred_artwork_search_text(self, game: DetectedGame) -> str:
        preferred = self.artwork_search_var.get().strip()
        if not preferred:
            return ""
        default_terms = {normalized_artwork_cache_key(term) for term in (game.display_title, game.title, game.source_title, game.metadata.clean_title)}
        if normalized_artwork_cache_key(preferred) in default_terms:
            return ""
        return preferred

    def artwork_search_text_for_game(self, game: DetectedGame) -> str:
        return self.artwork_search_var.get().strip() or game.display_title or game.title or game.source_title

    def sgdb_match_picker_available(self) -> bool:
        return bool(self.artwork_source_vars.get("steamgriddb") and self.artwork_source_vars["steamgriddb"].get() and self.api_key_var.get().strip())

    def find_art_for_current(self, force_refresh: bool = False) -> None:
        if self.current_game_index is None:
            messagebox.showwarning(__app_name__, "Select a game first.")
            return
        game = self.games[self.current_game_index]
        game.selected = True
        self.refresh_game_row(self.current_game_index)
        preferred = self.artwork_search_text_for_game(game)
        cache_preferred = self.preferred_artwork_search_text(game)
        if self.sgdb_match_picker_available():
            self.search_sgdb_matches_for_current(game, preferred, cache_preferred, force_refresh=force_refresh)
            return
        self.start_single_artwork_search(game, preferred=cache_preferred, force_refresh=force_refresh, artwork_only=True)

    def start_single_artwork_search(
        self,
        game: DetectedGame,
        preferred: str = "",
        force_refresh: bool = False,
        sgdb_game_id: int | None = None,
        artwork_only: bool = True,
    ) -> None:
        self.clear_individual_artwork_cache(game, preferred=preferred, sgdb_game_id=sgdb_game_id)
        self.match_metadata_and_art_for_games(
            [game],
            force_refresh=force_refresh,
            preferred_terms={id(game): preferred} if preferred else None,
            selected_sgdb_ids={id(game): sgdb_game_id} if sgdb_game_id else None,
            artwork_only=artwork_only,
        )

    def search_sgdb_matches_for_current(self, game: DetectedGame, search_text: str, cache_preferred: str, force_refresh: bool = False) -> None:
        game_index = self.game_index_for_object(game)
        client = self.make_sgdb_client()
        if not client.configured:
            self.start_single_artwork_search(game, preferred=cache_preferred, force_refresh=force_refresh, artwork_only=True)
            return

        def task() -> list[dict[str, Any]]:
            return self.sgdb_match_candidates(game, search_text, client, use_cache=not force_refresh)

        def done(candidates: list[dict[str, Any]]) -> None:
            if game_index is not None and self.game_index_for_object(game, game_index) is None:
                return
            chosen = self.choose_sgdb_artwork_match(game, candidates)
            if chosen is None:
                self.status_var.set("Artwork search cancelled.")
                return
            sgdb_id = int(chosen.get("id") or 0)
            chosen_name = str(chosen.get("name") or search_text).strip()
            if chosen_name:
                self.artwork_search_var.set(chosen_name)
            self.start_single_artwork_search(
                game,
                preferred=chosen_name or cache_preferred,
                force_refresh=force_refresh,
                sgdb_game_id=sgdb_id or None,
                artwork_only=True,
            )

        self.run_background("Searching SteamGridDB matches", task, done)

    def sgdb_match_candidates(self, game: DetectedGame, search_text: str, client: SteamGridDbClient, use_cache: bool = True) -> list[dict[str, Any]]:
        terms = self.artwork_search_terms(game, search_text)
        if not terms:
            terms = [search_text]
        seen: dict[int, dict[str, Any]] = {}
        for term in terms[:5]:
            if not term:
                continue
            self.raise_if_cancelled()
            try:
                candidates = client.search_games(term, use_cache=use_cache)
            except SteamGridDbError as exc:
                self.logger.warning("SteamGridDB match search failed for %s: %s", term, exc)
                continue
            for candidate in candidates[:12]:
                game_id = int(candidate.get("id") or 0)
                if not game_id:
                    continue
                detail: dict[str, Any] = {}
                try:
                    detail = client.get_game(game_id)
                except SteamGridDbError:
                    detail = {}
                merged = {**candidate, **detail} if isinstance(detail, dict) else dict(candidate)
                score = artwork_candidate_score(game, term, merged)
                merged["__score"] = score
                merged["__matched_term"] = term
                prior = seen.get(game_id)
                if prior is None or score > float(prior.get("__score") or 0):
                    seen[game_id] = merged
        ranked = sorted(seen.values(), key=lambda item: (float(item.get("__score") or 0), str(item.get("name") or "")), reverse=True)
        return ranked[:14]

    def sgdb_candidate_year(self, candidate: dict[str, Any]) -> str:
        for key in ("release_date", "released", "releaseDate"):
            year = release_year_from_text(str(candidate.get(key) or ""))
            if year:
                return year
        return ""

    def choose_sgdb_artwork_match(self, game: DetectedGame, candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
        if not candidates:
            return {}
        palette = self.palette()
        window = tk.Toplevel(self)
        window.title("Choose Artwork Match")
        window.geometry("720x420")
        window.transient(self)
        window.grab_set()
        window.columnconfigure(0, weight=1)
        window.rowconfigure(0, weight=1)
        result: dict[str, Any] | None = None

        tree = ttk.Treeview(window, columns=("name", "year", "score", "id"), show="headings", selectmode="browse")
        tree.heading("name", text="Name")
        tree.heading("year", text="Year")
        tree.heading("score", text="Match")
        tree.heading("id", text="SGDB ID")
        tree.column("name", width=410, anchor=tk.W)
        tree.column("year", width=80, anchor=tk.W)
        tree.column("score", width=80, anchor=tk.E)
        tree.column("id", width=100, anchor=tk.E)
        tree.grid(row=0, column=0, sticky="nsew", padx=10, pady=(10, 4))
        scrollbar = ttk.Scrollbar(window, orient=tk.VERTICAL, command=tree.yview)
        scrollbar.grid(row=0, column=1, sticky="ns", pady=(10, 4), padx=(0, 10))
        tree.configure(yscrollcommand=scrollbar.set)
        for index, candidate in enumerate(candidates):
            score = int(round(float(candidate.get("__score") or 0) * 100))
            tree.insert(
                "",
                tk.END,
                iid=str(index),
                values=(
                    str(candidate.get("name") or ""),
                    self.sgdb_candidate_year(candidate),
                    f"{score}%",
                    str(candidate.get("id") or ""),
                ),
            )
        if candidates:
            tree.selection_set("0")
            tree.focus("0")

        button_row = ttk.Frame(window, padding=(10, 4, 10, 10))
        button_row.grid(row=1, column=0, columnspan=2, sticky="ew")
        button_row.columnconfigure(0, weight=1)

        def choose_selected() -> None:
            nonlocal result
            selection = tree.selection()
            if not selection:
                return
            result = candidates[int(selection[0])]
            window.destroy()

        def skip_match() -> None:
            nonlocal result
            result = {}
            window.destroy()

        def cancel() -> None:
            nonlocal result
            result = None
            window.destroy()

        tree.bind("<Double-1>", lambda _event: choose_selected())
        ttk.Label(button_row, text=game.display_title, style="Subtle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Button(button_row, text="Cancel", command=cancel).grid(row=0, column=1, padx=(0, 8))
        ttk.Button(button_row, text="Skip Match", command=skip_match).grid(row=0, column=2, padx=(0, 8))
        ttk.Button(button_row, text="Use Selected", style="Accent.TButton", command=choose_selected).grid(row=0, column=3)
        window.protocol("WM_DELETE_WINDOW", cancel)
        self._theme_child(window, palette)
        self.wait_window(window)
        return result


    def match_metadata_and_art_for_selected(self, force_refresh: bool = False) -> None:
        selected = self.selected_games_in_current_view()
        if not selected:
            messagebox.showwarning(__app_name__, "Select at least one game in the current view.")
            return
        for game in selected:
            self.clear_individual_artwork_cache(game)
        self.match_metadata_and_art_for_games(selected, force_refresh=force_refresh)

    def match_metadata_and_art_for_games(
        self,
        selected: list[DetectedGame],
        force_refresh: bool = False,
        preferred_terms: dict[int, str] | None = None,
        selected_sgdb_ids: dict[int, int | None] | None = None,
        artwork_only: bool = False,
    ) -> None:
        client = self.make_sgdb_client()
        service = self.make_metadata_service(client)
        enabled_sources = self.active_artwork_sources()
        self.show_missing_artwork_api_prompt(enabled_sources)
        rawg_api_key = self.rawg_api_key_var.get().strip()
        preview_limit_per_kind = max(4, min(80, int(self.preview_limit_var.get() or 16)))
        cache_dir = Path(self.settings.cache_dir)
        preferred_terms = preferred_terms or {}
        selected_sgdb_ids = selected_sgdb_ids or {}
        index_by_game_id = {id(game): index for index, game in enumerate(self.games)}
        jobs: list[tuple[DetectedGame, str, str, int | None]] = []
        for game in selected:
            preferred = preferred_terms.get(id(game), "").strip()
            sgdb_game_id = selected_sgdb_ids.get(id(game))
            key = f"sgdb:{sgdb_game_id}" if sgdb_game_id else (self.artwork_cache_key(preferred) if preferred else self.artwork_cache_key(game))
            if key in self.artwork_job_keys:
                self.set_artwork_job_status(game, "Artwork search already running", index_by_game_id.get(id(game)))
                continue
            self.artwork_job_keys.add(key)
            self.set_artwork_job_status(game, "Queued artwork search", index_by_game_id.get(id(game)))
            jobs.append((game, key, preferred, sgdb_game_id))
        if not jobs:
            self.status_var.set("No new artwork searches needed.")
            return

        def task() -> tuple[int, int]:
            notes_count = 0
            artwork_count = 0
            total_steps = max(len(jobs) * 2, 1)
            step = 0
            self.set_task_progress("Lining up titles, store pages, and cover art...", step, total_steps)
            for number, (game, job_key, preferred, sgdb_game_id) in enumerate(jobs, start=1):
                game_index = index_by_game_id.get(id(game))
                try:
                    self.raise_if_cancelled()
                    title = preferred or game.source_title or game.title or game.display_title
                    allow_metadata_updates = not artwork_only and not game.is_native_steam_game
                    if allow_metadata_updates:
                        self.post_ui(lambda g=game, idx=game_index: self.set_artwork_job_status(g, "Reading store notes", idx))
                        self.logger.info("Finding artwork and Steam notes for %s using folder term %s", game.display_title, title)
                        self.set_task_progress(f"Reading store notes for {game.display_title} ({number}/{len(jobs)})", step, total_steps)
                        try:
                            service.enrich(game)
                        except Exception as exc:
                            self.logger.warning("Metadata lookup failed for %s: %s", game.display_title, exc)
                        self.raise_if_cancelled()
                        if not game.metadata.notes:
                            game.metadata.notes = build_metadata_notes(game)
                        self.logger.info("Prepared Steam notes for %s (%s chars).", game.display_title, len(game.metadata.notes))
                        if game_index is not None:
                            self.post_ui(lambda idx=game_index: self.refresh_notes_widget_if_current(idx))
                        notes_count += 1
                    else:
                        self.logger.info("Finding artwork only for %s using term %s", game.display_title, title)
                    step += 1

                    self.set_task_progress(f"Hanging artwork choices for {game.display_title} ({number}/{len(jobs)})", step, total_steps)
                    self.post_ui(lambda g=game, idx=game_index: self.set_artwork_job_status(g, "Searching artwork", idx))
                    assets_by_kind = None if force_refresh else self.cached_artwork_for_game(game, preferred)
                    if assets_by_kind is not None:
                        self.logger.info("Using cached artwork search results for %s.", preferred or game.display_title)
                    else:
                        assets_by_kind = self.collect_artwork_assets(
                            game,
                            title,
                            client,
                            use_sgdb_cache=not force_refresh,
                            enabled_sources=enabled_sources,
                            rawg_api_key=rawg_api_key,
                            sgdb_game_id=sgdb_game_id,
                            allow_metadata_updates=allow_metadata_updates,
                        )
                    self.raise_if_cancelled()
                    if game_index is not None:
                        self.post_ui(lambda idx=game_index, data=assets_by_kind, term=preferred: self.schedule_artwork_cache_refresh(idx, data, preferred=term, delay_ms=150))
                    selected_this_game = 0
                    for kind, assets in assets_by_kind.items():
                        selected_asset: ArtworkAsset | None = None
                        for asset in assets[:preview_limit_per_kind]:
                            self.raise_if_cancelled()
                            try:
                                download_asset(asset, cache_dir)
                            except Exception as exc:
                                self.logger.info("Artwork candidate failed for %s %s: %s", game.display_title, kind, exc)
                                continue
                            selected_asset = selected_asset or asset
                            artwork_count += 1
                            if game_index is not None and artwork_count % 3 == 0:
                                self.post_ui(lambda idx=game_index, data=assets_by_kind, term=preferred: self.schedule_artwork_cache_refresh(idx, data, preferred=term, delay_ms=100))
                        if selected_asset and self.can_auto_select_artwork(game, kind, force_refresh):
                            setattr(game.artwork, kind, selected_asset)
                            game.selected = True
                            selected_this_game += 1
                            self.logger.info("Auto-selected %s artwork for %s from %s.", kind, game.display_title, selected_asset.url)
                        elif selected_asset:
                            self.logger.info("Preserved existing/manual %s artwork for %s.", kind, game.display_title)
                    selected_this_game += self.fill_missing_artwork_slots(game)
                    if game_index is not None:
                        self.post_ui(lambda idx=game_index, data=assets_by_kind, term=preferred: self.update_artwork_cache_and_display(idx, data, preferred=term))
                        self.post_ui(lambda idx=game_index: self.refresh_game_row(idx))
                    status = "Artwork ready" if selected_this_game or game.artwork.selected_count() else "No confident artwork"
                    self.post_ui(lambda g=game, text=status, idx=game_index: self.set_artwork_job_status(g, text, idx))
                    step += 1
                    self.set_task_progress(f"Matched {number}/{len(jobs)} game(s); {artwork_count} artwork file(s) cached.", step, total_steps)
                except JobCancelled:
                    raise
                except Exception as exc:
                    self.logger.warning("Artwork search failed for %s: %s", game.display_title, exc)
                    self.post_ui(lambda g=game, idx=game_index: self.set_artwork_job_status(g, "Artwork failed", idx))
                    step += 2
                    continue
                finally:
                    self.post_ui(lambda key=job_key: self.clear_artwork_job_key(key))
            return notes_count, artwork_count

        def done(result: tuple[int, int]) -> None:
            notes_count, artwork_count = result
            self.refresh_all_game_rows()
            if self.current_game_index is not None:
                preferred = preferred_terms.get(id(self.games[self.current_game_index]), "") if 0 <= self.current_game_index < len(self.games) else ""
                self.load_game_detail(self.current_game_index)
                if preferred:
                    self.artwork_search_var.set(preferred)
            if artwork_only:
                self.status_var.set(f"Cached {artwork_count} artwork file(s).")
            else:
                self.status_var.set(f"Updated notes for {notes_count} game(s) and cached {artwork_count} artwork file(s).")

        if artwork_only:
            label = "Refreshing artwork" if force_refresh else "Finding artwork"
        else:
            label = "Refreshing artwork and notes" if force_refresh else "Finding artwork and notes"
        self.run_background(label, task, done)

    def fetch_artwork_for_selected(self, force_refresh: bool = False) -> None:
        if self.current_game_index is None:
            messagebox.showwarning(__app_name__, "Select a game first.")
            return
        self.fetch_artwork_for_games([self.games[self.current_game_index]], force_refresh=force_refresh)

    def fetch_artwork_for_all(self, force_refresh: bool = False) -> None:
        selected = [game for game in self.games if game.selected]
        if not selected:
            messagebox.showwarning(__app_name__, "Select at least one game.")
            return
        self.fetch_artwork_for_games(selected, force_refresh=force_refresh)

    def fetch_artwork_for_games(self, games: list[DetectedGame], force_refresh: bool = False) -> None:
        if not games:
            messagebox.showwarning(__app_name__, "Select at least one game.")
            return
        self.match_metadata_and_art_for_games(games, force_refresh=force_refresh)

    def artwork_search_terms(self, game: DetectedGame, preferred: str = "") -> list[str]:
        return build_artwork_search_terms(game, preferred)

    def local_artwork_assets_for_game(self, game: DetectedGame) -> dict[str, list[ArtworkAsset]]:
        assets_by_kind: dict[str, list[ArtworkAsset]] = {kind: [] for kind in ARTWORK_KINDS}
        for kind in assets_by_kind:
            asset = getattr(game.artwork, kind)
            if asset and asset.local_path and asset.local_path.exists():
                assets_by_kind[kind].append(asset)
        return assets_by_kind

    def fill_missing_artwork_slots(self, game: DetectedGame) -> int:
        fallback_order = {
            "wide": ("wide", "hero", "grid"),
            "hero": ("hero", "wide", "grid"),
            "icon": ("icon", "grid", "wide", "hero"),
            "grid": ("grid", "wide", "hero", "icon"),
            "logo": ("logo",),
        }
        filled = 0
        for slot, sources in fallback_order.items():
            current = getattr(game.artwork, slot)
            if current and current.local_path and current.local_path.exists():
                continue
            for source_slot in sources:
                source = getattr(game.artwork, source_slot)
                if source and source.local_path and source.local_path.exists():
                    setattr(game.artwork, slot, source if source.kind == slot else replace(source, kind=slot, asset_id=f"{source.asset_id}-{slot}-fallback"))
                    filled += 1
                    break
        if filled:
            self.logger.info("Filled %s artwork fallback slot(s) for %s.", filled, game.display_title)
        return filled

    def prefetch_artwork_for_games(self, games: list[DetectedGame], reason: str = "scan") -> None:
        if not games:
            return
        index_by_game_id = {id(game): index for index, game in enumerate(self.games)}
        loaded = 0
        games_with_art = 0
        for game in games:
            assets_by_kind = self.local_artwork_assets_for_game(game)
            count = sum(len(assets) for assets in assets_by_kind.values())
            if not count:
                continue
            game_index = index_by_game_id.get(id(game))
            if game_index is None:
                continue
            self.artwork_search_cache[game_index] = assets_by_kind
            for cache_key in self.artwork_cache_keys(game):
                self.artwork_title_cache[cache_key] = assets_by_kind
            games_with_art += 1
            loaded += count
        if loaded:
            self.save_persistent_artwork_search_cache()
            self.refresh_all_game_rows()
            if self.current_game_index is not None:
                self.display_cached_artwork_kind()
            self.status_var.set(f"Loaded {loaded} local artwork preview(s) from {games_with_art} game(s) after {reason}.")
            self.logger.info("Loaded %s local artwork preview(s) from %s game(s) after %s.", loaded, games_with_art, reason)

    def search_artwork(self, force_refresh: bool = False) -> None:
        self.find_art_for_current(force_refresh=force_refresh)

    def update_artwork_cache_and_display(self, game_index: int, assets_by_kind: dict[str, list[ArtworkAsset]], preferred: str = "") -> None:
        self.artwork_search_cache[game_index] = assets_by_kind
        if 0 <= game_index < len(self.games):
            for cache_key in self.artwork_cache_keys(self.games[game_index], preferred):
                self.artwork_title_cache[cache_key] = assets_by_kind
            self.save_persistent_artwork_search_cache()
        if self.current_game_index == game_index:
            self.display_cached_artwork_kind()

    def schedule_artwork_cache_refresh(self, game_index: int, assets_by_kind: dict[str, list[ArtworkAsset]], preferred: str = "", delay_ms: int = 350) -> None:
        self.artwork_search_cache[game_index] = assets_by_kind
        if 0 <= game_index < len(self.games):
            for cache_key in self.artwork_cache_keys(self.games[game_index], preferred):
                self.artwork_title_cache[cache_key] = assets_by_kind
        after_id = self.artwork_refresh_after_ids.get(game_index)
        if after_id:
            try:
                self.after_cancel(after_id)
            except tk.TclError:
                pass
        self.artwork_refresh_after_ids[game_index] = self.after(
            delay_ms,
            lambda: self.update_artwork_cache_and_display(game_index, assets_by_kind, preferred),
        )

    def collect_artwork_assets(
        self,
        game: DetectedGame,
        term: str,
        client: SteamGridDbClient,
        use_sgdb_cache: bool = True,
        use_extended_sources: bool = True,
        enabled_sources: dict[str, bool] | None = None,
        rawg_api_key: str = "",
        sgdb_game_id: int | None = None,
        allow_metadata_updates: bool = True,
    ) -> dict[str, list[ArtworkAsset]]:
        return ArtworkProviderSearchService(self.logger).collect_assets(
            game,
            term,
            client,
            use_sgdb_cache=use_sgdb_cache,
            use_extended_sources=use_extended_sources,
            enabled_sources=enabled_sources or self.active_artwork_sources(),
            rawg_api_key=rawg_api_key,
            sgdb_game_id=sgdb_game_id,
            allow_metadata_updates=allow_metadata_updates,
            cancellation_checkpoint=self.raise_if_cancelled,
        )

    def display_cached_artwork_kind(self) -> None:
        if self.current_game_index is None:
            return
        cached = self.artwork_search_cache.get(self.current_game_index)
        if cached is None and 0 <= self.current_game_index < len(self.games):
            cached = self.cached_artwork_for_game(self.games[self.current_game_index])
            if cached:
                self.artwork_search_cache[self.current_game_index] = cached
                self.logger.info("Restored artwork cache while displaying %s.", self.games[self.current_game_index].display_title)
        cached = cached or {}
        selected_kind = self.artwork_kind_var.get()
        if selected_kind == "all":
            all_assets: list[ArtworkAsset] = []
            for kind in ARTWORK_KINDS:
                all_assets.extend(cached.get(kind, []))
            self.populate_artwork_results(all_assets)
        else:
            self.populate_artwork_results(cached.get(selected_kind, []))

    def populate_artwork_results(self, assets: list[ArtworkAsset]) -> None:
        display_assets = [asset for asset in assets if asset.local_path and asset.local_path.exists()]
        self.current_artwork_results = display_assets
        for row in self.artwork_tree.get_children():
            self.artwork_tree.delete(row)
        for index, asset in enumerate(display_assets[:100]):
            self.artwork_tree.insert(
                "",
                tk.END,
                iid=str(index),
                values=(asset.kind, asset.dimensions, asset.score, asset.style, asset.url),
            )
        self.render_artwork_thumbnails(assets)

    def on_artwork_canvas_configure(self, event: tk.Event[Any]) -> None:
        self.artwork_canvas.itemconfigure(self.artwork_canvas_window, width=event.width)
        if not self.current_artwork_results:
            return
        if self.artwork_reflow_after_id:
            self.after_cancel(self.artwork_reflow_after_id)
        self.artwork_reflow_after_id = self.after(90, self.render_artwork_thumbnails)

    def artwork_grid_columns(self) -> int:
        width = self.artwork_canvas.winfo_width() if hasattr(self, "artwork_canvas") else 700
        return max(1, width // 188)

    def render_artwork_thumbnails(self, source_assets: list[ArtworkAsset] | None = None) -> None:
        self.artwork_reflow_after_id = None
        if self.artwork_render_after_id:
            try:
                self.after_cancel(self.artwork_render_after_id)
            except tk.TclError:
                pass
            self.artwork_render_after_id = None
        self.artwork_render_token += 1
        render_token = self.artwork_render_token
        self.artwork_result_images.clear()
        for child in self.artwork_thumb_frame.winfo_children():
            child.destroy()
        assets = source_assets if source_assets is not None else self.current_artwork_results
        display_assets = [asset for asset in assets if asset.local_path and asset.local_path.exists()]
        if not assets:
            ttk.Label(self.artwork_thumb_frame, text="No collected artwork yet. Click Search Art.", style="Subtle.TLabel").grid(row=0, column=0, sticky="w")
            return
        if not display_assets:
            ttk.Label(self.artwork_thumb_frame, text="Loading artwork previews...", style="Subtle.TLabel").grid(row=0, column=0, sticky="w")
            return
        columns = self.artwork_grid_columns()
        for col in range(columns):
            self.artwork_thumb_frame.columnconfigure(col, weight=1, uniform="artwork_tiles")
        self._render_artwork_thumbnail_batch(display_assets, 0, columns, render_token)

    def _render_artwork_thumbnail_batch(self, display_assets: list[ArtworkAsset], start: int, columns: int, render_token: int) -> None:
        if render_token != self.artwork_render_token:
            return
        palette = self.palette()
        batch_size = 10
        for index, asset in enumerate(display_assets[start : start + batch_size], start=start):
            row = index // columns
            col = index % columns
            source = str(asset.raw.get("source") or ("SteamGridDB" if "steamgriddb" in asset.url else ""))
            text = f"{asset.kind.title()}\n{source}".strip()
            image = self._load_preview_image(asset.local_path, max_size=(150, 95)) if asset.local_path else None
            button = tk.Button(
                self.artwork_thumb_frame,
                image=image or "",
                text=text if not image else asset.kind.title(),
                compound=tk.TOP,
                width=170,
                height=128,
                wraplength=155,
                command=lambda chosen=asset: self.use_artwork_asset(chosen),
                bg=palette["panel"],
                fg=palette["text"],
                activebackground=palette["selected"],
                activeforeground=palette["selected_text"],
                relief=tk.GROOVE,
                borderwidth=1,
                font=("Segoe UI", 8),
            )
            button.grid(row=row, column=col, sticky="nsew", padx=5, pady=5)
            ToolTip(button, asset.url)
            if image:
                self.artwork_result_images.append(image)
        next_index = start + batch_size
        if next_index < len(display_assets):
            self.artwork_render_after_id = self.after(
                12,
                lambda: self._render_artwork_thumbnail_batch(display_assets, next_index, columns, render_token),
            )

    def use_highlighted_artwork(self, _event: tk.Event[Any] | None = None) -> None:
        if self.current_game_index is None:
            return
        selection = self.artwork_tree.selection()
        if not selection:
            messagebox.showwarning(__app_name__, "Highlight an artwork result first.")
            return
        self.use_artwork_asset(self.current_artwork_results[int(selection[0])])

    def use_artwork_asset(self, asset: ArtworkAsset) -> None:
        if self.current_game_index is None:
            return
        game_index = self.current_game_index
        game = self.games[game_index]

        def task() -> ArtworkAsset:
            download_asset(asset, Path(self.settings.cache_dir))
            return asset

        def done(downloaded: ArtworkAsset) -> None:
            self.manual_artwork_slots.add((id(game), downloaded.kind))
            setattr(game.artwork, downloaded.kind, downloaded)
            self.fill_missing_artwork_slots(game)
            game.selected = True
            row_index = self.game_index_for_object(game, game_index)
            if row_index is not None:
                self.refresh_game_row(row_index)
                if self.current_game_index == row_index:
                    self.load_game_detail(row_index)

        self.run_background("Downloading selected artwork", task, done)

    def preview_size_for_kind(self, kind: str) -> tuple[int, int]:
        return {
            "grid": (102, 126),
            "wide": (158, 82),
            "hero": (158, 90),
            "logo": (150, 76),
            "icon": (92, 92),
        }.get(kind, (150, 95))

    def selected_artwork_asset_for_kind(self, kind: str) -> ArtworkAsset | None:
        if self.current_game_index is None:
            return None
        return getattr(self.games[self.current_game_index].artwork, kind, None)

    def selected_artwork_path_for_kind(self, kind: str) -> Path | None:
        asset = self.selected_artwork_asset_for_kind(kind)
        path = Path(asset.local_path) if asset and asset.local_path else None
        return path if path and path.exists() else None

    def show_artwork_preview_menu(self, event: tk.Event[Any], kind: str) -> None:
        has_game = self.current_game_index is not None
        has_asset = self.selected_artwork_asset_for_kind(kind) is not None
        has_path = self.selected_artwork_path_for_kind(kind) is not None
        menu = tk.Menu(self, tearoff=False)
        menu.add_command(
            label="Preview",
            command=lambda: self.open_selected_artwork_preview(kind),
            state=tk.NORMAL if has_path else tk.DISABLED,
        )
        menu.add_command(
            label="Choose Custom Image...",
            command=lambda: self.choose_custom_artwork_image(kind),
            state=tk.NORMAL if has_game else tk.DISABLED,
        )
        menu.add_command(
            label="Clear Image",
            command=lambda: self.clear_selected_artwork_image(kind),
            state=tk.NORMAL if has_asset else tk.DISABLED,
        )
        menu.add_separator()
        menu.add_command(
            label="Edit in Paint" if os.name == "nt" else "Open Image Externally",
            command=lambda: self.edit_selected_artwork_in_paint(kind),
            state=tk.NORMAL if has_path else tk.DISABLED,
        )
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def image_dimensions_for_path(self, path: Path) -> tuple[int, int]:
        if Image:
            try:
                with Image.open(path) as image:
                    return image.size
            except Exception:
                return (0, 0)
        if path.suffix.lower() != ".png":
            return (0, 0)
        try:
            image = tk.PhotoImage(file=str(path))
            return (image.width(), image.height())
        except Exception:
            return (0, 0)

    def forget_preview_cache_for_path(self, path: Path) -> None:
        path_text = str(path)
        for key in list(self.image_cache):
            if key[0] == path_text:
                self.image_cache.pop(key, None)

    def choose_custom_artwork_image(self, kind: str) -> None:
        if self.current_game_index is None:
            return
        game = self.games[self.current_game_index]
        initial_dir = str(game.root_path) if game.root_path.exists() else str(Path.home())
        path_text = filedialog.askopenfilename(
            title=f"Choose {kind.title()} Artwork",
            initialdir=initial_dir,
            filetypes=[("JPG or PNG images", "*.jpg *.png")],
        )
        if not path_text:
            return
        path = Path(path_text).expanduser().resolve(strict=False)
        if path.suffix.lower() not in {".jpg", ".png"}:
            messagebox.showerror(__app_name__, "Choose a .jpg or .png image.")
            return
        if not path.exists():
            messagebox.showerror(__app_name__, f"Image file does not exist:\n\n{path}")
            return
        width, height = self.image_dimensions_for_path(path)
        try:
            url = path.as_uri()
        except ValueError:
            url = str(path)
        asset = ArtworkAsset(
            kind=kind,
            asset_id=f"custom-{kind}-{path.stem}-{path.stat().st_mtime_ns}",
            url=url,
            thumb_url=url,
            width=width,
            height=height,
            mime="image/png" if path.suffix.lower() == ".png" else "image/jpeg",
            score=100,
            style="custom",
            local_path=path,
            raw={"source": "Custom image"},
        )
        setattr(game.artwork, kind, asset)
        self.manual_artwork_slots.add((id(game), kind))
        game.selected = True
        self.forget_preview_cache_for_path(path)
        self.update_artwork_previews()
        self.refresh_game_row(self.current_game_index)
        self.status_var.set(custom_artwork_selected_message(kind, game.display_title))
        self.logger.info("Custom %s artwork selected for %s: %s", kind, game.display_title, path)

    def clear_selected_artwork_image(self, kind: str) -> None:
        if self.current_game_index is None:
            return
        game = self.games[self.current_game_index]
        asset = getattr(game.artwork, kind, None)
        if asset and asset.local_path:
            self.forget_preview_cache_for_path(Path(asset.local_path))
        setattr(game.artwork, kind, None)
        self.manual_artwork_slots.discard((id(game), kind))
        self.update_artwork_previews()
        self.refresh_game_row(self.current_game_index)
        self.status_var.set(artwork_cleared_message(kind, game.display_title))
        self.logger.info("Cleared %s artwork for %s.", kind, game.display_title)

    def refresh_artwork_after_external_edit(self, path: Path, kind: str) -> None:
        self.forget_preview_cache_for_path(path)
        self.update_artwork_previews()
        if self.current_game_index is not None:
            self.refresh_game_row(self.current_game_index)
            game = self.games[self.current_game_index]
            self.status_var.set(artwork_preview_refreshed_message(kind, game.display_title))

    def edit_selected_artwork_in_paint(self, kind: str) -> None:
        path = self.selected_artwork_path_for_kind(kind)
        if not path:
            messagebox.showinfo(__app_name__, f"No {kind} artwork is selected.")
            return
        if os.name == "nt":
            command = ["mspaint.exe", str(path)]
            app_name = "Paint"
            popen_kwargs: dict[str, Any] = {}
        else:
            opener = shutil.which("xdg-open") or shutil.which("gio")
            if not opener:
                messagebox.showerror(__app_name__, "Could not find xdg-open or gio to open the image.")
                return
            command = [opener, "open", str(path)] if Path(opener).name == "gio" else [opener, str(path)]
            app_name = "the default image app"
            popen_kwargs = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL, "start_new_session": True}
        try:
            process = subprocess.Popen(command, **popen_kwargs)
        except OSError as exc:
            self.logger.warning("Could not open external image editor for %s: %s", path, exc)
            messagebox.showerror(__app_name__, f"Could not open {app_name}:\n\n{exc}")
            return
        self.status_var.set(artwork_editor_opened_message(kind, app_name))

        if os.name != "nt":
            self.after(1500, lambda: self.refresh_artwork_after_external_edit(path, kind))
            return

        def wait_for_paint() -> None:
            try:
                process.wait()
            except Exception:
                pass
            self.post_ui(lambda: self.refresh_artwork_after_external_edit(path, kind))

        threading.Thread(target=wait_for_paint, daemon=True).start()

    def open_selected_artwork_preview(self, kind: str) -> None:
        if self.current_game_index is None:
            return
        game = self.games[self.current_game_index]
        asset = getattr(game.artwork, kind, None)
        path = Path(asset.local_path) if asset and asset.local_path else None
        if not path or not path.exists():
            messagebox.showinfo(__app_name__, f"No {kind} artwork is selected.")
            return

        screen_width = max(800, self.winfo_screenwidth())
        screen_height = max(600, self.winfo_screenheight())
        width = max(640, int(screen_width * 0.75))
        height = max(480, int(screen_height * 0.75))
        x = max(0, (screen_width - width) // 2)
        y = max(0, (screen_height - height) // 2)

        window = tk.Toplevel(self)
        window.title(f"{game.display_title} - {kind.title()} Artwork")
        window.geometry(f"{width}x{height}+{x}+{y}")
        window.minsize(480, 360)
        window.transient(self)
        window.configure(bg=self.palette()["canvas"])
        window.bind("<Escape>", lambda _event: window.destroy())

        image_label = tk.Label(window, bg=self.palette()["canvas"], fg=self.palette()["text"])
        image_label.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)
        footer = ttk.Label(window, text=path.name, style="Subtle.TLabel", anchor=tk.CENTER)
        footer.pack(fill=tk.X, padx=12, pady=(0, 12))

        if Image and ImageTk:
            try:
                with Image.open(path) as opened:
                    original = opened.copy()
            except Exception as exc:
                image_label.configure(text=f"Could not open image:\n{exc}")
                return

            def render_large_preview(_event: tk.Event[Any] | None = None) -> None:
                max_width = max(1, image_label.winfo_width())
                max_height = max(1, image_label.winfo_height())
                image = original.copy()
                resampling = getattr(getattr(Image, "Resampling", Image), "LANCZOS", 1)
                image.thumbnail((max_width, max_height), resampling)
                photo = ImageTk.PhotoImage(image)
                image_label.configure(image=photo, text="")
                image_label.image = photo

            image_label.bind("<Configure>", render_large_preview)
            window.after(80, render_large_preview)
            return

        if path.suffix.lower() not in {".png", ".gif"}:
            image_label.configure(text="Large preview needs Pillow for this image type.")
            return
        try:
            image = tk.PhotoImage(file=str(path))
            while image.width() > width - 24 or image.height() > height - 60:
                image = image.subsample(2, 2)
            image_label.configure(image=image, text="")
            image_label.image = image
        except Exception as exc:
            image_label.configure(text=f"Could not open image:\n{exc}")

    def update_artwork_previews(self) -> None:
        self.preview_images.clear()
        if self.current_game_index is None:
            return
        game = self.games[self.current_game_index]
        for kind in ARTWORK_KINDS:
            label = self.preview_labels[kind]
            asset = getattr(game.artwork, kind)
            if not asset or not asset.local_path or not asset.local_path.exists():
                label.configure(image="", text="No image", fg=self.palette()["muted"])
                continue
            image = self._load_preview_image(asset.local_path, max_size=self.preview_size_for_kind(kind))
            if image:
                self.preview_images.append(image)
                label.configure(image=image, text="", fg=self.palette()["text"])
            else:
                label.configure(image="", text=asset.local_path.name, fg=self.palette()["text"])

    def _load_preview_image(self, path: Path, max_size: tuple[int, int]) -> Any:
        try:
            cache_key = (str(path), max_size, path.stat().st_mtime_ns)
        except OSError:
            return None
        cached = self.image_cache.get(cache_key)
        if cached:
            return cached
        if Image and ImageTk:
            try:
                image = Image.open(path)
                image.thumbnail(max_size)
                photo = ImageTk.PhotoImage(image)
                self.image_cache[cache_key] = photo
                return photo
            except Exception:
                return None
        if path.suffix.lower() not in {".png", ".gif"}:
            return None
        try:
            image = tk.PhotoImage(file=str(path))
            while image.width() > max_size[0] or image.height() > max_size[1]:
                image = image.subsample(2, 2)
            self.image_cache[cache_key] = image
            return image
        except Exception:
            return None

    def enrich_metadata_for_selected(self) -> None:
        indices = metadata_refresh_indices(
            tuple(game.selected for game in self.games),
            tuple(game.is_native_steam_game for game in self.games),
            self.current_game_index,
        )
        selected = [self.games[index] for index in indices]
        if not selected:
            messagebox.showwarning(__app_name__, "Select at least one non-Steam game.")
            return
        service = self.make_metadata_service()
        index_by_game_id = {id(game): index for index, game in enumerate(self.games)}

        def task() -> int:
            total = len(selected)
            for index, game in enumerate(selected, start=1):
                self.raise_if_cancelled()
                self.set_task_progress(f"Reading release notes for {game.display_title} ({index}/{total})", index - 1, total)
                self.logger.info("Refreshing Steam notes for %s", game.display_title)
                service.enrich(game)
                if not game.metadata.notes:
                    game.metadata.notes = build_metadata_notes(game)
                self.logger.info("Steam notes ready for %s (%s chars).", game.display_title, len(game.metadata.notes))
                game_index = index_by_game_id.get(id(game))
                if game_index is not None:
                    self.post_ui(lambda idx=game_index: self.refresh_notes_widget_if_current(idx))
            self.set_task_progress(f"Notes ready for {total} game(s).", total, total)
            return len(selected)

        def done(count: int) -> None:
            self.refresh_all_game_rows()
            if self.current_game_index is not None:
                self.load_game_detail(self.current_game_index)
            self.status_var.set(f"Updated notes for {count} game(s).")

        self.run_background("Refreshing Steam notes", task, done)

    def preview_write(self) -> None:
        self.save_current_detail()
        profile = self.current_profile()
        if not profile:
            messagebox.showwarning(__app_name__, "Choose a Steam profile first.")
            return
        compat_tool = self.selected_compat_tool_name()
        compat_for_preview = compat_tool if (os.name != "nt" or compat_tool) else None
        try:
            text = preview_changes(
                profile,
                self.games,
                self.update_existing_var.get(),
                default_tags=[tag.strip() for tag in self.default_tags_var.get().split(",") if tag.strip()],
                compat_tool=compat_for_preview,
            )
        except VdfParseError as exc:
            messagebox.showerror(__app_name__, f"Steam shortcuts.vdf could not be parsed safely:\n\n{exc}")
            return
        window = tk.Toplevel(self)
        window.title("Preview Steam Shortcut Changes")
        window.geometry("760x620")
        window.columnconfigure(0, weight=1)
        window.rowconfigure(0, weight=1)
        text_widget = tk.Text(window, wrap="word", font=("Consolas", 10))
        text_widget.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        text_widget.insert("1.0", text)
        text_widget.configure(state="disabled")
        button_frame = ttk.Frame(window, padding=(10, 0, 10, 10))
        button_frame.grid(row=1, column=0, sticky="ew")
        ttk.Button(button_frame, text="Close", command=window.destroy).pack(side=tk.RIGHT)
        ttk.Button(button_frame, text="Write to Steam", style="Accent.TButton", command=lambda: (window.destroy(), self.write_to_steam())).pack(
            side=tk.RIGHT, padx=(0, 8)
        )

    def write_to_steam(self) -> None:
        self.save_current_detail()
        self.save_settings_from_ui(log=False)
        profile = self.current_profile()
        if not profile:
            messagebox.showwarning(__app_name__, "Choose a Steam profile first.")
            return
        selected = [
            game
            for game in self.games
            if game.selected
            and not is_persistent_library_game(game)
            and (game.is_managed_non_steam or (game.is_native_steam_game and game.artwork.selected_count()))
        ]
        if not selected and self.current_game_index is not None and 0 <= self.current_game_index < len(self.games):
            current = self.games[self.current_game_index]
            if (
                not is_persistent_library_game(current)
                and (
                    current.is_managed_non_steam
                    or (current.is_native_steam_game and current.artwork.selected_count())
                )
            ):
                current.selected = True
                selected = [current]
                self.refresh_game_row(self.current_game_index)
                self.logger.info("No checked writable rows; using current row for write: %s", current.display_title)
        if not selected:
            messagebox.showwarning(__app_name__, "No selected games have shortcuts or artwork ready to write.")
            return
        self.logger.info("Write requested for %s selected writable game(s).", len(selected))
        steam_path = Path(self.steam_path_var.get().strip())
        compat_tool = self.selected_compat_tool_name()
        compat_label = self.compat_tool_display_name(compat_tool)
        manage_compat_tool = os.name != "nt" or bool(compat_tool)

        def task() -> tuple[int, int, Path | None, int, int, CompatToolWriteResult | None, bool, bool]:
            steam_closed = False
            steam_reopened = False
            added = 0
            updated = 0
            backup: Path | None = None
            compat_result: CompatToolWriteResult | None = None
            copied_count = 0
            notes_count = 0
            try:
                self.set_task_progress("Closing Steam for a clean write, only if it is running...", 0, 6)
                self.raise_if_cancelled()
                if is_valid_steam_path(steam_path):
                    steam_closed = shutdown_steam_for_write(steam_path)
                elif is_steam_running():
                    raise RuntimeError("Steam is running, but the configured Steam folder is not valid. Choose the Steam folder so the app can close Steam safely before writing.")
                if steam_closed:
                    self.logger.info("Steam was closed before writing and will be reopened afterward.")
                shortcut_games = [game for game in selected if game.selected_exe and not game.is_native_steam_game]
                self.set_task_progress(f"Writing {len(shortcut_games)} non-Steam shortcut(s) safely...", 1, 6)
                self.raise_if_cancelled()
                if shortcut_games:
                    added, updated, backup = upsert_games(
                        profile,
                        shortcut_games,
                        update_existing=self.update_existing_var.get(),
                        default_tags=[tag.strip() for tag in self.default_tags_var.get().split(",") if tag.strip()],
                    )
                self.set_task_progress(f"Applying Steam Play compatibility: {compat_label}...", 2, 6)
                self.raise_if_cancelled()
                if shortcut_games and manage_compat_tool:
                    written_records = load_shortcuts(profile.shortcuts_path) if profile.shortcuts_path.exists() else []
                    compat_records = [record for game in shortcut_games if (record := matching_record_for_game(written_records, game))]
                    compat_result = write_compat_tool_mappings(profile, compat_records, compat_tool)
                    if compat_result.tool:
                        self.logger.info(
                            "Steam Play compatibility set to %s for %s shortcut(s) in %s.",
                            compat_result.tool,
                            compat_result.applied,
                            compat_result.config_path,
                        )
                    else:
                        self.logger.info(
                            "Steam Play compatibility cleared for %s shortcut(s) in %s.",
                            compat_result.cleared,
                            compat_result.config_path,
                        )
                elif shortcut_games:
                    self.logger.info("Steam Play compatibility was left unchanged on Windows because no tool was selected.")
                self.set_task_progress("Copying selected artwork into Steam's grid folder...", 3, 6)
                self.raise_if_cancelled()
                try:
                    copied = copy_all_artwork_to_steam(self.games, profile)
                except Exception as exc:
                    copied = []
                    self.logger.warning("Shortcut write succeeded, but artwork copy failed: %s", exc)
                self.set_task_progress("Writing release notes and Big Picture-visible shortcut tags...", 4, 6)
                self.raise_if_cancelled()
                try:
                    for game in self.games:
                        if not game.selected or not game.is_managed_non_steam:
                            continue
                        if not game.metadata.notes:
                            game.metadata.notes = build_metadata_notes(game)
                        self.logger.info("Queueing Steam note for %s (%s chars).", game.display_title, len(game.metadata.notes))
                    notes = write_metadata_notes(profile, self.games)
                    for path in notes:
                        self.logger.info("Wrote Steam note: %s", path)
                except Exception as exc:
                    notes = []
                    self.logger.warning("Shortcut write succeeded, but Steam notes failed: %s", exc)
                copied_count = len(copied)
                notes_count = len(notes)
                if steam_closed:
                    self.set_task_progress("Reopening Steam because this app closed it...", 5, 6)
                    steam_reopened = reopen_steam(steam_path)
                self.set_task_progress("Steam write finished; backups and logs are ready.", 6, 6)
                return added, updated, backup, copied_count, notes_count, compat_result, steam_closed, steam_reopened
            except Exception:
                if steam_closed:
                    try:
                        reopen_steam(steam_path)
                    except Exception as exc:
                        self.logger.warning("Steam was closed for writing but could not be reopened after an error: %s", exc)
                raise

        def done(result: tuple[int, int, Path | None, int, int, CompatToolWriteResult | None, bool, bool]) -> None:
            added, updated, backup, copied_count, notes_count, compat_result, steam_closed, steam_reopened = result
            profile_records = load_shortcuts(profile.shortcuts_path)
            mark_existing_shortcuts(self.games, profile_records)
            self.apply_existing_shortcut_choices(self.games, profile_records)
            self.refresh_all_game_rows()
            backup_text = str(backup) if backup else "No prior shortcuts.vdf existed, so no backup file was needed."
            steam_text = ""
            if steam_closed:
                steam_text = "\nSteam was closed automatically and reopened." if steam_reopened else "\nSteam was closed automatically, but could not be reopened."
            compat_text = ""
            if compat_result:
                if compat_result.tool:
                    compat_text = f"\nSteam Play compatibility: {self.compat_tool_display_name(compat_result.tool)} for {compat_result.applied} shortcut(s)."
                elif compat_result.cleared:
                    compat_text = f"\nSteam Play compatibility: forced tools cleared for {compat_result.cleared} shortcut(s)."
                else:
                    compat_text = "\nSteam Play compatibility: Steam default; no forced mappings needed clearing."
                if compat_result.backup:
                    compat_text += f"\nCompatibility config backup: {compat_result.backup}"
            messagebox.showinfo(
                __app_name__,
                f"Steam shortcuts written.\n\nAdded: {added}\nUpdated: {updated}\nArtwork files copied: {copied_count}\nSteam notes written: {notes_count}{compat_text}\n\nBackup: {backup_text}{steam_text}",
            )

        self.run_background("Writing Steam shortcuts", task, done, exclusive=True)

    def export_report(self, kind: str) -> None:
        if not self.games:
            messagebox.showwarning(__app_name__, "Scan games before exporting a report.")
            return
        initial = self.settings.last_export_dir or self.collection_path_var.get() or str(Path.home())
        ext = ".json" if kind == "json" else ".csv"
        path = filedialog.asksaveasfilename(
            title=f"Export scan report as {kind.upper()}",
            defaultextension=ext,
            initialdir=initial,
            filetypes=[(kind.upper(), f"*{ext}"), ("All files", "*.*")],
        )
        if not path:
            return
        destination = Path(path)
        if kind == "json":
            export_json(self.games, destination)
        else:
            export_csv(self.games, destination)
        self.settings.last_export_dir = str(destination.parent)
        self.save_settings_from_ui(log=False)
        self.logger.info("Exported scan report to %s", destination)

    def export_settings(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Export app settings",
            defaultextension=".json",
            filetypes=[("JSON", "*.json"), ("All files", "*.*")],
        )
        if path:
            self.save_settings_from_ui(log=False)
            self.settings_store.export_to(self.settings, Path(path))
            self.logger.info("Exported settings to %s", path)

    def import_settings(self) -> None:
        path = filedialog.askopenfilename(title="Import app settings", filetypes=[("JSON", "*.json"), ("All files", "*.*")])
        if not path:
            return
        self.settings = self.settings_store.import_from(Path(path))
        self.apply_settings_to_ui()
        self.artwork_search_cache.clear()
        self.artwork_title_cache.clear()
        self.load_persistent_artwork_search_cache()
        self.settings_store.save(self.settings)
        self.refresh_profiles()
        self.apply_game_columns()
        self.apply_sort_preset()
        self.apply_view_filter()
        self._build_style()
        self.build_menu_bar()
        self.apply_widget_theme()
        self.logger.info("Imported settings from %s", path)


def main() -> None:
    app = MainWindow()
    app.mainloop()
