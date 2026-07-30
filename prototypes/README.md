# Handoff: Modern Library UI (Steam Shortcut Studio)

## Overview
A redesigned main-window UI for Steam Shortcut Studio: dark desktop shell with a left nav sidebar, top command bar, central sortable/filterable game library table with multi-select and bulk actions, and a right-side game inspector with tabs (Artwork/Details/Metadata/Links/Local Files), plus a safety-gated Apply Changes flow (Preview → Confirm → Applying → Success/Rollback-available).

This satisfies the approved direction in `docs/UI_UX_TARGET.md`.

## What's in this bundle now
Two things, not one:

1. **`Steam Shortcut Studio.dc.html`** — the original browser-based design reference (see "About the Design Files" below).
2. **`prototypes/modern_shell.py` + `prototypes/modern_library.py`** — a **real, working implementation** of that design, already wired to your actual code: `LibraryController`, `LibraryStore`/`SQLite`, `SelectionState`, `BackgroundJobQueue`, `SettingsStore`, `list_transaction_history`, and the `SteamLibraryAdapter` / `EpicManifestAdapter` / `FolderScannerAdapter` source adapters. **Drop these two files directly into your `prototypes/` folder, overwriting the existing mock-data versions**, then run:
   ```powershell
   python -m pip install -r requirements-ui-prototype.txt
   python prototypes/modern_library.py
   ```
   No mock `MockGame` data remains — the Library table reads your real persistent library (`library.sqlite3`). Search/filter/sort/multi-select, the sidebar accent switcher, all 10 sidebar screens, Tools (cache clear / reset settings / open logs), Settings (live artwork-source toggles saved to `settings.json`), Backups (real `list_transaction_history()` entries), and Import/Scan (real Steam/Epic/local-folder scans submitted through `LibraryController.scan_source` and polled via `BackgroundJobQueue`, per `CODEX_START_HERE.md`) are all live and functional today.

## What is intentionally still gated
Per `CODEX_START_HERE.md`'s required safety rules ("Add no new Steam writes", "Do not enable prototype Apply actions merely because the interface exists", "No fake safety" in `docs/UI_UX_TARGET.md`):
- **Apply Changes** shows an explanation dialog instead of writing anything — it needs `shortcut_transactions.py` / `artwork_transactions.py` wired with real backup → write → verify → rollback steps before it can be enabled honestly.
- **Auto-Art / per-slot Auto Match / Replace** show an explanation dialog — real matching needs `BulkArtworkCoordinator` wired to a live provider search (SteamGridDB/Official Steam/RAWG/Wikimedia).
These are exactly the pieces flagged "Codex Required" in `CODEX_START_HERE.md`; everything else in the shell is real and functional, not a mock.

**Clear Slot is live**: it calls `LibraryStore.clear_artwork_lock(item_id, slot)` (already exposed on the store) with a confirm prompt, then refreshes the row so the slot shows "Not fetched" again. The button is disabled when the slot has no lock to clear.

## About the Design Files
The file in this bundle (`Steam Shortcut Studio.dc.html`) is a **design reference built in plain, self-contained HTML/JS** (no build step, no external runtime — open it directly in a browser) — it shows intended look, layout, and interaction behavior end-to-end (including a mocked Apply flow), but it is not production code and uses mock data (`GAME_SEED`), not your real library. Do not port the HTML/JS into the app. Recreate the same layout, styling, and interactions using the project's existing Tkinter/customtkinter component and theme layer (see `docs/UI_FRAMEWORK_DECISION.md`), wired to the real controllers/services listed below.

## Fidelity
**High-fidelity.** Treat colors, spacing, radii, type sizes, and layout proportions below as final. Recreate pixel-close using customtkinter's available styling (corner_radius, fg_color, border_width/color, font) — some effects (CSS grid track shrinking, text-overflow ellipsis) will need Tkinter-appropriate equivalents (fixed column widths, `wraplength`/truncation).

## Screens / Views

### 1. Library (default view)
**Purpose:** Browse, search, filter, sort, multi-select games; inspect and manage one game's artwork/metadata/details.

