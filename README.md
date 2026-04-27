# Steam Shortcut Studio

Steam Shortcut Studio is a personal-use Windows desktop app for scanning folders of non-Steam PC games, selecting the most likely playable `.exe`, browsing artwork from selectable sources, writing simple release/description notes, and creating safe non-Steam shortcuts in Steam.

## Tech Stack Choice

This implementation uses Python 3.11+ with Tkinter. The original preference was C#/.NET 8 WPF, but this workspace has .NET desktop runtimes without the .NET SDK. Python/Tkinter gives a working Windows GUI with no mandatory third-party runtime, and optional Pillow support improves JPEG/WebP artwork previews.

## Features

- Detects Steam install paths from the Windows registry and common install folders.
- Detects Steam `userdata` profiles, marks the most recent profile when Steam exposes it, and locates `config\shortcuts.vdf`.
- Scans a chosen game collection folder recursively, and can also add currently installed Steam games to the review list as protected reference rows.
- Uses the top-level folder under the collection root as the source game title.
- Ranks `.exe` candidates by title match, path depth, common game launch folders, file size, PE validity, Windows version metadata, and known bad helper/installer keywords.
- Shows candidate reasoning and allows manual executable override.
- Provides parser-preview style selection tools, view filters, and sort presets for the detected game list.
- Lets you right-click game-list headers to hide/show or move columns for simpler views.
- Includes a `Cancel` button for long scan, note, and artwork jobs.
- Reads and writes Steam binary `shortcuts.vdf`.
- Creates timestamped backups before modifying an existing `shortcuts.vdf`.
- Detects duplicates by executable path first, then title, and can update existing shortcuts.
- Supports shortcut fields for app name, exe, start directory, icon, launch options, and tags.
- Always adds non-Steam shortcuts to Steam's `Non Steam` collection/tag, alongside any custom tags.
- Integrates with selectable artwork sources: official Steam CDN assets, SteamGridDB, Wikipedia/Wikimedia page images, and RAWG.
- Searches official Steam Store/CDN artwork when a matching Steam app can be found.
- Downloads artwork into a local cache and copies selected assets into Steam's `config\grid` folder using the right Steam or non-Steam AppID filenames.
- Writes portrait grid, wide capsule, hero, logo, and icon artwork slots, with sensible fallbacks so Big Picture and Library surfaces are less likely to show blanks.
- Provides a real-time all-artwork thumbnail grid with filtering, plus one-search caching across grid, hero, logo, and icon choices.
- Loads scan-time artwork previews only from local Steam/cache files so library scans stay responsive and avoid remote rate limits.
- Provides manual SteamGridDB artwork search and a compact per-game notes box for release info and description.
- Uses `Find Art` to auto-select artwork from enabled sources and refresh simple release/description notes for non-Steam games.
- Pulls notes from Steam Store, PCGamingWiki, Wikipedia, SteamGridDB, or executable info when useful.
- Writes reviewed non-Steam notes into Steam Game Notes files with visible note-card titles, marked sections, and backups.
- Protects real installed Steam games from note, artwork, category, and shortcut writes.
- Automatically closes Steam before writing only when Steam is running, then reopens Steam only if this app closed it.
- Detects SGDBoop from PATH or registered `sgdb://` protocol command when available.
- Exports scan reports as JSON or CSV.
- Keeps SteamGridDB, RAWG, SGDBoop, artwork source, preview limit, shortcut tag, theme, view, and sort options in a Settings dialog.
- Imports and exports app settings.
- Includes distinct skin-style themes: Follow System, Steam Deck Blue, Neon Grid, Vaporwave Dream, Cyberpunk Hazard, Monochrome Steel, High Contrast, Amber Arcade, Glacier Blue, Purple Glow, Green Terminal, Candy Pop, and Classic Light.
- Keeps a visible log panel for advanced troubleshooting.
- Writes a rotating troubleshooting log file under `%APPDATA%\SteamShortcutStudio\logs`.

## Folder Structure

```text
steam_shortcut_studio/
  app.py                 Entry point
  ui.py                  Tkinter GUI and workflow orchestration
  models.py              Shared dataclasses
  scanner.py             Recursive game scanner and executable ranking
  exe_metadata.py        PE/version metadata helpers
  steam_detection.py     Steam install/profile detection
  steam_library.py       Installed Steam library/appmanifest scanner
  vdf.py                 Binary VDF parser/writer
  steam_shortcuts.py     Shortcut model, duplicate detection, backup/write logic
  steam_notes.py         Steam Game Notes writer
  steam_store.py         Steam Store note and official CDN artwork lookup
  steamgrid.py           SteamGridDB API client
  artwork_sources.py     Wikipedia/Wikimedia and RAWG artwork providers plus source settings
  artwork.py             Artwork cache/download/Steam grid copy logic
  metadata.py            Local, SteamGridDB, Steam Store, PCGamingWiki, and Wikipedia metadata providers
  sgdboop.py             Optional SGDBoop detection helpers
  reporting.py           JSON/CSV scan report export
examples/
  settings.example.json
tests/
  smoke_test.py
```

