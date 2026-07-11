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
- Back up `shortcuts.vdf` before modifying it.
- Close Steam before writing when needed, then reopen Steam only if this app closed it.
- Write grid, wide, hero, logo, and icon artwork to Steam's grid folder.
- Keep generated settings, API keys, cache files, logs, and builds out of source control.

## Development Roadmap

The next major direction is a safer, modern personal-library manager with:

- A sleek dark desktop UI with selectable accent colors
- Native Steam and non-Steam games in one library view
- Reliable multi-selection and contextual bulk actions
- `Find Artwork for Selected` for processing many games in one batch
- High-confidence artwork automation with an exception review queue
- Transactional writes, read-back verification, history, and rollback
- Windows launcher manifests first, followed by SteamOS/Bazzite sources

Planning and execution documents:

- [Product Roadmap](docs/PRODUCT_ROADMAP.md)
- [UI/UX Target](docs/UI_UX_TARGET.md)
- [Sprint Map](docs/SPRINT_MAP.md)
- [Current Sprint Status](docs/SPRINT_STATUS.md)

Future development should begin by reading all four files. The current active work is **Sprint 00 — Baseline and Repository Audit**. Safety and write-path verification come before the broader UI rewrite or native Steam setting expansion.

## Requirements

- Windows 10 or newer, SteamOS, or Bazzite
- Python 3.11 or newer
- Optional: Pillow for richer JPEG/WebP artwork previews
- Optional: Tkinter if your Python does not include it

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

Installed Steam game Artwork can also be edited.

## Settings And Cache

Settings and API keys are stored locally under:

```text
Windows:
%APPDATA%\SteamShortcutStudio\settings.json

Linux:
~/.config/SteamShortcutStudio/settings.json
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

Before writing an existing `shortcuts.vdf`, the app creates a timestamped backup beside it.

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