**Layout:** CSS grid, `222px` sidebar | `1fr` main content, 3 rows (topbar `auto`, content `1fr`, footer `28px`, 28px tall). Main content area splits into a 2-column grid: library panel `minmax(0,1.15fr)` and inspector panel `minmax(0,1fr)`, `8px` gap, both panels `border-radius:12px`, `background:#0b1b2c`, `padding:12–14px`.

**Sidebar** (`background:#081625`, full height, `overflow-y:auto` — important, must scroll on short windows):
- Brand row: accent-colored "◉" glyph (30px) + "STEAM" (14px/700) + "SHORTCUT STUDIO" (11px/700) + "v1.6.2" with a "PRO" pill (accent bg, white text, 8px/700, 4px radius).
- Nav list (10 items, 40px tall rows, 9px radius, 12px horizontal padding, 3px gap): Library ▦, Shortcuts ↗, Artwork ▧, Metadata ≡, Tools ✎, Import / Scan ⌕, Backups ◈, Settings ⚙, Extensions ✚, About ⓘ. Active item: `background: palette.selected`, `border: 1px solid palette.border`, bold text. Inactive: transparent bg, `#b7c5d4` text, 500 weight.
- Appearance card (`#0b1b2c`, 12px radius, 10px/12px padding): "APPEARANCE" label (10px/700, `#8fa3b8`) + 5 accent swatches (22px circles) + a dashed "+" add-swatch affordance.
- Steam Library card: folder label + path (`D:\SteamLibrary`, 10px `#8fa3b8`), a 7px progress bar (accent fill), and "142.1 GB of 1.86 TB used" caption.

**Top command bar** (`#0b1b2c`, 12px radius, 8px/10px padding, flex row):
- 4 action buttons, each icon+title (13px/700) on one line and subtitle (10px, `#8fa3b8`) indented below: Scan ⌕ "Scan Folders & Libraries", Refresh Metadata ↻ "Update Info & Artwork", Auto-Art ✦ "Find & Match Artwork", Preview ◫ "Preview Changes". Transparent bg, hover highlight.
- Right-aligned: "SAFE MODE" label (10px/700, `#f5b942`), then the primary **Apply Changes** button (accent-filled, white text, 9px radius, "⇪ Apply Changes ▾" bold + "Safely" subtitle).

**Library panel:**
- Search input (flex:1, 38px tall, `#07111f` bg, `1px solid #1c3147`, 8px radius) + filter `<select>` (All Games / Steam / Non-Steam / Needs Review / Protected).
- Table header row (grid, `26px minmax(0,2.2fr) minmax(0,1fr)×3 minmax(0,0.7fr)`, `#07111f` bg, 7px radius, 10px/700 `#8fa3b8` labels): checkbox col, TITLE (sortable), SOURCE, PLATFORM, LAST PLAYED (sortable), SIZE (sortable). Sort arrows (↑/↓) appear next to the active sort column.
- Scrollable row list, each row: 34px monogram thumbnail (2-letter initials on a dark tint), title (12px/600, truncated), source/platform/last-played/size (11px, `#b8c6d5`, truncated). Active/inspected row: `background: palette.selected`, `border: palette.border`. Default row: `#0d2135` bg, `#1c3147` border. Checkbox toggles multi-select independent of row click (which sets the active/inspected game).
- Bulk action bar (appears only when ≥1 selected): "N selected" (11px/700) + Scan Selected / Find Art (accent-filled) / Refresh Metadata / Preview buttons + Clear.
- Footer row: "{count} games" left, pagination (‹ page numbers › , active page = accent-filled) right.

