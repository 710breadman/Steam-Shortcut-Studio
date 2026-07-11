# Current Architecture

**Audit date:** 2026-07-11  
**Branch audited:** `agent/foundation-and-bulk-artwork`  
**Baseline version:** 0.2.1

## Executive Summary

Steam Shortcut Studio is a standard-library-first Python desktop application. The current implementation has a useful domain core, broad smoke coverage, and working Windows/Linux support, but the application shell has accumulated too many responsibilities in `steam_shortcut_studio/ui.py`.

The safest path is incremental:

1. Preserve current scanning, matching, and Steam integration behavior.
2. Put transaction boundaries around every Steam-owned write.
3. Extract testable selection, job, policy, and service layers.
4. Replace the visual shell only after those boundaries exist.

A full rewrite is not recommended.

## Runtime Entry Points

- `main.py`
  - Starts the desktop application.
- `steam_shortcut_studio/ui.py`
  - Owns the current Tkinter/ttk application shell.
  - Coordinates scanning, metadata, artwork, preview, writing, settings, logging, and background jobs.
- `steam_shortcut_studio/__init__.py`
  - Stores application name and version.

## Current Domain Modules

### Library discovery and identity

- `scanner.py`
  - Scans folders recursively for launch candidates.
  - Scores executables/scripts and chooses a preferred candidate.
  - Cleans display titles and applies title-specific aliases.
- `steam_library.py`
  - Reads installed native Steam games.
  - Converts existing non-Steam shortcuts into library rows.
- `steam_detection.py`
  - Detects Steam roots and user profiles.
  - Detects, closes, and reopens Steam around writes.
- `models.py`
  - Holds game, artwork, metadata, executable candidate, profile, and settings-related data models.

### Metadata and artwork discovery

- `metadata.py`
  - Runs metadata providers and merges results.
- `steam_store.py`
  - Searches Steam store identity and official media.
- `steamgrid.py`
  - Calls SteamGridDB API endpoints.
- `artwork_sources.py`
  - Provides Wikimedia and RAWG fallback discovery.
- `http_client.py`
  - Centralizes HTTP headers and certificate handling.

### Steam read/write behavior

- `steam_shortcuts.py`
  - Reads and writes binary `shortcuts.vdf`.
  - Generates non-Steam AppIDs.
  - Preserves selected user-managed fields when updating an existing shortcut.
  - Creates timestamped backups.
  - Performs a post-write read-back check for expected games.
- `artwork.py`
  - Downloads artwork into the application cache.
  - Maps assets into Steam grid slots.
  - Backs up and replaces files in the Steam grid directory.
- `steam_compat.py`
  - Reads and writes text `config.vdf` compatibility mappings.
  - Creates a backup before changing an existing file.
- `steam_notes.py`
  - Writes metadata notes for managed non-Steam entries.
  - Explicitly excludes native Steam games.
- `vdf.py`
  - Implements custom binary and text VDF parsing/serialization.

### Persistence and export

- `settings_store.py`
  - Stores application settings, API keys, theme choices, provider choices, and cache location.
  - Performs cache maintenance and settings reset.
- `reporting.py`
  - Exports library/report data.

## Current UI Responsibilities

`ui.py` currently owns or directly coordinates:

- Window construction and theming
- Game table state
- Selection state
- View filtering and sorting
- Steam detection
- Folder scan orchestration
- Existing shortcut merge behavior
- Metadata provider orchestration
- Artwork search orchestration
- Artwork candidate scoring and aliases
- Artwork cache state
- Background threads and UI event delivery
- Preview generation
- Steam shutdown/reopen flow
- Shortcut, artwork, notes, and compatibility writes
- Logging and dialogs

This concentration makes UI changes risky because visual changes can accidentally affect Steam-write behavior.

## Existing Strengths

- Native Steam games are protected from non-Steam shortcut creation.
- Existing shortcut fields such as overlay state and manual tags are preserved during merge.
- `shortcuts.vdf` writes use a temporary file and replacement.
- Existing Steam-owned files are backed up before replacement.
- Shortcut writes are read back and checked for expected games.
- The smoke suite covers scanning, VDF round trips, merging, compatibility mappings, notes, artwork, themes, settings, and cache behavior.
- Windows, SteamOS, Bazzite, and common Linux Steam locations are already considered.

## Highest-Risk Areas

1. **Malformed `shortcuts.vdf` recovery**
   - The current behavior backs up the malformed file, then writes a fresh shortcut list.
   - This can recover the app workflow but may remove unrelated shortcuts from the active file.
   - Future transaction work must require explicit recovery confirmation or restore the original automatically on verification failure.

2. **Independent write systems**
   - Shortcuts, artwork, notes, and compatibility mappings each perform their own backup/write behavior.
   - They are not yet one atomic transaction.

3. **Artwork validation**
   - Downloads reject empty and HTML responses, but do not yet require successful image decoding before entering an apply plan.

4. **UI-coupled domain logic**
   - Matching, aliases, batch state, and cache behavior are partly embedded in the UI module.

5. **Custom VDF parser scope**
   - Unknown or future field types may not be preserved safely without fixture and compatibility testing.

## New Foundation Added

The following UI-independent modules are now available for future implementation:

- `selection.py`
  - Separates the active inspector row from bulk-selected rows.
  - Supports range selection and stable action scope.
- `jobs.py`
  - Defines job types, lifecycle states, retry rules, cancellation, and batch summaries.
- `artwork_policy.py`
  - Defines automatic acceptance, review, and rejection decisions from explicit evidence.

These modules do not alter current runtime behavior yet.

## Target Boundaries

Future extraction should move toward:

```text
ui/
  components/
  views/
  theme/
controllers/
services/
  scan_service.py
  metadata_service.py
  artwork_service.py
  transaction_service.py
  backup_service.py
models/
  library_item.py
  transaction.py
  job.py
```

Do not move everything at once. Extract one tested responsibility at a time.

## Baseline Validation

The repository now contains cross-platform CI that runs:

```text
python -m compileall -q steam_shortcut_studio tests main.py
python tests/smoke_test.py
python tests/foundation_test.py
```

CI results must be recorded in `SPRINT_STATUS.md` before Sprint 00 is marked complete.
