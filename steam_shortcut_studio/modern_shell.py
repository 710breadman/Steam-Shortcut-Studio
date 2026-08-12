from __future__ import annotations

import logging
import os
import subprocess
import sys
import webbrowser
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, StringVar
from typing import Callable
from uuid import uuid4

import customtkinter as ctk

from . import __app_name__, __version__
from .artwork import copy_all_artwork_to_steam, download_asset
from .artwork_bulk_search import build_provider_searcher
from .artwork_queue_status import (
    artwork_plan_no_jobs_message,
    artwork_plan_selection_required_message,
    artwork_queue_submission_message,
)
from .artwork_review_workspace import (
    ArtworkReviewQueue,
    artwork_queue_progress_text,
    artwork_review_action_message,
    artwork_review_detail_text,
    artwork_review_empty_message,
    artwork_review_header_text,
    artwork_review_no_pending_message,
    build_artwork_review_rows,
    build_artwork_review_summary,
    review_result_slot_count,
)
from .artwork_search_service import ArtworkProviderSearchService
from .artwork_sources import ARTWORK_SOURCE_LABELS
from .bulk_artwork import ArtworkSearchMode, BulkArtworkCoordinator
from .image_validation import validate_artwork_file
from .job_queue import JobEvent, JobExecutionResult
from .jobs import JobKind, JobRecord, JobState, TERMINAL_JOB_STATES
from .library_controller import LibraryController, LibraryRow
from .library_edits import (
    OVERRIDE_FIELDS,
    build_manual_overrides,
    describe_override_changes,
    field_label,
    override_change_message,
)
from .library_store import ArtworkLock, LibraryStore, default_library_database
from .models import ArtworkAsset, DetectedGame
from .modern_library_view import format_size, initial_active_item_id
from .selection import SelectionState
from .settings_store import AppSettings, SettingsStore
from .shortcut_transactions import upsert_games_transactional
from .sources.epic import EpicManifestAdapter, default_epic_manifest_dir
from .sources.local import FolderScannerAdapter
from .sources.steam import SteamLibraryAdapter
from .steam_detection import (
    detect_steam_install,
    find_steam_profiles,
    is_steam_running,
    is_valid_steam_path,
    reopen_steam,
    shutdown_steam_for_write,
)
from .steamgrid import SteamGridDbClient
from .transaction_history import (
    list_artwork_transaction_history,
    list_transaction_history,
)
from .ui_library_adapter import (
    apply_locked_artwork,
    artwork_copy_skip_reason,
    game_from_library_row,
    native_steam_artwork_game_from_library_row,
    writable_game_from_library_row,
    writable_game_skip_reason,
)

LOGGER = logging.getLogger(__name__)
PACKAGE_ROOT = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_ROOT.parent


PALETTES = {
    "Ocean Blue": {"accent": "#1677ff", "hover": "#2f8cff", "selected": "#0f315f", "border": "#1d4f8f"},
    "Orion Purple": {"accent": "#7c3aed", "hover": "#8b5cf6", "selected": "#35205c", "border": "#6640a5"},
    "Forest Green": {"accent": "#12a66a", "hover": "#22bd7b", "selected": "#163f35", "border": "#26745c"},
    "Solar Amber": {"accent": "#d97706", "hover": "#f59e0b", "selected": "#4a3218", "border": "#8a5b1f"},
    "Rose": {"accent": "#db2777", "hover": "#ec4899", "selected": "#51223e", "border": "#8e3765"},
}

COLORS = {
    "window": "#07111f", "sidebar": "#081625", "panel": "#0b1b2c", "panel_alt": "#0d2135",
    "panel_soft": "#10263b", "line": "#1c3147", "text": "#f1f5f9", "muted": "#8fa3b8",
    "success": "#34c878", "warning": "#f5b942", "danger": "#ef5350",
}

NAV_ITEMS = [
    ("\u25a6", "Library"), ("\u2197", "Shortcuts"), ("\u25a7", "Artwork"), ("\u2261", "Metadata"),
    ("\u270e", "Tools"), ("\u2315", "Import / Scan"), ("\u25c8", "Backups"), ("\u2699", "Settings"),
    ("\u271a", "Extensions"), ("\u24d8", "About"),
]

FILTER_OPTIONS = ["All Games", "Steam", "Non-Steam", "Needs Review", "Customized", "Missing"]


def _monogram(title: str) -> str:
    parts = [p for p in title.split() if p]
    if not parts:
        return "??"
    if len(parts) == 1:
        return (parts[0][:2]).upper()
    return (parts[0][0] + parts[1][0]).upper()