**Inspector panel:**
- Header: 52px monogram avatar + title (19px/700) + detail line (10px, `#8fa3b8`): `Steam App ID: … • Installed/Needs review • Last played …`.
- Segmented tab bar (`#07111f` bg track, 9px radius, 4px padding): Artwork / Details / Metadata / Links / Local Files. Active tab: accent-filled pill, white text.
- **Artwork tab:** 2-col grid of 5 slot cards (Portrait 600×900, Wide Capsule 616×353, Hero 1920×620, Logo 512×256, Icon 256×256), each: title row (name + dims in muted + green ✓), a 96px preview block (monogram-tinted placeholder), and 4 action buttons (Auto Match [accent-filled], Review, Replace, Clear [red text]). A 6th card (same grid cell as slot 2's row) holds "AUTO-ART SOURCE": a source `<select>` (SteamGridDB/Official Steam/Local Files/Wikimedia/RAWG) + "Match confidence NN%" (green) + green progress bar. Below the grid: a full-width "SAFETY & BACKUP" card with 3 sub-cards (Backup Ready ▣ / Write Verification ✓ / Rollback Available ↶, each green title + muted detail) and a "Changes to be applied: N artwork file(s)" link line.
- **Details tab:** stacked rows (label left, value right, `#0d2135` card, `1px solid #1c3147`): Launch target, Working directory, Compatibility tool, Source launcher.
- **Metadata tab:** same row style: Title, Release year, Developer, Publisher, Genres, Notes.
- **Links tab:** empty-state message.
- **Local Files tab:** install path row.

### 2. Other sidebar screens (Shortcuts, Artwork, Metadata, Tools, Import / Scan, Backups, Settings, Extensions, About)
Each renders inside the same main-content slot as a single card (`#0b1b2c`, 12px radius, 20px padding): a title (18px/700) + subtitle (12px, `#8fa3b8`), then a vertical list of row items (`#0d2135` bg, `1px solid #1c3147`, 10px radius, 14px/16px padding): a 34px icon tile, title (13px/700) + detail (11px, `#8fa3b8`), and a right-aligned accent-filled action button (Edit/Find Art/Refresh/Run/Scan/Restore/Toggle/View, per screen). See the DC's `renderVals()` `screens` object for exact per-screen copy and items — this is real, screen-appropriate content (e.g. Settings lists the four artwork-source toggles from `README.md`; Tools lists Delete Cached Artwork / Reset Settings / Open Logs Folder; Backups lists restore points).

### 3. Modals (Apply Changes flow)
Centered dialog, `#0b1b2c` bg, `1px solid #1c3147`, 14px radius, 22px padding, over a `rgba(2,8,16,0.6)` backdrop (click backdrop to dismiss where applicable):
- **Preview:** title + summary of what would change for the current selection.
- **Confirm:** "Apply Changes Safely?" + backup/verify/rollback explanation + Cancel/Apply buttons.
- **Applying:** step label (Creating backup… → Writing shortcut data… → Writing artwork set… → Verifying writes…) + accent progress bar, auto-advances.
- **Success:** green "✓ Applied successfully" + summary (backup created, writes verified, rollback available) + Done button.
A toast (bottom-center, `#10263b` bg, palette-bordered, 9px radius) confirms other actions (scan, refresh, per-slot artwork actions, bulk actions, screen-item actions) — kept for parity while wiring real async jobs; replace with real `BackgroundJobQueue` progress once wired.

## Interactions & Behavior
- **Sidebar nav:** click switches the main content region between Library and the 9 simple screens; selected item gets the strong highlight described above.
- **Accent/theme swatches:** click sets `accentName`, recoloring accent-driven elements (selected nav/row highlight, primary buttons, progress bars, checkboxes, tab pills) instantly. 5 presets ship (Ocean Blue default, Orion Purple, Forest Green, Solar Amber, Rose) — same hex values as `prototypes/modern_shell.py`'s `PALETTES`.
- **Search:** live-filters the table by title substring, resets to page 1.
- **Filter select:** All Games / Steam / Non-Steam / Needs Review / Protected — resets to page 1.
- **Column sort:** click TITLE/LAST PLAYED/SIZE header to sort; click again to reverse direction; arrow glyph shows active column + direction.
- **Row selection:** clicking the checkbox toggles multi-select (stops row-click propagation); clicking anywhere else on the row sets it as the active/inspected game and resets the inspector to the Artwork tab.
- **Bulk bar:** appears only when selection is non-empty; each action currently toasts a mock confirmation — wire to real bulk operations (scan, find-art, refresh-metadata, preview) via `BulkArtworkCoordinator`/`BackgroundJobQueue`.
- **Pagination:** 8 rows/page in this mock; ‹ › and numbered page buttons.
- **Inspector tabs:** click switches visible tab content; active tab is pill-highlighted.
- **Artwork slot buttons:** Auto Match / Review Matches / Replace Art / Clear Slot — currently toast-only; wire to `BulkArtworkCoordinator`/artwork transaction services per slot.
- **Auto-Art Source select + confidence bar:** confidence is per-game mock data (`62–98%`); should reflect the real match-policy confidence once wired.
- **Apply Changes button (top bar):** opens the Confirm modal directly. **Preview button (top bar) / "Changes to be applied" link:** opens the Preview modal (read-only summary).
- **Confirm → Applying → Success:** Confirm starts a 4-step timed sequence (mocked at ~550ms/step) then shows Success. Replace the timer with real progress events from the transaction services (staged write → backup → verified write → rollback-point recorded); do not show "success"/green safety states before the service actually confirms them (per `UI_UX_TARGET.md`: "No fake safety").
- No responsive breakpoints are implemented beyond CSS grid shrink-safety (`minmax(0,…)` tracks) — Tkinter layout should follow the "Wide/Medium/Small Window" rules in `docs/UI_UX_TARGET.md`.

## State Management
State needed (see the DC's `state = {...}` for the reference shape):
- `nav` — current sidebar screen.
- `accentName` — selected theme preset.
- `search`, `filter`, `sortCol`, `sortDir`, `page`, `pageSize` — library query/view state.
- `selected` — array/set of selected game ids (multi-select).
- `activeId` — the game shown in the inspector.
- `tab` — active inspector tab.
- `autoArtSource` — selected auto-art provider.
- `modal` — `null | "preview" | "confirm" | "applying" | "success"`, plus `applyStep` for the applying sequence.
- `toast` — transient status message, auto-clears (~2.6s).

Replace the in-DC mock `this.games` array with real data from `LibraryController` (`LibraryRow`s), and back `selected`/`activeId` with the existing `SelectionState` class rather than reinventing it.

## Design Tokens

**Colors:**
```
window        #07111f
sidebar        #081625
panel          #0b1b2c
panel_alt      #0d2135
panel_soft     #10263b
line           #1c3147
text           #f1f5f9
muted          #8fa3b8
success        #34c878
warning        #f5b942
danger         #ef5350
```

**Accent palettes** (`accent` / `hover` / `selected-bg` / `border`):
```
Ocean Blue    #1677ff / #2f8cff / #0f315f / #1d4f8f   (default)
Orion Purple  #7c3aed / #8b5cf6 / #35205c / #6640a5
Forest Green  #12a66a / #22bd7b / #163f35 / #26745c
Solar Amber   #d97706 / #f59e0b / #4a3218 / #8a5b1f
Rose          #db2777 / #ec4899 / #51223e / #8e3765
```

**Typography:** Segoe UI (system-ui fallback). Sizes used: 19px/700 (game title), 15px/700 (modal titles), 14px, 13px/700 (nav/section labels, tab labels), 12px (body, search input), 11px (table rows, detail rows), 10px (captions, sort headers, muted subtitles), 9px (art-card button labels).

**Spacing/radius:** gaps 4/6/8/12/14px; radii 6-7px (small controls, checkboxes), 8-9px (buttons/inputs/rows), 10-12px (cards/panels), 14px (modal).

**Icons:** plain unicode glyphs (◉ ▦ ↗ ▧ ≡ ✎ ⌕ ◈ ⚙ ✚ ⓘ ↻ ✦ ◫ ⇪ ▣ ✓ ↶ ‹ ›) — no icon font/SVG library required; swap for the app's existing icon set if one exists.

## Assets
No external image assets — game thumbnails are 2-letter monogram tiles on a dark tint (6-color rotation), matching the "no fake artwork" placeholder approach. The app's real icon (`steam_shortcut_studio/assets/sss.png` / `sss.ico`) should replace the "◉" brand glyph in the sidebar.

## Files
- `Steam Shortcut Studio.dc.html` — the full interactive design reference (open in a browser; all interactions described above are live/clickable in this file).
- `prototypes/modern_shell.py` — real customtkinter implementation, replaces the file of the same name in your repo.
- `prototypes/modern_library.py` — real entry point, replaces the file of the same name in your repo (same CLI args as before: `--database`, `--include-missing`).