## Setup

1. Install Python 3.11 or newer for Windows.
2. Optional: install Pillow for richer artwork previews:

```powershell
python -m pip install -r requirements.txt
```

The app still runs without Pillow, but previews are limited to image formats Tkinter can load directly.

## Run

From this folder:

```powershell
.\run.ps1
```

or:

```powershell
python -m steam_shortcut_studio.app
```

You can also launch through:

```powershell
python main.py
```

## Basic Workflow

1. Let the app auto-detect Steam, or choose the Steam folder manually.
2. Choose the Steam profile/user to modify.
3. Choose a game collection root, for example `D:\Games`.
4. Click `Scan` once to scan installed Steam games, existing non-Steam shortcuts, and the chosen folder collection.
5. Review detected games, confidence scores, and executable reasoning.
6. Manually change an executable if the ranking is wrong.
7. Open `Settings` to enter SteamGridDB or RAWG API keys if you want those sources, choose artwork sources, pick a theme, and adjust preview count.
8. Use `Find Art` to fetch artwork and refresh release/description notes for checked non-Steam games.
9. Preview changes.
10. Write shortcuts. The app closes Steam first if it is running, then reopens Steam when the write finishes. If Steam was already closed, it stays closed.

The single `Scan` button combines the old Steam-library scan and folder scan. It loads installed Steam games, existing non-Steam shortcuts from `shortcuts.vdf`, and folder-detected games. Installed Steam rows are reference-only and are protected from writes. Existing non-Steam rows are labeled in the Steam column so you can tell what is already in `shortcuts.vdf`.

The game list has a `Selection` menu, `View` filter, and `Sort` preset dropdown. These are inspired by Steam ROM Manager's preview/exceptions workflow: keep the main list calm, then focus it on checked rows, missing artwork, new non-Steam shortcuts, existing non-Steam shortcuts, installed Steam games, or skipped rows.

## Steam Shortcut Writing

Steam stores non-Steam shortcuts per user at:

```text
<Steam>\userdata\<user id>\config\shortcuts.vdf
```

`shortcuts.vdf` is a binary Valve Data Format file. The app parses it into shortcut records, compares existing records against selected games, then writes a complete binary VDF file back to disk. Existing shortcuts are preserved as records. When `Update duplicates` is enabled, matching shortcuts are updated instead of duplicated. Updates merge with the old record so manual launch options, overlay flags, hidden status, last-play time, shortcut path, and existing tags are kept unless you explicitly change the app-owned fields.

Steam collections for non-Steam shortcuts are stored as shortcut tags. Steam Shortcut Studio always includes a `Non Steam` tag so entries land in the requested non-Steam collection, while still preserving or adding any other configured tags.

Before modifying an existing `shortcuts.vdf`, the app creates a timestamped backup next to it:

```text
shortcuts.vdf.20260425-153012.bak
```

If Steam is running, the app closes it before writing because Steam can overwrite external shortcut edits when it exits. Steam is reopened afterward only when this app closed it.

References:

- [Valve Developer Community: Steam Library Shortcuts](https://developer.valvesoftware.com/wiki/Steam_Library_Shortcuts)
- [Valve Developer Community: Adding Non-Steam Games](https://developer.valvesoftware.com/wiki/Add_Non-Steam_Game)

## Artwork Handling

Artwork sources can be enabled or disabled in `Settings > Artwork`.

Official Steam artwork uses known public Steam CDN asset names when a Steam AppID is known. These include library capsule, hero, logo, and header-style images. Steam sometimes serves newer assets from hashed URLs, so this source is best-effort.

Wikipedia/Wikimedia uses the MediaWiki PageImages API to pull the page image for likely game pages. It does not require an API key and works as a useful fallback, especially for older or niche games.

RAWG uses the RAWG Video Games Database API for background images and screenshots. It requires a RAWG API key and is disabled by default until you enable it.

SteamGridDB uses API v2 with a bearer token:

```text
Authorization: Bearer <your API key>
```

It searches `/search/autocomplete/{term}`, then fetches assets from:

- `/grids/game/{gameId}`
- `/heroes/game/{gameId}`
- `/logos/game/{gameId}`
- `/icons/game/{gameId}`

Downloads are cached under the configured cache folder. On write, selected artwork is copied to:

```text
<Steam>\userdata\<user id>\config\grid
```

File names are based on the generated non-Steam AppID:

- `<appid>p.png` for portrait grid/cover art
- `<appid>.png` for wide capsule/landscape art
- `<appid>_hero.png` for hero art
- `<appid>_logo.png` for logos
- `<appid>_icon.png` or `.ico` for icons

When one artwork slot is missing, the app falls back to the best suitable downloaded image for that Steam surface, for example using a grid or hero image for a missing wide capsule. If an old image exists with another supported extension, it is backed up and removed before the new file is copied.

References:

- [SteamGridDB API v2](https://www.steamgriddb.com/api/v2)
- [MediaWiki PageImages API](https://www.mediawiki.org/wiki/Extension:PageImages#API)
- [RAWG API docs](https://rawg.io/apidocs)

When multiple sources return results, the app keeps them together in the artwork grid and records the source on each tile. Initial scan preloading is local-only: it displays artwork already present in Steam or already chosen in the app, and it does not download remote previews until you use `Search Game` or `Find Art`.

## Artwork API Key Storage

The SteamGridDB field expects a SteamGridDB API key, not your Steam account password. Sign in to SteamGridDB and generate/copy the key from your user preferences page, then paste it into `Settings > Artwork` and save.

The RAWG field expects a RAWG API key from RAWG's API docs page. RAWG requires a key on requests and asks projects to attribute RAWG when using its data/images.

API keys are saved locally in:

```text
%APPDATA%\SteamShortcutStudio\settings.json
```

This is intentionally simple for personal use. Treat that file as private.

## Optional SGDBoop Support

SGDBoop is optional. It can apply SteamGridDB assets through the `sgdb://` protocol, and this app detects it if it is installed or registered. Steam Shortcut Studio does not require SGDBoop because it can download and place artwork directly.

Reference:

- [SteamGridDB/SGDBoop](https://github.com/SteamGridDB/SGDBoop)

## Steam Notes

Notes are intentionally simple and Steam-friendly. For non-Steam shortcuts, the app writes only:

- Game title
- Release year/date when found
- Description/overview when found

The app may use Steam Store, PCGamingWiki, Wikipedia, SteamGridDB, or local executable info to find that release/description text. The GUI no longer exposes a metadata-heavy editor; the `Shortcut` tab keeps just the title, launch options, release field, executable picker, and final Notes box.

The Notes box is the exact text that will be written, so user edits are preserved. The note title is set to the fetched description when possible so useful text is visible on Steam's Notes card without opening the note.

Notes are written only for non-Steam shortcuts. They use the shortcut-name file Steam creates for non-Steam games, plus multiple non-Steam shortcut ID variants because Steam has used more than one shortcut ID form. Real installed Steam games are intentionally skipped:

```text
<Steam>\userdata\<user id>\2371090\remote\notes_shortcut_<game name>
<Steam>\userdata\<user id>\2371090\remote\notes_<shortcut appid>
```

Existing note files are backed up and preserved. Steam Shortcut Studio replaces only its marked notes section when it updates notes. It also writes a non-conflicting fallback copy here:

```text
<Steam>\userdata\<user id>\config\SteamShortcutStudio\metadata_notes\<game>.txt
```

## Design References

Several workflow ideas are intentionally borrowed from Steam ROM Manager and the EmuDeck flow around it:

- Steam ROM Manager's parser preview/save split, fuzzy title matching, local/remote artwork choice, exception-style hiding, and artwork-only Steam parser.
- EmuDeck's guided Steam ROM Manager workflow and clear separation between generating an app list, choosing art, and saving to Steam.
- SGDBoop's idea of making SteamGridDB artwork application convenient while keeping built-in artwork placement available.

## Packaging

For a local single-folder build, PyInstaller is the most practical path:

```powershell
python -m pip install pyinstaller
pyinstaller --noconsole --name SteamShortcutStudio main.py
```

The source version is the primary deliverable here; packaging is optional.

## Tests

Run the smoke tests:

```powershell
python tests\smoke_test.py
```

The smoke tests cover binary VDF round-tripping, executable ranking, duplicate/update behavior, Steam notes, Steam AppID artwork naming, and settings persistence.

## Logs

The visible log panel is mirrored to a rotating file:

```text
%APPDATA%\SteamShortcutStudio\logs\steam_shortcut_studio.log
```

Use `Settings > Show Log File Path` to see the exact file. The app keeps up to four rotated backups. HTTP 404 entries from Steam artwork usually mean that optional CDN asset does not exist for that AppID. HTTP 429 entries from Wikimedia mean the remote service is rate-limiting requests; scan-time preloading is now local-only and reserves remote sources for manual searches or `Find Art`.

## Limitations and Future Improvements

- Steam must be restarted after shortcut changes.
- SteamGridDB and RAWG require user-provided API keys.
- Steam artwork filename behavior is implemented for common modern Steam grid assets, but Valve does not provide a stable public contract for every client variation.
- Note/artwork lookup is intentionally conservative. IGDB and MobyGames can be added later, but both need API credentials or stricter usage rules.
- The current UI is a practical native Tkinter app. A future WPF or PySide6 front end could add richer image browsing and theming.
- `shortcuts.vdf` unknown fields are normalized to the supported shortcut schema when writing.
