[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/Z8Z71YMW54)

# Steam Shortcut Studio

Steam Shortcut Studio is a Windows desktop app for scanning PC game folders, choosing the right executable, finding Steam-style artwork, and safely writing non-Steam shortcuts into Steam.

It is built for personal game libraries where many games live outside Steam, and where Steam's default artwork and shortcut tools are too manual.

## Features

- Scan installed Steam games, existing non-Steam shortcuts, and a local game folder.
- Review executable candidates and manually choose a different `.exe` when needed.
- Preserve existing non-Steam shortcut executable choices when rescanning.
- Search artwork from official Steam assets, SteamGridDB, Wikimedia, and RAWG.
- Search official Steam game artwork without changing installed Steam shortcuts.
- Preview, replace, clear, or open selected artwork in Paint.
- Delete cached artwork and reset settings from the Settings dialog.
- Preview Steam changes before writing.
- Back up `shortcuts.vdf` before modifying it.
- Close Steam before writing when needed, then reopen Steam only if this app closed it.
- Write grid, wide, hero, logo, and icon artwork to Steam's grid folder.
- Keep generated settings, API keys, cache files, logs, and builds out of source control.

## Requirements

- Windows 10 or newer
- Python 3.11 or newer
- Optional: Pillow for richer JPEG/WebP artwork previews

Install optional dependencies:

```powershell
python -m pip install -r requirements.txt
```

## Run From Source

```powershell
python main.py
```

or:

```powershell
.\run.ps1
```

## Basic Workflow

1. Open the app.
2. In `Library Location`, choose or detect your Steam folder.
3. Choose your game collection folder.
4. Click `Scan`.
5. Review detected games and executable candidates.
6. Use `Search Art` for checked games in the current view.
7. Use the `Artwork` tab to choose or customize artwork.
8. Click `Preview`.
9. Click `Write to Steam`.

Installed Steam game Artwork can also be edited.

## Settings And Cache

Settings and API keys are stored locally under:

```text
%APPDATA%\SteamShortcutStudio\settings.json
```

Logs are stored under:

```text
%APPDATA%\SteamShortcutStudio\logs
```

Artwork downloads and search caches are stored under the configured cache folder, shown in `Settings > Maintenance`.

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
<Steam>\userdata\<user id>\config\shortcuts.vdf
```

Artwork is copied to:

```text
<Steam>\userdata\<user id>\config\grid
```

Before writing an existing `shortcuts.vdf`, the app creates a timestamped backup beside it.

## Tests

Run the smoke tests:

```powershell
python tests\smoke_test.py
```

The smoke tests cover VDF parsing/writing, shortcut duplicate handling, executable ranking, artwork cache behavior, settings reset, and Steam artwork filenames.

## Project Structure

```text
steam_shortcut_studio/
  app.py
  ui.py
  models.py
  scanner.py
  exe_metadata.py
  steam_detection.py
  steam_library.py
  steam_shortcuts.py
  steam_notes.py
  steam_store.py
  steamgrid.py
  artwork.py
  artwork_sources.py
  metadata.py
  settings_store.py
  reporting.py
  sgdboop.py
  vdf.py
  assets/
    sss.png
    sss.ico
tests/
  smoke_test.py
examples/
  settings.example.json
```

## Publishing Notes

This project is not affiliated with Valve, Steam, SteamGridDB, RAWG, Wikimedia, or PCGamingWiki.