class ModernShell(ctk.CTk):
    """Production-data modern shell: Library workspace + sidebar screens.

    Backed by the real ``LibraryController`` / ``LibraryStore`` (no mock
    games). Long-running work (source scans, Apply Changes, artwork search)
    runs on ``BackgroundJobQueue`` and is polled from the Tk thread via
    ``after`` per CODEX_START_HERE. Apply Changes writes real non-Steam
    shortcuts AND copies real locked artwork into Steam's grid folder, in
    one combined pass, through the same verified transaction services
    (``shortcut_transactions.upsert_games_transactional`` /
    ``artwork.copy_all_artwork_to_steam``) the legacy UI uses. Per-slot Auto
    Match / Replace perform real artwork search/download/validate and write
    the result to ``LibraryStore.set_artwork_lock`` (same safety model as
    Clear Slot: local cache + local SQLite only) — matching/locking a slot
    never touches the real Steam grid folder by itself; that only happens
    when Apply Changes runs. The bulk top-bar Auto-Art button remains
    intentionally gated: matching many games unattended needs a
    review-queue UI (like legacy's) that doesn't exist yet, and this UI
    must not claim success it cannot back up (see docs/UI_UX_TARGET.md:
    "No fake safety").
    """

    def __init__(
        self,
        database: Path | str | None = None,
        *,
        include_missing: bool = False,
        settings_store: SettingsStore | None = None,
    ) -> None:
        super().__init__(fg_color=COLORS["window"])
        self.title("Steam Shortcut Studio")
        self.geometry("1440x900")
        self.minsize(1100, 700)

        self.settings_store = settings_store or SettingsStore()
        self.settings: AppSettings = self.settings_store.load()
        self.include_missing = include_missing
        self.database_path = Path(database or default_library_database())
        self.store = LibraryStore(self.database_path)
        self.controller = LibraryController(self.store)

        self.accent_name = "Ocean Blue"
        self.palette = PALETTES[self.accent_name]
        self.nav = "Library"
        self.tab = "Artwork"
        self.search_query = ""
        self.filter_value = "All Games"
        self.sort_col = "title"
        self.sort_dir = True
        self.status_text = StringVar(value="Ready")
        self.row_frames: dict[str, ctk.CTkFrame] = {}
        self.row_checks: dict[str, ctk.CTkCheckBox] = {}
        self._ordered_ids: list[str] = []
        self._pending_action_jobs: dict[str, Callable[[JobEvent], None]] = {}
        self.review_queue = ArtworkReviewQueue()
        self._preview_images: list[ctk.CTkImage] = []

        self.controller.refresh(include_missing=self.include_missing)
        self._auto_select_first()

        self.grid_columnconfigure(0, minsize=222)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._build_sidebar()
        self._build_topbar()
        self.content = ctk.CTkFrame(self, fg_color="transparent")
        self.content.grid(row=1, column=1, padx=(6, 14), pady=(0, 8), sticky="nsew")
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_rowconfigure(0, weight=1)
        self._build_footer()
        self._render_content()

        self._closing = False
        self._poll_after_id: str | None = self.after(200, self._poll_jobs)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _on_close(self) -> None:
        """Stop polling and release worker threads before the window goes away.

        Without this, the repeating `after` callback fires against a
        half-destroyed widget tree, and `LibraryController`'s job queue keeps
        its workers alive -- which can leave the process running after the
        window has closed, mid-scan.
        """
        self._closing = True
        if self._poll_after_id is not None:
            try:
                self.after_cancel(self._poll_after_id)
            except Exception:  # noqa: BLE001 - already torn down
                pass
            self._poll_after_id = None
        try:
            self.controller.close(wait=False, cancel_pending=True)
        except Exception:  # noqa: BLE001 - shutdown must not raise
            LOGGER.debug("Library controller did not close cleanly.", exc_info=True)
        self.destroy()

    # ---------- font / small helpers ----------

    def _font(self, size: int, weight: str = "normal") -> ctk.CTkFont:
        return ctk.CTkFont(family="Segoe UI", size=size, weight=weight)

    def _auto_select_first(self) -> None:
        snapshot = self.controller.snapshot()
        item_id = initial_active_item_id(snapshot.rows, snapshot.active_item_id)
        if item_id is not None and item_id != snapshot.active_item_id:
            self.controller.set_active(item_id)

    def _set_status(self, message: str) -> None:
        self.status_text.set(message)

    # ---------- sidebar ----------

    def _build_sidebar(self) -> None:
        sidebar = ctk.CTkScrollableFrame(self, fg_color=COLORS["sidebar"], corner_radius=0)
        sidebar.grid(row=0, column=0, rowspan=2, sticky="nsew")
        sidebar.grid_columnconfigure(0, weight=1)
        self.sidebar = sidebar

        brand = ctk.CTkFrame(sidebar, fg_color="transparent")
        brand.grid(row=0, column=0, padx=18, pady=(20, 18), sticky="ew")
        ctk.CTkLabel(brand, text="\u25c9", text_color=self.palette["accent"], font=self._font(30, "bold")).pack(side="left", padx=(0, 10))
        title = ctk.CTkFrame(brand, fg_color="transparent")
        title.pack(side="left")
        ctk.CTkLabel(title, text="STEAM", anchor="w", font=self._font(14, "bold")).pack(fill="x")
        ctk.CTkLabel(title, text="SHORTCUT STUDIO", anchor="w", font=self._font(11, "bold")).pack(fill="x")

        self.nav_buttons: dict[str, ctk.CTkButton] = {}
        for index, (icon, label) in enumerate(NAV_ITEMS, start=1):
            button = ctk.CTkButton(
                sidebar, text=f"{icon}   {label}", anchor="w", height=40, corner_radius=9,
                fg_color="transparent", hover_color=COLORS["panel_soft"], text_color="#b7c5d4",
                font=self._font(13), command=lambda value=label: self._set_nav(value),
            )
            button.grid(row=index, column=0, padx=12, pady=2, sticky="ew")
            self.nav_buttons[label] = button
        self._refresh_nav_highlight()

        appearance = ctk.CTkFrame(sidebar, fg_color=COLORS["panel"], corner_radius=12)
        appearance.grid(row=11, column=0, padx=12, pady=(10, 8), sticky="ew")
        ctk.CTkLabel(appearance, text="APPEARANCE", anchor="w", text_color=COLORS["muted"], font=self._font(10, "bold")).pack(fill="x", padx=12, pady=(10, 6))
        chips = ctk.CTkFrame(appearance, fg_color="transparent")
        chips.pack(fill="x", padx=10, pady=(0, 10))
        self.swatch_buttons: dict[str, ctk.CTkButton] = {}
        for name, palette in PALETTES.items():
            swatch = ctk.CTkButton(
                chips, text="", width=22, height=22, corner_radius=11, fg_color=palette["accent"],
                hover_color=palette["hover"], border_width=0, command=lambda value=name: self._set_accent(value),
            )
            swatch.pack(side="left", padx=3)
            self.swatch_buttons[name] = swatch
        self._refresh_swatch_borders()

        self.library_card = ctk.CTkFrame(sidebar, fg_color=COLORS["panel"], corner_radius=12)
        self.library_card.grid(row=12, column=0, padx=12, pady=(0, 16), sticky="ew")
        self._render_library_card()

    def _render_library_card(self) -> None:
        for child in self.library_card.winfo_children():
            child.destroy()
        rows = self.controller.snapshot().rows
        total_bytes = sum(row.size_bytes for row in rows)
        path_label = self.settings.steam_path or "No Steam folder set"
        ctk.CTkLabel(self.library_card, text="\u25b1  Steam Library", anchor="w", font=self._font(12, "bold")).pack(fill="x", padx=12, pady=(12, 2))
        ctk.CTkLabel(self.library_card, text=path_label, anchor="w", text_color=COLORS["muted"], font=self._font(10)).pack(fill="x", padx=12)
        ctk.CTkLabel(
            self.library_card, text=f"{format_size(total_bytes)} across {len(rows)} tracked game(s)",
            anchor="w", text_color=COLORS["muted"], font=self._font(10),
        ).pack(fill="x", padx=12, pady=(10, 12))

    def _set_nav(self, label: str) -> None:
        self.nav = label
        self._refresh_nav_highlight()
        self._render_content()

    def _refresh_nav_highlight(self) -> None:
        for label, button in self.nav_buttons.items():
            selected = label == self.nav
            button.configure(
                fg_color=self.palette["selected"] if selected else "transparent",
                border_width=1 if selected else 0, border_color=self.palette["border"],
                text_color=COLORS["text"] if selected else "#b7c5d4",
                font=self._font(13, "bold" if selected else "normal"),
            )

    def _set_accent(self, name: str) -> None:
        self.accent_name = name
        self.palette = PALETTES[name]
        self._refresh_nav_highlight()
        self._refresh_swatch_borders()
        self._render_content()

    def _refresh_swatch_borders(self) -> None:
        for name, button in self.swatch_buttons.items():
            button.configure(border_width=2 if name == self.accent_name else 0, border_color="#dceeff")

    # ---------- topbar ----------

    def _build_topbar(self) -> None:
        topbar = ctk.CTkFrame(self, fg_color=COLORS["panel"], corner_radius=12)
        topbar.grid(row=0, column=1, padx=(6, 14), pady=(12, 8), sticky="ew")

        actions = [
            ("\u2315", "Scan", "Folders & libraries", self._open_import_scan),
            ("\u21bb", "Refresh Metadata", "Reload stored library", self._refresh_metadata),
            ("\u2726", "Auto-Art", "Find & match artwork", self._start_bulk_auto_art),
            ("\u25eb", "Preview", "Preview changes", self._preview_changes),
        ]
        for column, (icon, title, subtitle, command) in enumerate(actions):
            button = ctk.CTkButton(
                topbar, text=f"{icon}  {title}\n    {subtitle}", anchor="w", width=170, height=52,
                corner_radius=9, fg_color="transparent", hover_color=COLORS["panel_soft"],
                text_color=COLORS["text"], font=self._font(12, "bold"), command=command,
            )
            button.grid(row=0, column=column, padx=(8 if column else 10, 2), pady=8)

        ctk.CTkLabel(topbar, text="SAFE MODE", text_color=COLORS["warning"], font=self._font(10, "bold")).grid(row=0, column=4, padx=12)
        self.apply_button = ctk.CTkButton(
            topbar, text="\u2b06  Apply Changes\n    Safely", width=210, height=52, corner_radius=9,
            fg_color=self.palette["accent"], hover_color=self.palette["hover"], text_color="#fff",
            font=self._font(12, "bold"), command=self._apply_changes,
        )
        self.apply_button.grid(row=0, column=5, padx=(4, 10), pady=8)

    def _open_import_scan(self) -> None:
        self._set_nav("Import / Scan")

    def _refresh_metadata(self) -> None:
        self.controller.refresh(include_missing=self.include_missing)
        self._render_library_card()
        self._render_content()
        self._set_status("Reloaded stored library from disk.")

    def _start_bulk_auto_art(self) -> None:
        """Queue artwork searches for the selected rows through the coordinator.

        Results are never locked automatically: `ArtworkMatchPolicy` sends
        everything the real providers produce to `NEEDS_REVIEW` (see
        `artwork_bulk_search`'s placeholder scores), so each finished job lands
        in the Artwork screen's review queue for an explicit decision.
        """
        if not self._artwork_sources_enabled():
            messagebox.showinfo(
                "Auto-Art",
                "No artwork source is enabled. Turn on at least one source (SteamGridDB, "
                "Official Steam, Wikimedia, or RAWG) on the Settings screen first.",
            )
            return

        item_ids = tuple(row.item_id for row in self.controller.selected_rows())
        if not item_ids:
            messagebox.showinfo("Auto-Art", artwork_plan_selection_required_message())
            return
        if self._submit_artwork_jobs(item_ids) == 0:
            messagebox.showinfo("Auto-Art", artwork_plan_no_jobs_message())
            return
        self._set_nav("Artwork")

    def _submit_artwork_jobs(self, item_ids: tuple[str, ...]) -> int:
        """Submit `item_ids` through `BulkArtworkCoordinator`; return job count.

        Submission scope is an explicit `SelectionState` built from the passed
        IDs rather than the live table selection, so a retry of one row cannot
        widen into whatever happens to be selected at that moment.
        """
        client = SteamGridDbClient(self.settings.steamgriddb_api_key, Path(self.settings.cache_dir), LOGGER)
        provider_service = ArtworkProviderSearchService(LOGGER)
        row_map = self.controller.row_map()

        def game_lookup(item_id: str) -> DetectedGame | None:
            row = row_map.get(item_id)
            return game_from_library_row(row) if row is not None else None

        searcher = build_provider_searcher(
            game_lookup=game_lookup,
            collect_assets=provider_service.collect_assets,
            client=client,
            cache_dir=Path(self.settings.cache_dir),
            enabled_sources=self.settings.artwork_sources,
            rawg_api_key=self.settings.rawg_api_key,
            missing_game_reason="Stored row is no longer visible in the library.",
            logger=LOGGER,
        )

        scope = SelectionState()
        scope.replace(item_ids)
        submission = BulkArtworkCoordinator(self.controller.job_queue).submit_selected(
            scope,
            list(item_ids),
            self.controller.bulk_artwork_items(),
            searcher,
            mode=ArtworkSearchMode.ALL_UNLOCKED,
        )
        for job in submission.jobs:
            self.review_queue.track(job.job_id, job.item_id)
        if submission.jobs:
            self._set_status(
                artwork_queue_submission_message(len(submission.jobs), "artwork search")
            )
        return len(submission.jobs)

    def _apply_scope_rows(self) -> tuple[LibraryRow, ...]:
        rows = self.controller.selected_rows() or self.controller.snapshot().rows
        return tuple(rows)

    def _partition_apply_rows(
        self, rows: tuple[LibraryRow, ...]
    ) -> tuple[
        list[tuple[LibraryRow, DetectedGame]],
        list[tuple[LibraryRow, str]],
        list[tuple[LibraryRow, str]],
        int,
        int,
    ]:
        combined: list[tuple[LibraryRow, DetectedGame]] = []
        shortcut_skipped: list[tuple[LibraryRow, str]] = []
        artwork_skipped: list[tuple[LibraryRow, str]] = []
        shortcut_count = 0
        artwork_count = 0
        for row in rows:
            game = writable_game_from_library_row(row)
            if game is not None:
                shortcut_count += 1
            else:
                shortcut_skipped.append((row, writable_game_skip_reason(row)))

            locks = [
                lock for lock in self.store.list_artwork_locks(row.item_id)
                if lock.local_path and Path(lock.local_path).is_file()
            ]
            art_reason = artwork_copy_skip_reason(row, locks)
            if not art_reason:
                artwork_count += 1
                if game is None:
                    game = native_steam_artwork_game_from_library_row(row)
                if game is not None:
                    apply_locked_artwork(game, locks)
            else:
                artwork_skipped.append((row, art_reason))

            if game is not None:
                combined.append((row, game))
        return combined, shortcut_skipped, artwork_skipped, shortcut_count, artwork_count

    def _preview_changes(self) -> None:
        rows = self._apply_scope_rows()
        combined, shortcut_skipped, artwork_skipped, shortcut_count, artwork_count = (
            self._partition_apply_rows(rows)
        )
        lines = [
            f"{shortcut_count} shortcut(s) will be added or updated in shortcuts.vdf.",
            f"{artwork_count} game(s) have locked artwork that will be copied into Steam's grid folder.",
        ]
        if shortcut_skipped:
            lines.append(f"\n{len(shortcut_skipped)} game(s) skipped for shortcuts:")
            for row, reason in shortcut_skipped[:20]:
                lines.append(f"  \u2022 {row.title}: {reason}")
            if len(shortcut_skipped) > 20:
                lines.append(f"  ...and {len(shortcut_skipped) - 20} more.")
        if artwork_skipped:
            lines.append(f"\n{len(artwork_skipped)} game(s) skipped for artwork:")
            for row, reason in artwork_skipped[:20]:
                lines.append(f"  \u2022 {row.title}: {reason}")
            if len(artwork_skipped) > 20:
                lines.append(f"  ...and {len(artwork_skipped) - 20} more.")
        lines.append("\nNo Steam files have been modified. This is a read-only preview.")
        messagebox.showinfo("Preview changes", "\n".join(lines))

    def _apply_changes(self) -> None:
        rows = self._apply_scope_rows()
        combined, shortcut_skipped, artwork_skipped, shortcut_count, artwork_count = (
            self._partition_apply_rows(rows)
        )
        if not combined:
            messagebox.showinfo(
                "Nothing to apply",
                "No game(s) in scope are eligible for a Steam shortcut write or an "
                "artwork copy. Use Preview to see why.",
            )
            return

        steam_path_value = self.settings.steam_path
        if not steam_path_value:
            messagebox.showerror(
                "Apply Changes",
                "No Steam folder is configured. Use Import / Scan to detect or choose "
                "your Steam install first.",
            )
            return
        steam_path = Path(steam_path_value)

        lines = [
            f"{shortcut_count} shortcut(s) will be added or updated in shortcuts.vdf.",
            f"{artwork_count} game(s) will have locked artwork copied into Steam's grid folder.",
        ]
        if shortcut_skipped or artwork_skipped:
            lines.append(
                f"{len(shortcut_skipped)} skipped for shortcuts, "
                f"{len(artwork_skipped)} skipped for artwork (see Preview for details)."
            )
        if is_steam_running():
            lines.append(
                "\nSteam is currently running and will be closed automatically, "
                "then reopened once the write finishes."
            )
        lines.append(
            "\nA backup is created and verified automatically for every file changed; "
            "any failing file is rolled back individually and Steam is left untouched."
        )
        if not messagebox.askyesno("Apply Changes", "\n".join(lines)):
            return

        games = [game for _, game in combined]
        job_id = f"apply-changes-{uuid4().hex[:12]}"
        record = JobRecord(
            job_id=job_id,
            item_id="apply:changes",
            kind=JobKind.APPLY,
            message=f"Queued write of {shortcut_count} shortcut(s) and {artwork_count} artwork set(s)",
        )
        self._pending_action_jobs[job_id] = self._handle_apply_job_finished
        self.apply_button.configure(state="disabled")
        self.controller.job_queue.submit(
            record,
            lambda job, token, report_progress: self._apply_changes_job(
                steam_path, games, report_progress
            ),
        )
        self._set_status(
            f"Applying {shortcut_count} shortcut(s) and {artwork_count} artwork set(s) to Steam\u2026"
        )

    def _apply_changes_job(self, steam_path: Path, games: list, report_progress) -> JobExecutionResult:
        steam_closed = False
        try:
            report_progress(0.05, "Checking Steam status\u2026")
            if is_valid_steam_path(steam_path):
                steam_closed = shutdown_steam_for_write(steam_path)
            elif is_steam_running():
                raise RuntimeError(
                    "Steam is running, but the configured Steam folder is not valid. "
                    "Choose a valid Steam folder in Import / Scan before writing shortcuts."
                )
            report_progress(0.2, "Finding Steam profile\u2026")
            profiles = find_steam_profiles(steam_path)
            if not profiles:
                raise RuntimeError(f"No Steam user profile found under {steam_path}.")
            profile = profiles[0]

            report_progress(0.35, "Writing shortcut(s)\u2026")
            shortcut_result = upsert_games_transactional(
                profile,
                games,
                update_existing=self.settings.update_existing_shortcuts,
                default_tags=list(self.settings.default_tags),
            )

            report_progress(0.6, "Copying artwork into Steam's grid folder\u2026")
            artwork_failures: list[tuple[str, str]] = []
            copied = copy_all_artwork_to_steam(
                games,
                profile,
                error_handler=lambda game, exc: artwork_failures.append((game.display_title, str(exc))),
            )
            artwork_attempted = sum(
                1 for game in games
                if game.selected and (game.is_managed_non_steam or game.is_native_steam_game)
            )

            if steam_closed:
                report_progress(0.9, "Reopening Steam\u2026")
                reopen_steam(steam_path)
            return JobExecutionResult(
                state=JobState.SUCCEEDED,
                result={
                    "added": shortcut_result.added,
                    "updated": shortcut_result.updated,
                    "backup": str(shortcut_result.backup) if shortcut_result.backup else "",
                    "profile": profile.display_name,
                    "artwork_files_copied": len(copied),
                    "artwork_attempted": artwork_attempted,
                    "artwork_failed": len(artwork_failures),
                    "artwork_failures": artwork_failures,
                },
                message=(
                    f"Wrote {shortcut_result.added} new and {shortcut_result.updated} updated "
                    f"shortcut(s); artwork copied for {artwork_attempted - len(artwork_failures)} "
                    f"of {artwork_attempted} game(s)."
                ),
            )
        except Exception:
            if steam_closed:
                try:
                    reopen_steam(steam_path)
                except Exception:
                    LOGGER.warning(
                        "Steam was closed for writing but could not be reopened.", exc_info=True
                    )
            raise

    def _handle_apply_job_finished(self, event: JobEvent) -> None:
        self.apply_button.configure(state="normal")
        if event.state is JobState.SUCCEEDED:
            added = event.result.get("added", 0)
            updated = event.result.get("updated", 0)
            backup_path = event.result.get("backup")
            if not added and not updated:
                backup = "No changes were needed — nothing to write."
            elif backup_path:
                backup = backup_path
            else:
                backup = "No prior shortcuts.vdf existed, so no backup was needed."

            artwork_attempted = event.result.get("artwork_attempted", 0)
            artwork_failed = event.result.get("artwork_failed", 0)
            artwork_copied = event.result.get("artwork_files_copied", 0)
            artwork_failures = event.result.get("artwork_failures") or []

            lines = [
                f"Added: {added}",
                f"Updated: {updated}",
                f"Steam profile: {event.result.get('profile', '')}",
                f"Backup: {backup}",
            ]
            if artwork_attempted:
                ok = artwork_attempted - artwork_failed
                lines.append(
                    f"\nArtwork: copied for {ok} of {artwork_attempted} game(s) "
                    f"({artwork_copied} file(s) written)."
                )
                if artwork_failed:
                    lines.append(f"{artwork_failed} game(s) failed artwork copy:")
                    for title, reason in artwork_failures[:10]:
                        lines.append(f"  • {title}: {reason}")
                    if artwork_failed > 10:
                        lines.append(f"  ...and {artwork_failed - 10} more.")
            lines.append("\nSee the Backups screen for the full transaction record.")
            self._set_status(event.message or "Changes applied.")
            messagebox.showinfo("Apply Changes", "\n".join(lines))
        else:
            self._set_status(f"Apply Changes failed: {event.error or event.message}")
            messagebox.showerror(
                "Apply Changes failed",
                f"{event.error or event.message}\n\n"
                "Nothing is left partially written: any staged shortcuts.vdf write is "
                "automatically rolled back on verification failure, and any artwork "
                "file that started writing is rolled back individually too. The "
                "attempt is recorded on the Backups screen.",
            )

    # ---------- footer ----------

    def _build_footer(self) -> None:
        footer = ctk.CTkFrame(self, fg_color=COLORS["sidebar"], corner_radius=0, height=28)
        footer.grid(row=2, column=1, sticky="ew")
        footer.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(footer, textvariable=self.status_text, anchor="w", text_color=COLORS["muted"], font=self._font(10)).grid(row=0, column=0, padx=14, pady=5, sticky="ew")
        self.cancel_button = ctk.CTkButton(
            footer, text="Cancel", height=20, width=64, corner_radius=6, font=self._font(9, "bold"),
            fg_color="transparent", border_width=1, border_color=COLORS["line"],
            text_color=COLORS["muted"], hover_color=COLORS["line"], command=self._cancel_running_jobs,
        )
        self.cancel_button.grid(row=0, column=1, padx=(0, 10))
        self.cancel_button.grid_remove()
        steam_state = "Steam path set" if self.settings.steam_path else "Steam path not configured"
        ctk.CTkLabel(footer, text=f"\u25cf  {steam_state}", text_color=COLORS["success"] if self.settings.steam_path else COLORS["warning"], font=self._font(10)).grid(row=0, column=2, padx=14)

    def _running_job_ids(self) -> tuple[str, ...]:
        """Job IDs this shell started that have not reached a terminal state."""
        tracked = set(self._pending_action_jobs) | set(self.review_queue.job_ids)
        return tuple(
            job_id
            for job_id in tracked
            if (record := self.controller.job_queue.get(job_id)) is not None
            and record.state not in TERMINAL_JOB_STATES
        )

    def _refresh_cancel_button(self) -> None:
        if not hasattr(self, "cancel_button"):
            return
        if self._running_job_ids():
            self.cancel_button.grid()
        else:
            self.cancel_button.grid_remove()

    def _cancel_running_jobs(self) -> None:
        """Ask in-flight jobs to stop at their next safe checkpoint.

        Cancellation is cooperative: `BulkArtworkCoordinator` and the provider
        searcher check the token between candidates, so a search stops without
        leaving a half-written cache entry. An Apply Changes job that has
        already started writing is *not* interrupted mid-transaction -- the
        transaction services own that, and their rollback is what makes a
        failed write safe.
        """
        running = self._running_job_ids()
        if not running:
            return
        for job_id in running:
            self.controller.job_queue.cancel(job_id)
        self._set_status(f"Cancel requested for {len(running)} job(s). Stopping at the next safe checkpoint\u2026")

    # ---------- content dispatch ----------

    def _render_content(self) -> None:
        for child in self.content.winfo_children():
            child.destroy()
        # Tk drops an image the moment nothing references it, so previews for
        # the screen being replaced are released here and rebuilt below.
        self._preview_images.clear()
        if self.nav == "Library":
            self._build_library_screen()
        else:
            builder = {
                "Shortcuts": self._build_shortcuts_screen,
                "Artwork": self._build_artwork_screen,
                "Metadata": self._build_metadata_screen,
                "Tools": self._build_tools_screen,
                "Import / Scan": self._build_import_screen,
                "Backups": self._build_backups_screen,
                "Settings": self._build_settings_screen,
                "Extensions": self._build_extensions_screen,
                "About": self._build_about_screen,
            }[self.nav]
            builder()

    def _simple_screen(self, title: str, subtitle: str):
        card = ctk.CTkFrame(self.content, fg_color=COLORS["panel"], corner_radius=12)
        card.grid(row=0, column=0, sticky="nsew")
        card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(card, text=title, anchor="w", font=self._font(18, "bold")).grid(row=0, column=0, padx=20, pady=(20, 2), sticky="ew")
        ctk.CTkLabel(card, text=subtitle, anchor="w", text_color=COLORS["muted"], font=self._font(12)).grid(row=1, column=0, padx=20, pady=(0, 14), sticky="ew")
        body = ctk.CTkScrollableFrame(card, fg_color="transparent")
        body.grid(row=2, column=0, padx=12, pady=(0, 16), sticky="nsew")
        body.grid_columnconfigure(0, weight=1)
        card.grid_rowconfigure(2, weight=1)
        return body

    def _list_row(self, parent, row: int, icon: str, title: str, detail: str, action_label: str | None, command=None) -> None:
        item = ctk.CTkFrame(parent, fg_color=COLORS["panel_alt"], border_width=1, border_color=COLORS["line"], corner_radius=10)
        item.grid(row=row, column=0, sticky="ew", pady=4)
        item.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(item, text=icon, width=34, height=34, fg_color=COLORS["panel_soft"], corner_radius=8, font=self._font(14)).grid(row=0, column=0, padx=(12, 12), pady=10)
        text = ctk.CTkFrame(item, fg_color="transparent")
        text.grid(row=0, column=1, sticky="ew", pady=6)
        ctk.CTkLabel(text, text=title, anchor="w", font=self._font(13, "bold")).pack(fill="x")
        ctk.CTkLabel(text, text=detail, anchor="w", text_color=COLORS["muted"], font=self._font(11)).pack(fill="x")
        if action_label:
            ctk.CTkButton(
                item, text=action_label, height=30, width=100, corner_radius=7, font=self._font(11, "bold"),
                fg_color=self.palette["accent"], hover_color=self.palette["hover"], command=command,
            ).grid(row=0, column=2, padx=12)

    # ---------- Library screen ----------

    def _build_library_screen(self) -> None:
        self.content.grid_columnconfigure(0, weight=6)
        self.content.grid_columnconfigure(1, weight=5)

        library_panel = ctk.CTkFrame(self.content, fg_color=COLORS["panel"], corner_radius=12)
        library_panel.grid(row=0, column=0, padx=(0, 4), sticky="nsew")
        library_panel.grid_columnconfigure(0, weight=1)
        library_panel.grid_rowconfigure(2, weight=1)

        controls = ctk.CTkFrame(library_panel, fg_color="transparent")
        controls.grid(row=0, column=0, padx=12, pady=(12, 8), sticky="ew")
        controls.grid_columnconfigure(0, weight=1)
        search = ctk.CTkEntry(controls, placeholder_text="Search games...", height=36, corner_radius=8, border_color=COLORS["line"], fg_color=COLORS["window"])
        search.insert(0, self.search_query)
        search.grid(row=0, column=0, padx=(0, 8), sticky="ew")
        search.bind("<KeyRelease>", lambda e: self._on_search(search.get()))
        ctk.CTkOptionMenu(
            controls, values=FILTER_OPTIONS, width=150, height=36, fg_color=COLORS["panel_soft"],
            button_color=COLORS["panel_soft"], button_hover_color=self.palette["selected"],
            command=self._on_filter,
        ).grid(row=0, column=1)

        header = ctk.CTkFrame(library_panel, fg_color=COLORS["window"], corner_radius=7)
        header.grid(row=1, column=0, padx=12, sticky="ew")
        cols = [("", 0, None), ("TITLE", 4, "title"), ("SOURCE", 2, None), ("PLATFORM", 2, None), ("LAST PLAYED", 2, None), ("SIZE", 1, "size")]
        for column, (label, weight, sort_key) in enumerate(cols):
            header.grid_columnconfigure(column, weight=weight, minsize=32 if column == 0 else 60)
            text = label + (" \u2191" if sort_key and self.sort_col == sort_key and self.sort_dir else " \u2193" if sort_key and self.sort_col == sort_key else "")
            lbl = ctk.CTkLabel(header, text=text, anchor="w", text_color=COLORS["muted"], font=self._font(10, "bold"))
            lbl.grid(row=0, column=column, padx=6, pady=7, sticky="ew")
            if sort_key:
                lbl.bind("<Button-1>", lambda e, key=sort_key: self._on_sort(key))

        rows_frame = ctk.CTkScrollableFrame(library_panel, fg_color="transparent")
        rows_frame.grid(row=2, column=0, padx=8, pady=6, sticky="nsew")
        rows_frame.grid_columnconfigure(0, weight=1)

        rows = self._visible_rows()
        self._ordered_ids = [r.item_id for r in rows]
        self.row_frames.clear()
        self.row_checks.clear()
        if rows:
            for row in rows:
                self._add_game_row(rows_frame, row)
        else:
            self._build_empty_library_state(rows_frame)

        selection = self.controller.snapshot()
        if selection.selected_count:
            bulk = ctk.CTkFrame(library_panel, fg_color=COLORS["panel_soft"], corner_radius=9)
            bulk.grid(row=3, column=0, padx=12, pady=(4, 10), sticky="ew")
            ctk.CTkLabel(bulk, text=f"{selection.selected_count} selected", font=self._font(11, "bold")).pack(side="left", padx=12, pady=8)
            for label, command in [
                ("Scan Selected", lambda: self._set_nav("Import / Scan")),
                ("Find Art", self._start_bulk_auto_art),
                ("Refresh Metadata", self._refresh_metadata),
                ("Preview", self._preview_changes),
            ]:
                ctk.CTkButton(
                    bulk, text=label, height=28, width=110, corner_radius=7, font=self._font(10, "bold"),
                    fg_color=self.palette["accent"] if label == "Find Art" else COLORS["panel"],
                    hover_color=self.palette["hover"] if label == "Find Art" else COLORS["line"], command=command,
                ).pack(side="left", padx=3, pady=6)
            ctk.CTkButton(
                bulk, text="Clear", height=28, width=70, corner_radius=7, font=self._font(10, "bold"),
                fg_color="transparent", hover_color=COLORS["line"], text_color=COLORS["muted"],
                command=self._clear_selection,
            ).pack(side="left", padx=3)

        footer_row = ctk.CTkFrame(library_panel, fg_color="transparent")
        footer_row.grid(row=4, column=0, padx=12, pady=(4, 10), sticky="ew")
        ctk.CTkLabel(footer_row, text=f"{len(rows)} game(s)", text_color=COLORS["muted"], font=self._font(11)).pack(side="left")

        self._build_inspector()

    def _build_empty_library_state(self, parent) -> None:
        """Say what to do next, rather than showing an unexplained empty table.

        Distinguishes an empty library from a filter that hides everything --
        telling a first-run user to "clear the search" would be useless advice,
        and telling someone with 200 hidden games to "scan a source" would be
        wrong.
        """
        total = len(self.controller.snapshot().rows)
        card = ctk.CTkFrame(parent, fg_color="transparent")
        card.grid(row=0, column=0, sticky="ew", pady=40)
        card.grid_columnconfigure(0, weight=1)

        if total:
            ctk.CTkLabel(
                card, text="No games match this view", font=self._font(15, "bold"),
            ).grid(row=0, column=0, pady=(0, 6))
            ctk.CTkLabel(
                card,
                text=f"{total} game(s) are in your library but hidden by the current search or filter.",
                text_color=COLORS["muted"], font=self._font(11), wraplength=420,
            ).grid(row=1, column=0, pady=(0, 14))
            ctk.CTkButton(
                card, text="Clear search and filter", height=32, width=190, corner_radius=7,
                font=self._font(11, "bold"), fg_color=self.palette["accent"],
                hover_color=self.palette["hover"], command=self._clear_view_filters,
            ).grid(row=2, column=0)
            return

        ctk.CTkLabel(card, text="Your library is empty", font=self._font(15, "bold")).grid(row=0, column=0, pady=(0, 6))
        ctk.CTkLabel(
            card,
            text=(
                "Scan a source to bring your games in. Scanning only reads — it writes "
                "to this app's own database, never to Steam or your games."
            ),
            text_color=COLORS["muted"], font=self._font(11), wraplength=420,
        ).grid(row=1, column=0, pady=(0, 14))
        buttons = ctk.CTkFrame(card, fg_color="transparent")
        buttons.grid(row=2, column=0)
        for label, command, accent in [
            ("Scan Steam", self._scan_steam, True),
            ("Scan Epic", self._scan_epic, False),
            ("Scan a folder", self._scan_folder, False),
        ]:
            ctk.CTkButton(
                buttons, text=label, height=32, width=130, corner_radius=7,
                font=self._font(11, "bold"),
                fg_color=self.palette["accent"] if accent else "transparent",
                border_width=0 if accent else 1, border_color=COLORS["line"],
                hover_color=self.palette["hover"] if accent else COLORS["line"],
                command=command,
            ).pack(side="left", padx=4)

    def _clear_view_filters(self) -> None:
        self.search_query = ""
        self.filter_value = "All Games"
        self._render_content()

    def _visible_rows(self) -> list[LibraryRow]:
        rows = list(self.controller.snapshot().rows)
        query = self.search_query.strip().casefold()
        if query:
            rows = [r for r in rows if query in r.title.casefold()]
        if self.filter_value == "Steam":
            rows = [r for r in rows if r.source == "steam"]
        elif self.filter_value == "Non-Steam":
            rows = [r for r in rows if r.source != "steam"]
        elif self.filter_value == "Needs Review":
            rows = [r for r in rows if r.status == "review"]
        elif self.filter_value == "Customized":
            rows = [r for r in rows if r.status == "customized"]
        elif self.filter_value == "Missing":
            rows = [r for r in rows if r.status == "missing"]
        reverse = not self.sort_dir
        if self.sort_col == "size":
            rows.sort(key=lambda r: r.size_bytes, reverse=reverse)
        else:
            rows.sort(key=lambda r: r.title.casefold(), reverse=reverse)
        return rows

    def _on_search(self, value: str) -> None:
        self.search_query = value
        self._render_content()

    def _on_filter(self, value: str) -> None:
        self.filter_value = value
        self._render_content()

    def _on_sort(self, key: str) -> None:
        if self.sort_col == key:
            self.sort_dir = not self.sort_dir
        else:
            self.sort_col, self.sort_dir = key, True
        self._render_content()

    def _clear_selection(self) -> None:
        self.controller.clear_selection()
        self._render_content()

    def _add_game_row(self, parent, row: LibraryRow) -> None:
        snapshot = self.controller.snapshot()
        active = row.item_id == snapshot.active_item_id
        selected = row.item_id in snapshot.selected_ids
        frame = ctk.CTkFrame(
            parent, fg_color=self.palette["selected"] if active else COLORS["panel_alt"],
            corner_radius=8, border_width=1, border_color=self.palette["border"] if active else COLORS["line"],
        )
        frame.grid(sticky="ew", padx=2, pady=3)
        for col, weight in [(1, 4), (2, 2), (3, 2), (4, 2), (5, 1)]:
            frame.grid_columnconfigure(col, weight=weight, minsize=60)

        checkbox = ctk.CTkCheckBox(
            frame, text="", width=20, checkbox_width=18, checkbox_height=18,
            fg_color=self.palette["accent"], hover_color=self.palette["hover"],
            command=lambda item=row.item_id: self._toggle_selected(item),
        )
        checkbox.grid(row=0, column=0, padx=(8, 2), pady=9)
        if selected:
            checkbox.select()

        title_lbl = ctk.CTkLabel(frame, text=row.title, anchor="w", font=self._font(11, "bold"))
        title_lbl.grid(row=0, column=1, padx=6, pady=9, sticky="ew")
        title_lbl.bind("<Button-1>", lambda e, item=row.item_id: self._activate(item))

        last_played = "\u2014"
        values = [row.source.title(), row.platform.title() or "PC", last_played, format_size(row.size_bytes)]
        for column, value in enumerate(values, start=2):
            lbl = ctk.CTkLabel(frame, text=value, anchor="w", text_color="#b8c6d5", font=self._font(10))
            lbl.grid(row=0, column=column, padx=6, pady=9, sticky="ew")
            lbl.bind("<Button-1>", lambda e, item=row.item_id: self._activate(item))

        self.row_frames[row.item_id] = frame
        self.row_checks[row.item_id] = checkbox

    def _toggle_selected(self, item_id: str) -> None:
        snapshot = self.controller.snapshot()
        self.controller.set_selected(item_id, item_id not in snapshot.selected_ids)
        self._render_content()

    def _activate(self, item_id: str) -> None:
        self.controller.set_active(item_id)
        self.tab = "Artwork"
        self._render_content()

    # ---------- inspector ----------

    def _build_inspector(self) -> None:
        inspector = ctk.CTkFrame(self.content, fg_color=COLORS["panel"], corner_radius=12)
        inspector.grid(row=0, column=1, padx=(4, 0), sticky="nsew")
        inspector.grid_columnconfigure(0, weight=1)
        inspector.grid_rowconfigure(2, weight=1)

        row_map = self.controller.row_map()
        active_id = self.controller.snapshot().active_item_id
        row = row_map.get(active_id) if active_id else None

        heading = ctk.CTkFrame(inspector, fg_color="transparent")
        heading.grid(row=0, column=0, padx=14, pady=(14, 8), sticky="ew")
        heading.grid_columnconfigure(1, weight=1)
        if row is None:
            ctk.CTkLabel(heading, text="No game selected", font=self._font(16, "bold")).grid(row=0, column=0, sticky="w")
            return

        ctk.CTkLabel(
            heading, text=_monogram(row.title), width=52, height=52, fg_color=COLORS["panel_alt"],
            corner_radius=9, font=self._font(12, "bold"),
        ).grid(row=0, column=0, rowspan=2, padx=(0, 12))
        ctk.CTkLabel(heading, text=row.title, anchor="w", font=self._font(19, "bold")).grid(row=0, column=1, sticky="ew")
        detail = f"{row.source.title()} \u2022 {row.status.title()}" + (f" \u2022 {row.external_id}" if row.external_id else "")
        ctk.CTkLabel(heading, text=detail, anchor="w", text_color=COLORS["muted"], font=self._font(10)).grid(row=1, column=1, sticky="ew")

        tab_bar = ctk.CTkFrame(inspector, fg_color=COLORS["window"], corner_radius=9)
        tab_bar.grid(row=1, column=0, padx=14, pady=(0, 8), sticky="ew")
        for name in ["Artwork", "Details", "Metadata", "Local Files"]:
            active_tab = name == self.tab
            ctk.CTkButton(
                tab_bar, text=name, height=30, width=1, corner_radius=6, font=self._font(11, "bold"),
                fg_color=self.palette["accent"] if active_tab else "transparent",
                text_color="#fff" if active_tab else COLORS["muted"], hover_color=self.palette["hover"],
                command=lambda value=name: self._set_tab(value),
            ).pack(side="left", expand=True, fill="x", padx=2, pady=2)

        body = ctk.CTkScrollableFrame(inspector, fg_color="transparent")
        body.grid(row=2, column=0, padx=10, pady=(0, 10), sticky="nsew")
        body.grid_columnconfigure(0, weight=1)

        if self.tab == "Artwork":
            self._build_artwork_tab(body, row)
        elif self.tab == "Details":
            self._build_details_tab(body, row)
        elif self.tab == "Metadata":
            self._build_kv_rows(body, [
                ("Title", row.title), ("Source", row.source), ("External ID", row.external_id or "\u2014"),
                ("Version", row.version or "\u2014"), ("Overridden fields", ", ".join(sorted(row.overridden_fields)) or "None"),
            ])
        elif self.tab == "Local Files":
            self._build_kv_rows(body, [("Install path", row.install_path or "\u2014"), ("Present on disk", str(row.is_present))])

    def _set_tab(self, name: str) -> None:
        self.tab = name
        self._render_content()

    def _build_kv_rows(self, parent, rows: list[tuple[str, str]]) -> None:
        for index, (label, value) in enumerate(rows):
            card = ctk.CTkFrame(parent, fg_color=COLORS["panel_alt"], border_width=1, border_color=COLORS["line"], corner_radius=8)
            card.grid(row=index, column=0, sticky="ew", pady=4)
            card.grid_columnconfigure(1, weight=1)
            ctk.CTkLabel(card, text=label, anchor="w", text_color=COLORS["muted"], font=self._font(11)).grid(row=0, column=0, padx=12, pady=8, sticky="w")
            ctk.CTkLabel(card, text=value, anchor="e", font=self._font(11, "bold")).grid(row=0, column=1, padx=12, pady=8, sticky="e")

    # ---------- Details tab (manual overrides) ----------

    def _source_values(self, row: LibraryRow) -> dict[str, str]:
        """The launcher's own values for a row, ignoring any overrides."""
        resolved = self.store.resolve_item(row.item_id)
        record = resolved.record if resolved is not None else None
        return {
            "display_title": getattr(record, "title", "") or "",
            "launch_target": getattr(record, "launch_target", "") or "",
            "launch_arguments": getattr(record, "launch_arguments", "") or "",
            "working_directory": getattr(record, "working_directory", "") or "",
            "notes": "",
        }

    def _current_values(self, row: LibraryRow) -> dict[str, str]:
        resolved = self.store.resolve_item(row.item_id)
        return {
            "display_title": row.title,
            "launch_target": row.launch_target,
            "launch_arguments": row.launch_arguments,
            "working_directory": row.working_directory,
            "notes": getattr(resolved, "notes", "") or "",
        }

    def _build_details_tab(self, parent, row: LibraryRow) -> None:
        current = self._current_values(row)
        launch_state = (
            "Unknown" if row.launch_target_exists is None
            else ("Yes" if row.launch_target_exists else "No — this game cannot be written to Steam")
        )
        rows = [(field_label(field), current[field] or "—") for field in OVERRIDE_FIELDS]
        rows.append(("Launch target exists", launch_state))
        self._build_kv_rows(parent, rows)

        overridden = sorted(row.overridden_fields)
        footer = ctk.CTkFrame(parent, fg_color="transparent")
        footer.grid(row=len(rows), column=0, sticky="ew", pady=(10, 0))
        ctk.CTkLabel(
            footer,
            text=(
                "Overridden: " + ", ".join(field_label(field) for field in overridden)
                if overridden else "No manual overrides — showing the launcher's own values."
            ),
            anchor="w", text_color=COLORS["muted"], font=self._font(10), wraplength=420,
        ).pack(fill="x", padx=4, pady=(0, 8))
        ctk.CTkButton(
            footer, text="Edit details", height=30, width=130, corner_radius=7,
            font=self._font(11, "bold"), fg_color=self.palette["accent"],
            hover_color=self.palette["hover"], command=lambda: self._edit_details(row.item_id),
        ).pack(side="left", padx=4)
        if overridden:
            ctk.CTkButton(
                footer, text="Reset to source", height=30, width=140, corner_radius=7,
                font=self._font(11, "bold"), fg_color="transparent", border_width=1,
                border_color=COLORS["line"], text_color=COLORS["danger"],
                hover_color=COLORS["line"], command=lambda: self._reset_details(row.item_id),
            ).pack(side="left", padx=4)

    def _edit_details(self, item_id: str) -> None:
        row = self.controller.row_map().get(item_id)
        if row is None:
            return
        current = self._current_values(row)

        dialog = ctk.CTkToplevel(self)
        dialog.title(f"Edit details — {row.title}")
        dialog.geometry("620x430")
        dialog.configure(fg_color=COLORS["window"])
        dialog.transient(self)
        dialog.grab_set()
        dialog.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            dialog,
            text="Blank a field, or type the launcher's own value, to drop the override.",
            anchor="w", text_color=COLORS["muted"], font=self._font(10), wraplength=580,
        ).grid(row=0, column=0, padx=18, pady=(16, 8), sticky="ew")

        entries: dict[str, ctk.CTkEntry] = {}
        body = ctk.CTkFrame(dialog, fg_color=COLORS["panel"], corner_radius=10)
        body.grid(row=1, column=0, padx=16, sticky="nsew")
        body.grid_columnconfigure(1, weight=1)
        dialog.grid_rowconfigure(1, weight=1)
        for index, field in enumerate(OVERRIDE_FIELDS):
            ctk.CTkLabel(
                body, text=field_label(field), anchor="w", width=140,
                text_color=COLORS["muted"], font=self._font(11),
            ).grid(row=index, column=0, padx=(14, 8), pady=8, sticky="w")
            entry = ctk.CTkEntry(
                body, height=32, corner_radius=7, border_color=COLORS["line"],
                fg_color=COLORS["window"], font=self._font(11),
            )
            entry.insert(0, current.get(field, ""))
            entry.grid(row=index, column=1, padx=(0, 14), pady=8, sticky="ew")
            entries[field] = entry

        actions = ctk.CTkFrame(dialog, fg_color="transparent")
        actions.grid(row=2, column=0, padx=16, pady=14, sticky="ew")

        def save() -> None:
            edits = {field: entry.get() for field, entry in entries.items()}
            self._save_details(item_id, edits)
            dialog.destroy()

        ctk.CTkButton(
            actions, text="Save", height=32, width=110, corner_radius=7,
            font=self._font(11, "bold"), fg_color=self.palette["accent"],
            hover_color=self.palette["hover"], command=save,
        ).pack(side="right", padx=4)
        ctk.CTkButton(
            actions, text="Cancel", height=32, width=110, corner_radius=7,
            font=self._font(11, "bold"), fg_color="transparent", border_width=1,
            border_color=COLORS["line"], text_color=COLORS["muted"],
            hover_color=COLORS["line"], command=dialog.destroy,
        ).pack(side="right", padx=4)

    def _active_overrides(self, row: LibraryRow) -> dict[str, str]:
        """The override values currently in effect, for change reporting."""
        current = self._current_values(row)
        return {
            field: current.get(field, "") if field in row.overridden_fields or field == "notes" else ""
            for field in OVERRIDE_FIELDS
        }

    def _save_details(self, item_id: str, edits: dict[str, str]) -> None:
        row = self.controller.row_map().get(item_id)
        if row is None:
            return
        previous = self._active_overrides(row)
        try:
            overrides = build_manual_overrides(item_id, edits, self._source_values(row))
            self.store.save_overrides(overrides)
        except (ValueError, KeyError) as exc:
            messagebox.showerror("Edit details", f"Could not save these details: {exc}")
            return
        self.controller.refresh(include_missing=self.include_missing)
        self._set_status(override_change_message(describe_override_changes(previous, overrides)))
        self._render_library_card()
        self._render_content()

    def _reset_details(self, item_id: str) -> None:
        if not messagebox.askyesno(
            "Reset to source",
            "Drop every manual override for this game and go back to the values its "
            "launcher reports?\n\nArtwork locks and rejected matches are not affected.",
        ):
            return
        self._save_details(item_id, {field: "" for field in OVERRIDE_FIELDS})

    def _build_artwork_tab(self, parent, row: LibraryRow) -> None:
        slots = [("Portrait", "grid", "600 \u00d7 900"), ("Wide Capsule", "wide", "616 \u00d7 353"),
                  ("Hero", "hero", "1920 \u00d7 620"), ("Logo", "logo", "512 \u00d7 256"), ("Icon", "icon", "256 \u00d7 256")]
        locks = {lock.slot: lock for lock in self.store.list_artwork_locks(row.item_id)}
        grid = ctk.CTkFrame(parent, fg_color="transparent")
        grid.grid(row=0, column=0, sticky="ew")
        grid.grid_columnconfigure((0, 1), weight=1)
        for index, (name, slot_key, dims) in enumerate(slots):
            locked = slot_key in row.locked_slots
            lock = locks.get(slot_key)
            cached = Path(lock.local_path) if lock and lock.local_path else None
            on_disk = cached is not None and cached.is_file()
            card = ctk.CTkFrame(grid, fg_color=COLORS["panel_alt"], border_width=1, border_color=COLORS["line"], corner_radius=10)
            card.grid(row=index // 2, column=index % 2, padx=5, pady=5, sticky="nsew")
            if not locked:
                status = "Not fetched"
            elif on_disk:
                status = "\u2713 Locked"
            else:
                # A lock whose cache file is gone cannot be applied to Steam,
                # so say so here rather than showing a confident green check.
                status = "\u26a0 Locked, file missing"
            ctk.CTkLabel(card, text=f"{name}  {dims}  {status}", anchor="w", text_color="#c8d8e8", font=self._font(10, "bold")).pack(fill="x", padx=10, pady=(10, 6))
            preview = ctk.CTkFrame(card, height=90, fg_color=COLORS["panel_soft"], corner_radius=8)
            preview.pack(fill="x", padx=10)
            preview.pack_propagate(False)
            image = self._thumbnail(str(cached), box=(150, 84)) if on_disk else None
            if image is not None:
                self._preview_images.append(image)
                ctk.CTkLabel(preview, image=image, text="").place(relx=0.5, rely=0.5, anchor="center")
            else:
                ctk.CTkLabel(preview, text=_monogram(row.title), font=self._font(15, "bold")).place(relx=0.5, rely=0.5, anchor="center")
            if lock is not None and lock.source:
                ctk.CTkLabel(
                    card, text=f"via {lock.source}", anchor="w",
                    text_color=COLORS["muted"], font=self._font(9),
                ).pack(fill="x", padx=10, pady=(4, 0))
            buttons = ctk.CTkFrame(card, fg_color="transparent")
            buttons.pack(fill="x", padx=8, pady=8)
            for label in ["Auto Match", "Replace", "Clear"]:
                ctk.CTkButton(
                    buttons, text=label, height=26, width=1, corner_radius=6, font=self._font(9, "bold"),
                    fg_color=self.palette["accent"] if label == "Auto Match" else "transparent",
                    border_width=0 if label == "Auto Match" else 1, border_color=COLORS["line"],
                    text_color=COLORS["danger"] if label == "Clear" else COLORS["text"],
                    command=lambda item=row.item_id, key=slot_key, n=name, l=label: self._artwork_action(item, key, n, l),
                ).pack(side="left", expand=True, fill="x", padx=2)

        summary = self.controller.artwork_decision_summary((row.item_id,))
        info = ctk.CTkFrame(parent, fg_color=COLORS["panel_alt"], border_width=1, border_color=COLORS["line"], corner_radius=10)
        info.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        ctk.CTkLabel(info, text="SAFETY & BACKUP", anchor="w", text_color="#68aefc", font=self._font(11, "bold")).pack(fill="x", padx=12, pady=(10, 4))
        ctk.CTkLabel(
            info, text=f"{summary.locked_slots} slot(s) locked \u2022 {summary.rejected_matches} rejected match(es) on file.",
            anchor="w", text_color=COLORS["muted"], font=self._font(10),
        ).pack(fill="x", padx=12, pady=(0, 10))

    def _artwork_action(self, item_id: str, slot_key: str, slot_name: str, label: str) -> None:
        if label == "Clear":
            row = self.controller.row_map().get(item_id)
            if row is None or slot_key not in row.locked_slots:
                self._set_status(f"{slot_name} had no lock to clear.")
                return
            if not messagebox.askyesno("Clear artwork lock", f"Clear the locked {slot_name} artwork for this game?"):
                return
            self.store.clear_artwork_lock(item_id, slot_key)
            self.controller.refresh(include_missing=self.include_missing)
            self._set_status(f"Cleared {slot_name} artwork lock.")
            self._render_content()
        elif label == "Auto Match":
            self._start_auto_match(item_id, slot_key, slot_name)
        elif label == "Replace":
            self._start_replace(item_id, slot_key, slot_name)

    # ---------- Auto-Art (per-slot search, download, lock) ----------

    def _artwork_sources_enabled(self) -> bool:
        return any(self.settings.artwork_sources.values())

    def _search_artwork_candidates(self, row: LibraryRow, slot_key: str) -> list[ArtworkAsset]:
        game = game_from_library_row(row)
        client = SteamGridDbClient(self.settings.steamgriddb_api_key, Path(self.settings.cache_dir), LOGGER)
        service = ArtworkProviderSearchService(LOGGER)
        assets_by_kind = service.collect_assets(
            game,
            row.title,
            client,
            enabled_sources=self.settings.artwork_sources,
            rawg_api_key=self.settings.rawg_api_key,
        )
        return assets_by_kind.get(slot_key, [])

    @staticmethod
    def _asset_source_label(asset: ArtworkAsset) -> str:
        source = asset.raw.get("source") if asset.raw else ""
        if source:
            return str(source)
        return "SteamGridDB" if "steamgriddb" in asset.url else ""

    def _start_auto_match(self, item_id: str, slot_key: str, slot_name: str) -> None:
        if not self._artwork_sources_enabled():
            messagebox.showinfo(
                "Auto Match",
                "No artwork source is enabled. Turn on at least one source (SteamGridDB, "
                "Official Steam, Wikimedia, or RAWG) on the Settings screen first.",
            )
            return
        row = self.controller.row_map().get(item_id)
        if row is None:
            return
        job_id = f"artwork-match-{uuid4().hex[:12]}"
        record = JobRecord(
            job_id=job_id,
            item_id=item_id,
            kind=JobKind.ARTWORK,
            message=f"Searching artwork sources for {slot_name}…",
        )
        self._pending_action_jobs[job_id] = self._handle_artwork_match_finished
        self.controller.job_queue.submit(
            record,
            lambda job, token, report_progress: self._auto_match_slot_job(row, slot_key, slot_name, report_progress),
        )
        self._set_status(f"Searching artwork sources for {slot_name}…")

    def _auto_match_slot_job(
        self, row: LibraryRow, slot_key: str, slot_name: str, report_progress
    ) -> JobExecutionResult:
        report_progress(0.1, f"Searching artwork sources for {slot_name}…")
        try:
            candidates = self._search_artwork_candidates(row, slot_key)
        except Exception as exc:
            raise RuntimeError(f"Artwork search failed: {exc}") from exc
        if not candidates:
            raise RuntimeError(f"No artwork candidates found for {slot_name}.")

        cache_dir = Path(self.settings.cache_dir)
        tried = candidates[:8]
        for index, candidate in enumerate(tried):
            report_progress(0.3 + 0.5 * index / max(len(tried), 1), f"Trying candidate {index + 1} of {len(tried)}…")
            try:
                path = download_asset(candidate, cache_dir)
                validate_artwork_file(path)
            except Exception:
                continue
            source = self._asset_source_label(candidate)
            return JobExecutionResult(
                state=JobState.SUCCEEDED,
                result={
                    "item_id": row.item_id,
                    "slot": slot_key,
                    "slot_name": slot_name,
                    "candidate_id": candidate.asset_id,
                    "source": source,
                    "local_path": str(path),
                },
                message=f"Matched {slot_name} via {source or 'artwork search'}.",
            )
        raise RuntimeError(
            f"Found {len(candidates)} candidate(s) for {slot_name}, but none downloaded/validated successfully."
        )

    def _lock_artwork_result(self, result: dict) -> None:
        self.store.set_artwork_lock(
            ArtworkLock(
                item_id=result["item_id"],
                slot=result["slot"],
                candidate_id=result["candidate_id"],
                source=result["source"],
                local_path=result["local_path"],
            )
        )
        self.controller.refresh(include_missing=self.include_missing)
        self._render_content()

    def _handle_artwork_match_finished(self, event: JobEvent) -> None:
        if event.state is JobState.SUCCEEDED:
            self._lock_artwork_result(event.result)
            self._set_status(event.message or "Artwork matched.")
        else:
            self._set_status(f"Auto Match failed: {event.error or event.message}")
            messagebox.showerror("Auto Match failed", event.error or event.message)

    def _start_replace(self, item_id: str, slot_key: str, slot_name: str) -> None:
        if not self._artwork_sources_enabled():
            messagebox.showinfo(
                "Replace",
                "No artwork source is enabled. Turn on at least one source (SteamGridDB, "
                "Official Steam, Wikimedia, or RAWG) on the Settings screen first.",
            )
            return
        row = self.controller.row_map().get(item_id)
        if row is None:
            return
        job_id = f"artwork-replace-{uuid4().hex[:12]}"
        record = JobRecord(
            job_id=job_id,
            item_id=item_id,
            kind=JobKind.ARTWORK,
            message=f"Searching artwork sources for {slot_name}…",
        )
        self._pending_action_jobs[job_id] = self._handle_replace_job_finished
        self.controller.job_queue.submit(
            record,
            lambda job, token, report_progress: self._replace_slot_job(row, slot_key, slot_name, report_progress),
        )
        self._set_status(f"Searching artwork sources for {slot_name}…")

    def _replace_slot_job(
        self, row: LibraryRow, slot_key: str, slot_name: str, report_progress
    ) -> JobExecutionResult:
        report_progress(0.1, f"Searching artwork sources for {slot_name}…")
        try:
            candidates = self._search_artwork_candidates(row, slot_key)
        except Exception as exc:
            raise RuntimeError(f"Artwork search failed: {exc}") from exc
        if not candidates:
            raise RuntimeError(f"No artwork candidates found for {slot_name}.")

        cache_dir = Path(self.settings.cache_dir)
        downloaded: list[dict] = []
        tried = candidates[:10]
        for index, candidate in enumerate(tried):
            if len(downloaded) >= 3:
                break
            report_progress(0.2 + 0.6 * index / max(len(tried), 1), f"Checking candidate {index + 1} of {len(tried)}…")
            try:
                path = download_asset(candidate, cache_dir)
                validate_artwork_file(path)
            except Exception:
                continue
            downloaded.append(
                {
                    "candidate_id": candidate.asset_id,
                    "source": self._asset_source_label(candidate),
                    "local_path": str(path),
                    "width": candidate.width,
                    "height": candidate.height,
                }
            )
        if not downloaded:
            raise RuntimeError(
                f"Found {len(candidates)} candidate(s) for {slot_name}, but none downloaded/validated successfully."
            )
        return JobExecutionResult(
            state=JobState.SUCCEEDED,
            result={
                "item_id": row.item_id,
                "slot": slot_key,
                "slot_name": slot_name,
                "candidates": downloaded,
            },
            message=f"Found {len(downloaded)} usable candidate(s) for {slot_name}.",
        )

    def _handle_replace_job_finished(self, event: JobEvent) -> None:
        if event.state is not JobState.SUCCEEDED:
            self._set_status(f"Replace failed: {event.error or event.message}")
            messagebox.showerror("Replace failed", event.error or event.message)
            return
        slot_name = event.result["slot_name"]
        candidates = event.result["candidates"]
        lines = [f"Choose a {slot_name} image:"]
        for index, candidate in enumerate(candidates, start=1):
            lines.append(
                f"  {index}. {candidate['width']}x{candidate['height']} "
                f"— {candidate['source'] or 'unknown source'}"
            )
        messagebox.showinfo("Replace", "\n".join(lines))
        choice = simpledialog.askinteger(
            "Replace",
            f"Enter a number from 1 to {len(candidates)} (Cancel to keep the current artwork):",
            minvalue=1,
            maxvalue=len(candidates),
        )
        if choice is None:
            self._set_status(f"Replace cancelled for {slot_name}.")
            return
        chosen = candidates[choice - 1]
        self._lock_artwork_result(
            {
                "item_id": event.result["item_id"],
                "slot": event.result["slot"],
                "candidate_id": chosen["candidate_id"],
                "source": chosen["source"],
                "local_path": chosen["local_path"],
            }
        )
        self._set_status(f"Replaced {slot_name} via {chosen['source'] or 'artwork search'}.")

    # ---------- other sidebar screens (real data, honest gaps) ----------

    def _build_shortcuts_screen(self) -> None:
        rows = [r for r in self.controller.snapshot().rows if r.source != "steam"]
        body = self._simple_screen("Shortcuts", "Non-Steam launcher entries tracked in the persistent library.")
        if not rows:
            ctk.CTkLabel(body, text="No non-Steam shortcuts tracked yet.", text_color=COLORS["muted"], font=self._font(12)).grid(row=0, column=0, sticky="w")
            return
        for index, row in enumerate(rows):
            self._list_row(body, index, "\u2197", row.title, f"{row.source.title()} \u2022 {row.status.title()}", "Open", lambda item=row.item_id: self._activate_and_show_library(item))

    def _build_artwork_screen(self) -> None:
        rows = self.controller.snapshot().rows
        pending_ids = self.review_queue.pending_item_ids
        active_jobs = self.review_queue.active_job_count
        body = self._simple_screen(
            "Artwork",
            "Review queue for bulk Auto-Art, plus locked slots and rejected matches per game.",
        )

        next_row = 0
        if active_jobs or pending_ids:
            self._build_review_queue_section(body, next_row, pending_ids, active_jobs)
            next_row += 1

        for index, row in enumerate(rows):
            summary = self.controller.artwork_decision_summary((row.item_id,))
            self._list_row(
                body,
                next_row + index,
                "\u25a7",
                row.title,
                f"{summary.locked_slots} locked \u2022 {summary.rejected_matches} rejected",
                "Open",
                lambda item=row.item_id: self._activate_and_show_library(item),
            )

    # ---------- bulk artwork review queue ----------

    def _build_review_queue_section(
        self, parent, grid_row: int, pending_ids: tuple[str, ...], active_jobs: int
    ) -> None:
        row_map = self.controller.row_map()
        titles = {item_id: row.title for item_id, row in row_map.items()}
        decisions = self.controller.artwork_decision_summary(pending_ids or ())
        summary = build_artwork_review_summary(pending_ids, self.review_queue.results)

        card = ctk.CTkFrame(parent, fg_color=COLORS["panel_alt"], border_width=1, border_color=self.palette["border"], corner_radius=10)
        card.grid(row=grid_row, column=0, sticky="ew", pady=(0, 10))
        card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(card, text="ARTWORK REVIEW QUEUE", anchor="w", text_color="#68aefc", font=self._font(11, "bold")).grid(row=0, column=0, padx=14, pady=(12, 2), sticky="ew")
        ctk.CTkLabel(
            card, text=artwork_queue_progress_text(active_jobs, len(pending_ids)),
            anchor="w", text_color=COLORS["muted"], font=self._font(10),
        ).grid(row=1, column=0, padx=14, sticky="ew")
        ctk.CTkLabel(
            card,
            text=artwork_review_header_text(
                summary.selected_item_count,
                decisions.locked_slots,
                decisions.rejected_matches,
                summary.pending_slot_count,
            ),
            anchor="w", text_color=COLORS["muted"], font=self._font(10),
        ).grid(row=2, column=0, padx=14, pady=(2, 8), sticky="ew")

        if not pending_ids:
            ctk.CTkLabel(
                card, text=artwork_review_empty_message(), anchor="w",
                text_color=COLORS["muted"], font=self._font(11),
            ).grid(row=3, column=0, padx=14, pady=(0, 12), sticky="ew")
            return

        bulk = ctk.CTkFrame(card, fg_color="transparent")
        bulk.grid(row=3, column=0, padx=10, pady=(0, 6), sticky="ew")
        for label, command, accent in [
            ("Accept All", lambda: self._review_decision(pending_ids, "accept"), True),
            ("Reject All", lambda: self._review_decision(pending_ids, "reject"), False),
            ("Skip All", lambda: self._review_decision(pending_ids, "skip"), False),
        ]:
            ctk.CTkButton(
                bulk, text=label, height=28, width=110, corner_radius=7, font=self._font(10, "bold"),
                fg_color=self.palette["accent"] if accent else COLORS["panel"],
                hover_color=self.palette["hover"] if accent else COLORS["line"],
                command=command,
            ).pack(side="left", padx=3, pady=4)

        review_rows = build_artwork_review_rows(pending_ids, titles, self.review_queue.results)
        by_item: dict[str, list] = {}
        for review_row in review_rows:
            by_item.setdefault(review_row.item_id, []).append(review_row)

        container = ctk.CTkFrame(card, fg_color="transparent")
        container.grid(row=4, column=0, padx=10, pady=(0, 12), sticky="ew")
        container.grid_columnconfigure(0, weight=1)
        for index, item_id in enumerate(pending_ids):
            self._build_review_item_card(
                container, index, item_id, titles.get(item_id, item_id), by_item.get(item_id, [])
            )

    def _build_review_item_card(self, parent, grid_row: int, item_id: str, title: str, rows: list) -> None:
        card = ctk.CTkFrame(parent, fg_color=COLORS["panel"], border_width=1, border_color=COLORS["line"], corner_radius=9)
        card.grid(row=grid_row, column=0, sticky="ew", pady=4)
        card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(card, text=title, anchor="w", font=self._font(12, "bold")).grid(row=0, column=0, padx=12, pady=(10, 2), sticky="ew")
        summary = f"{len(rows)} candidate slot(s) awaiting a decision"
        if rows:
            # These are measured by artwork_scoring, not placeholders, so they
            # are safe to show as confidence.
            summary += f"    ·    match {rows[0].identity_score}%, set coherence {rows[0].set_coherence_score}%"
        ctk.CTkLabel(
            card, text=summary,
            anchor="w", text_color=COLORS["muted"], font=self._font(10),
        ).grid(row=1, column=0, padx=12, pady=(0, 2), sticky="ew")
        if rows and rows[0].reasons:
            ctk.CTkLabel(
                card, text=rows[0].reasons[0], anchor="w", wraplength=520,
                text_color=COLORS["muted"], font=self._font(9),
            ).grid(row=2, column=0, padx=12, pady=(0, 6), sticky="ew")

        slots = ctk.CTkFrame(card, fg_color="transparent")
        slots.grid(row=3, column=0, padx=10, pady=(0, 6), sticky="ew")
        slots.grid_columnconfigure(1, weight=1)
        for index, row in enumerate(rows):
            preview = self._preview_widget(slots, row.path, title)
            preview.grid(row=index, column=0, padx=(2, 10), pady=3)
            text = ctk.CTkFrame(slots, fg_color="transparent")
            text.grid(row=index, column=1, sticky="ew", pady=3)
            heading = f"{row.slot.title()}  \u2022  {row.provider or 'provider'}"
            if row.dimensions_label:
                heading += f"  \u2022  {row.dimensions_label}"
            ctk.CTkLabel(text, text=heading, anchor="w", font=self._font(11, "bold")).pack(fill="x")
            ctk.CTkLabel(
                text, text=row.path or "(no validated file)", anchor="w",
                text_color=COLORS["muted"], font=self._font(9),
            ).pack(fill="x")
            ctk.CTkButton(
                slots, text="Details", height=24, width=70, corner_radius=6, font=self._font(9, "bold"),
                fg_color="transparent", border_width=1, border_color=COLORS["line"],
                command=lambda r=row: messagebox.showinfo("Candidate details", artwork_review_detail_text(r)),
            ).grid(row=index, column=2, padx=6)

        actions = ctk.CTkFrame(card, fg_color="transparent")
        actions.grid(row=4, column=0, padx=10, pady=(0, 10), sticky="ew")
        for label, command, accent, danger in [
            ("Accept", lambda: self._review_decision((item_id,), "accept"), True, False),
            ("Reject", lambda: self._review_decision((item_id,), "reject"), False, True),
            ("Skip", lambda: self._review_decision((item_id,), "skip"), False, False),
            ("Retry", lambda: self._retry_review_item(item_id), False, False),
        ]:
            ctk.CTkButton(
                actions, text=label, height=26, width=90, corner_radius=6, font=self._font(10, "bold"),
                fg_color=self.palette["accent"] if accent else "transparent",
                border_width=0 if accent else 1, border_color=COLORS["line"],
                hover_color=self.palette["hover"] if accent else COLORS["line"],
                text_color=COLORS["danger"] if danger else COLORS["text"],
                command=command,
            ).pack(side="left", padx=3)

    def _preview_widget(self, parent, path: str, title: str):
        """Real thumbnail for a validated candidate, or a monogram placeholder.

        Never falls back to a *different* game's art or a stock image: if the
        file cannot be decoded, the slot shows initials so a broken candidate
        is visibly broken rather than plausibly wrong.
        """
        image = self._thumbnail(path)
        if image is not None:
            self._preview_images.append(image)
            return ctk.CTkLabel(parent, image=image, text="")
        return ctk.CTkLabel(
            parent, text=_monogram(title), width=64, height=48, fg_color=COLORS["panel_soft"],
            corner_radius=6, font=self._font(12, "bold"),
        )

    @staticmethod
    def _thumbnail(path: str, box: tuple[int, int] = (64, 48)) -> ctk.CTkImage | None:
        if not path or not Path(path).is_file():
            return None
        try:
            from PIL import Image

            with Image.open(path) as handle:
                image = handle.convert("RGBA")
                image.thumbnail(box)
                return ctk.CTkImage(light_image=image, dark_image=image, size=image.size)
        except Exception:  # noqa: BLE001 - a bad preview must never break the screen
            LOGGER.debug("Could not build artwork preview for %s", path, exc_info=True)
            return None

    def _review_decision(self, item_ids: tuple[str, ...], action: str) -> None:
        results = self.review_queue.results_for(item_ids)
        if not results:
            messagebox.showinfo("Artwork review", artwork_review_no_pending_message())
            return
        if action == "reject" and not messagebox.askyesno(
            "Reject artwork",
            f"Reject the pending candidates for {len(results)} game(s)?\n\n"
            "Rejected candidates are remembered so future searches can skip them. "
            "No Steam file is touched either way.",
        ):
            return

        decided = 0
        for result in results:
            item_id = str(result.get("item_id") or "")
            if action == "accept":
                decided += self.controller.accept_artwork_review_result(result).accepted
            elif action == "reject":
                decided += self.controller.reject_artwork_review_result(result).rejected
            else:
                decided += review_result_slot_count(result)
            self.review_queue.discard(item_id)

        if action != "skip":
            self.controller.refresh(include_missing=self.include_missing)
        self._set_status(artwork_review_action_message(action, decided))
        self._render_library_card()
        self._render_content()

    def _retry_review_item(self, item_id: str) -> None:
        self.review_queue.discard(item_id)
        if self._submit_artwork_jobs((item_id,)) == 0:
            messagebox.showinfo("Artwork review", artwork_plan_no_jobs_message())
        self._render_content()

    def _build_metadata_screen(self) -> None:
        rows = self.controller.snapshot().rows
        body = self._simple_screen("Metadata", "Fields resolved for each stored library item.")
        for index, row in enumerate(rows):
            self._list_row(body, index, "\u2261", row.title, f"Overrides: {', '.join(sorted(row.overridden_fields)) or 'none'}", "Open", lambda item=row.item_id: self._activate_and_show_library(item))

    def _activate_and_show_library(self, item_id: str) -> None:
        self.controller.set_active(item_id)
        self._set_nav("Library")

    def _build_tools_screen(self) -> None:
        body = self._simple_screen("Tools", "Maintenance utilities backed by SettingsStore.")
        self._list_row(body, 0, "\U0001f5d1", "Delete Cached Artwork", f"Cache: {self.settings.cache_dir}", "Run", self._clear_cache)
        self._list_row(body, 1, "\u21ba", "Reset Settings to Defaults", "Clears saved app settings", "Run", self._reset_settings)
        self._list_row(body, 2, "\U0001f5c2", "Open Logs Folder", "View recent activity logs", "Open", self._open_logs)

    def _clear_cache(self) -> None:
        result = self.settings_store.clear_cached_artwork(self.settings)
        self._set_status(f"Deleted {result.files_deleted} cached file(s) ({format_size(result.bytes_deleted)}).")
        self._render_content()

    def _reset_settings(self) -> None:
        if not messagebox.askyesno("Reset settings", "Reset all app settings to defaults?"):
            return
        self.settings = self.settings_store.reset_to_defaults()
        self._set_status("Settings reset to defaults.")
        self._render_content()

    def _open_logs(self) -> None:
        logs_dir = self.settings_store.settings_dir / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        try:
            if os.name == "nt":
                os.startfile(logs_dir)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.run(["open", str(logs_dir)], check=False)
            else:
                subprocess.run(["xdg-open", str(logs_dir)], check=False)
        except OSError:
            messagebox.showinfo("Logs folder", str(logs_dir))

    def _build_import_screen(self) -> None:
        body = self._simple_screen("Import / Scan", "Bring games into the persistent library from a source.")
        detected = detect_steam_install()
        self._list_row(body, 0, "\u25c7", "Native Steam Install", str(detected) if detected else "No installation auto-detected \u2014 will prompt to choose", "Scan", self._scan_steam)
        epic_dir = default_epic_manifest_dir()
        self._list_row(body, 1, "\u25c6", "Epic Games Launcher", str(epic_dir) if epic_dir else "Manifest folder not found on this OS", "Scan", self._scan_epic)
        self._list_row(body, 2, "\u25a2", "Local Folder", self.settings.collection_root or "No folder chosen yet", "Scan", self._scan_folder)

    def _scan_steam(self) -> None:
        root = detect_steam_install()
        if root is None:
            chosen = filedialog.askdirectory(title="Choose your Steam install folder")
            if not chosen:
                return
            root = Path(chosen)
        self.settings.steam_path = str(root)
        self.settings_store.save(self.settings)
        self._submit_scan(SteamLibraryAdapter(root))

    def _scan_epic(self) -> None:
        self._submit_scan(EpicManifestAdapter())

    def _scan_folder(self) -> None:
        chosen = filedialog.askdirectory(title="Choose your local game collection folder")
        if not chosen:
            return
        self.settings.collection_root = chosen
        self.settings_store.save(self.settings)
        self._submit_scan(FolderScannerAdapter(chosen))

    def _submit_scan(self, adapter) -> None:
        try:
            self.controller.scan_source(adapter)
            self._set_status(f"Queued {adapter.source_name} scan\u2026")
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Scan failed to start", str(exc))

    def _poll_jobs(self) -> None:
        if self._closing:
            return
        for event in self.controller.poll_events():
            if event.snapshot is not None:
                self._render_library_card()
                self._render_content()
            job_event = event.event
            if job_event.job_id in self._pending_action_jobs:
                if job_event.state in TERMINAL_JOB_STATES:
                    handler = self._pending_action_jobs.pop(job_event.job_id)
                    handler(job_event)
                continue
            if self.review_queue.tracks(job_event.job_id):
                self._handle_bulk_artwork_event(job_event)
                continue
            if job_event.state in (JobState.SUCCEEDED, JobState.NEEDS_REVIEW):
                self._set_status(job_event.message or "Scan finished.")
            elif job_event.state is JobState.FAILED:
                self._set_status(f"Scan failed: {job_event.error or job_event.message}")
        self._refresh_cancel_button()
        self._poll_after_id = self.after(200, self._poll_jobs)

    def _handle_bulk_artwork_event(self, event: JobEvent) -> None:
        accepted = rejected = 0
        if event.state in TERMINAL_JOB_STATES and event.result:
            # Auto-accepted and policy-rejected decisions persist themselves;
            # review results are held in memory until a human decides.
            persistence = self.controller.persist_artwork_job_result(event.result)
            accepted, rejected = persistence.accepted, persistence.rejected

        update = self.review_queue.handle_event(event, accepted=accepted, rejected=rejected)
        if update is None:
            return
        self._set_status(update.status)
        if not update.terminal:
            return
        if accepted or rejected:
            self.controller.refresh(include_missing=self.include_missing)
        if self.review_queue.active_job_count == 0:
            self._set_status(
                artwork_queue_progress_text(0, len(self.review_queue.pending_item_ids))
            )
        if self.nav == "Artwork":
            self._render_content()

    def _build_backups_screen(self) -> None:
        body = self._simple_screen("Backups", "Restore points recorded by the transaction system.")
        try:
            shortcut_entries = list_transaction_history()
            if isinstance(shortcut_entries, tuple):
                shortcut_entries = shortcut_entries[0]
        except Exception:  # noqa: BLE001
            shortcut_entries = []
        try:
            artwork_entries = list_artwork_transaction_history()
        except Exception:  # noqa: BLE001
            artwork_entries = []
        entries = [*shortcut_entries, *artwork_entries]
        if not entries:
            ctk.CTkLabel(body, text="No transactions recorded yet.", text_color=COLORS["muted"], font=self._font(12)).grid(row=0, column=0, sticky="w")
            return
        ordered = sorted(entries, key=lambda e: e.updated_at, reverse=True)
        # Rendering every historical transaction as a widget can freeze the UI
        # once real usage accumulates hundreds of entries (observed live this
        # session: 446 real artwork transactions from months of prior use) --
        # cap to the most recent 50, matching transaction_history.py's own
        # retention_candidates(keep_latest=50) precedent.
        shown, remainder = ordered[:50], len(ordered) - 50
        for index, entry in enumerate(shown):
            detail = f"{entry.status} \u2022 {entry.updated_at.isoformat(timespec='minutes')}" + (" \u2022 restore available" if entry.restore_available else "")
            self._list_row(body, index, "\u25c8", entry.display_target, detail, None)
        if remainder > 0:
            ctk.CTkLabel(
                body, text=f"...and {remainder} older transaction(s) not shown.",
                text_color=COLORS["muted"], font=self._font(11),
            ).grid(row=len(shown), column=0, padx=4, pady=(8, 0), sticky="w")

    def _build_settings_screen(self) -> None:
        body = self._simple_screen("Settings", "Artwork sources and app preferences (SettingsStore-backed).")
        self.artwork_source_vars: dict[str, ctk.BooleanVar] = {}
        for index, (key, label) in enumerate(ARTWORK_SOURCE_LABELS.items()):
            var = ctk.BooleanVar(value=bool(self.settings.artwork_sources.get(key, True)))
            self.artwork_source_vars[key] = var
            row_frame = ctk.CTkFrame(body, fg_color=COLORS["panel_alt"], border_width=1, border_color=COLORS["line"], corner_radius=10)
            row_frame.grid(row=index, column=0, sticky="ew", pady=4)
            row_frame.grid_columnconfigure(0, weight=1)
            ctk.CTkSwitch(
                row_frame, text=label, variable=var, onvalue=True, offvalue=False,
                progress_color=self.palette["accent"], font=self._font(12, "bold"),
                command=lambda k=key, v=var: self._toggle_artwork_source(k, v),
            ).grid(row=0, column=0, padx=14, pady=10, sticky="w")

    def _toggle_artwork_source(self, key: str, var) -> None:
        self.settings.artwork_sources[key] = bool(var.get())
        self.settings_store.save(self.settings)
        self._set_status(f"{ARTWORK_SOURCE_LABELS.get(key, key)} {'enabled' if var.get() else 'disabled'}.")

    def _build_extensions_screen(self) -> None:
        body = self._simple_screen("Extensions", "No extensions installed yet.")
        ctk.CTkLabel(body, text="Extension support is not implemented in this build.", text_color=COLORS["muted"], font=self._font(12)).grid(row=0, column=0, sticky="w")

    def _build_about_screen(self) -> None:
        body = self._simple_screen(
            f"About {__app_name__} {__version__}",
            "Not affiliated with Valve, Steam, SteamGridDB, RAWG, or Wikimedia.",
        )
        row = 0
        readme = REPO_ROOT / "README.md"
        if readme.is_file():
            # Absent in a packaged build, where there is no repo checkout.
            self._list_row(
                body, row, "\u24d8", "Project README", str(readme), "Open",
                lambda: webbrowser.open(readme.as_uri()),
            )
            row += 1
        self._list_row(body, row, "\u2699", "Settings file", str(self.settings_store.settings_path), None)
        self._list_row(body, row + 1, "\u25a4", "Library database", str(self.database_path), None)
        self._list_row(
            body, row + 2, "\u270e", "Classic interface",
            "Opens the original window; every workflow not yet in this UI lives there",
            "Open", self._open_classic_ui,
        )

    def _open_classic_ui(self) -> None:
        """Launch the legacy window in a separate process.

        The classic UI still owns workflows this shell has not replaced (live
        scan detail editing, per-game exe/title overrides, custom artwork
        files). Running it in its own process keeps two Tk mainloops from
        fighting, and keeps a shell crash from taking the classic UI with it.
        """
        if not messagebox.askyesno(
            "Open classic interface",
            "Open the original Steam Shortcut Studio window in a separate process?\n\n"
            "Both interfaces read the same library database and settings. Avoid "
            "applying changes from both at once.",
        ):
            return
        # A frozen build has no importable -m entry point, so it re-launches
        # itself with the flag main.py understands instead.
        frozen = getattr(sys, "frozen", False)
        command = (
            [sys.executable, "--classic"] if frozen
            else [sys.executable, "-m", "steam_shortcut_studio.app"]
        )
        try:
            subprocess.Popen(command, cwd=None if frozen else str(REPO_ROOT))
            self._set_status("Opened the classic interface in a separate process.")
        except OSError as exc:
            messagebox.showerror(
                "Classic interface",
                f"Could not start the classic interface: {exc}",
            )


def main(argv: list[str] | None = None) -> int:
    ctk.set_appearance_mode("dark")
    app = ModernShell()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
