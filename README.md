# Steam Shortcut Studio

Steam Shortcut Studio is a desktop app for scanning PC game folders, choosing the right launch file, finding Steam-style artwork, and safely writing non-Steam shortcuts into Steam.

It is built for personal game libraries where many games live outside Steam, and where Steam's default artwork and shortcut tools are too manual.

## Features

- Scan installed Steam games, existing non-Steam shortcuts, and a local game folder.
- Review launch candidates and manually choose a different `.exe`, Linux binary, script, or AppImage when needed.
- Preserve existing non-Steam shortcut launch choices when rescanning.
- Search artwork from official Steam assets, SteamGridDB, Wikimedia, and RAWG.
- Search official Steam game artwork without changing installed Steam shortcuts.
- Preview, replace, clear, or open selected artwork in Paint on Windows or the default image app on Linux.
- Delete cached artwork and reset settings from the Settings dialog.
- Preview Steam changes before writing.
- Write non-Steam shortcuts through staged, verified, automatically reversible transactions.
- Write each game's grid, wide, hero, logo, and icon artwork as one atomic set with full rollback.
- Close Steam before writing when needed, then reopen Steam only if this app closed it.
- Keep generated settings, API keys, cache files, logs, builds, and library databases out of source control.

## Current Development Direction

The project is evolving into a safe modern personal-library manager with:

- A sleek dark desktop UI with selectable accent colors
- Native Steam and non-Steam games in one library view
- Reliable multi-selection and contextual bulk actions
- `Find Artwork for Selected` for processing many games in one batch
- High-confidence artwork automation with an exception review queue
- Persistent manual overrides, artwork locks, rejected matches, and scan history
- Windows launcher manifests first, followed by SteamOS/Bazzite sources

Already completed foundations include:

- Transactional production shortcut writes
- Atomic production artwork-set writes
- Transaction and restore-point history
- Stable selection and bounded background jobs
- Bulk artwork planning and policy routing
- Image validation and duplicate detection
- Read-only Epic Games Launcher manifest import
- Persistent SQLite library state
- Read-only modern UI prototype using real stored library data

Development should begin with [CODEX_START_HERE.md](CODEX_START_HERE.md).

Planning and execution documents:

- [Product Roadmap](docs/PRODUCT_ROADMAP.md)
- [UI/UX Target](docs/UI_UX_TARGET.md)
- [Sprint Map](docs/SPRINT_MAP.md)
- [Current Sprint Status](docs/SPRINT_STATUS.md)
- [Current Architecture](docs/CURRENT_ARCHITECTURE.md)
- [Write Path Audit](docs/WRITE_PATH_AUDIT.md)
- [Transaction Service Specification](docs/TRANSACTION_SERVICE_SPEC.md)
- [Artwork Match Policy](docs/ARTWORK_MATCH_POLICY.md)
- [Launcher Import Research](docs/LAUNCHER_IMPORT_RESEARCH.md)
- [CLI Guide](docs/CLI.md)
- [UI Framework Decision](docs/UI_FRAMEWORK_DECISION.md)
- [Development Setup](docs/DEVELOPMENT_SETUP.md)

The active engineering focus is **controller/service extraction and production modern-library integration**, followed by real artwork-provider integration for `Find Artwork for Selected`.

## Validation

```text
python -m compileall -q steam_shortcut_studio tests main.py
python tests/smoke_test.py
python tests/foundation_test.py
python tests/transaction_test.py
python tests/file_transaction_test.py
python tests/shortcut_transaction_test.py
python tests/app_transaction_wiring_test.py
python tests/transaction_history_test.py
python tests/job_queue_test.py
python tests/bulk_artwork_test.py
python tests/epic_source_test.py
python tests/library_store_test.py
python tests/source_scan_test.py
python tests/cli_test.py
python tests/image_validation_test.py
python tests/artwork_transaction_test.py
python tests/artwork_live_transaction_test.py
```

