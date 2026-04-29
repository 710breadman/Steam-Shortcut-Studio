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

## Requirements

- Windows 10 or newer, SteamOS, or Bazzite
- Python 3.11 or newer
- Optional: Pillow for richer JPEG/WebP artwork previews

Install optional dependencies:

```powershell
python -m pip install -r requirements.txt
```

On SteamOS or Bazzite, install Tkinter if your Python does not include it:

```bash
# SteamOS / Arch
sudo pacman -S tk

# Bazzite / Fedora
sudo dnf install python3-tkinter
```

## Run From Source

```powershell
python main.py
```

or:

```powershell
.\run.ps1
```

Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python main.py
```

## Basic Workflow

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

## Build A Standalone EXE

Install PyInstaller:

```powershell
python -m pip install pyinstaller
```

Build:

```powershell
python -m PyInstaller --noconfirm --clean SteamShortcutStudio.spec
```

The standalone executable is written to:

```text
dist\SteamShortcutStudio.exe
```

`dist/` and `build/` are ignored by Git. For GitHub, publish the source repository first, then upload the built `.exe` as a GitHub Release asset if you want other people to download it directly.

## Build A Linux Binary

PyInstaller does not cross-compile, so build the Linux binary on Linux:

```bash
python -m pip install -r requirements.txt pyinstaller
python -m PyInstaller --noconfirm --clean --onefile --windowed \
  --name SteamShortcutStudio-Linux \
  --add-data "steam_shortcut_studio/assets/sss.png:steam_shortcut_studio/assets" \
  --add-data "steam_shortcut_studio/assets/sss.ico:steam_shortcut_studio/assets" \
  --collect-all PIL \
  main.py
```

The standalone Linux executable is written to:

```text
dist/SteamShortcutStudio-Linux
```

The `Build Release` GitHub Actions workflow builds both Windows and Linux binaries. When you push a version tag like `v0.2.0`, it uploads the build artifacts to that GitHub Release.

## Tests

Run the smoke tests:

```powershell
python tests/smoke_test.py
```

The smoke tests cover VDF parsing/writing, shortcut duplicate handling, launch candidate ranking, Linux Steam path validation, artwork cache behavior, settings reset, and Steam artwork filenames.

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

[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/Z8Z71YMW54)