GitHub Actions runs the suites on Windows and Ubuntu with Python 3.11 and 3.13. Optional modern UI imports and persistent-library mapping are also tested on Windows and Ubuntu.

## Requirements

- Windows 10 or newer, SteamOS, or Bazzite
- Python 3.11 or newer
- Pillow 10 or newer
- Optional: Tkinter if your Python does not include it
- Optional UI prototype: `requirements-ui-prototype.txt`

## Basic Usage

1. Open the app.
2. In `Library Location`, choose or detect your Steam folder.
3. Choose your game collection folder.
4. Click `Scan`.
5. Review detected games and launch candidates.
6. Use `Search Art` for checked games in the current view.
7. Use the `Artwork` tab to choose or customize artwork.
8. Click `Preview`.
9. Click `Write to Steam`.

Installed Steam game artwork can also be edited.

## Epic Library and Modern Prototype

Scan Epic's installed-game manifests into the persistent library:

```powershell
python -m steam_shortcut_studio.cli scan-epic
```

Inspect the stored library:

```powershell
python -m steam_shortcut_studio.cli list-library --source epic
```

Open the approved modern UI prototype with those real stored games:

```powershell
python -m pip install -r requirements-ui-prototype.txt
python prototypes/modern_library.py
```

The prototype is read-only. Its Apply action remains disabled until production controller and review-workspace integration is complete.

## Settings, Library, and Cache

Settings and API keys are stored locally under:

```text
Windows:
%APPDATA%\SteamShortcutStudio\settings.json

Linux:
~/.config/SteamShortcutStudio/settings.json
```

Persistent library state is stored under:

```text
Windows:
%APPDATA%\SteamShortcutStudio\library.sqlite3

Linux:
~/.config/SteamShortcutStudio/library.sqlite3
```

Logs are stored under:

```text
Windows:
%APPDATA%\SteamShortcutStudio\logs

Linux:
~/.config/SteamShortcutStudio/logs
```

Artwork downloads and search caches are stored under the configured cache folder, shown in `Settings > Maintenance`.

By default, artwork cache files are under `%LOCALAPPDATA%\SteamShortcutStudio\cache` on Windows and `~/.cache/SteamShortcutStudio/cache` on Linux.

Use `Delete Cached Artwork` to remove downloaded artwork previews and artwork search caches. Use `Reset Settings to Defaults` to clear saved app settings.

## Artwork Sources

Artwork sources can be enabled or disabled in `Settings > Artwork`.

- Official Steam artwork uses public Steam CDN assets when an AppID can be matched.
- SteamGridDB requires a SteamGridDB API key.
- RAWG requires a RAWG API key.
- Wikimedia does not require a key and is used as a fallback source.

SteamGridDB keys are created from your SteamGridDB account preferences. RAWG keys are created from RAWG's API docs page. Do not commit real API keys.

## Steam Files

Non-Steam shortcuts live at:

```text
Windows:
<Steam>\userdata\<user id>\config\shortcuts.vdf

Linux:
<Steam>/userdata/<user id>/config/shortcuts.vdf
```

Artwork is copied to:

```text
Windows:
<Steam>\userdata\<user id>\config\grid

Linux:
<Steam>/userdata/<user id>/config/grid
```

Production shortcut and artwork writes are staged, backed up, verified after writing, and automatically rolled back when verification fails. Malformed active shortcut data is blocked rather than silently replaced.

## Linux Steam Paths

On Linux, the app looks for Steam in common SteamOS, Bazzite, and Flatpak locations:

```text
~/.local/share/Steam
~/.steam/steam
~/.steam/root
~/.var/app/com.valvesoftware.Steam/.local/share/Steam
/home/deck/.local/share/Steam
```

You can also set `STEAM_PATH` or choose the folder manually.

## Publishing Notes

This project is not affiliated with Valve, Steam, SteamGridDB, RAWG, Wikimedia, or PCGamingWiki.
