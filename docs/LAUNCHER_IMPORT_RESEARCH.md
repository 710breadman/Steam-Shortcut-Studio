# Launcher Import Research

## Goal

Prefer launcher-owned installation metadata over recursive executable guessing. Folder scanning remains the fallback for portable games and unsupported launchers.

## Priority Order

1. Epic Games Launcher
2. GOG Galaxy
3. Playnite
4. EA app
5. Ubisoft Connect
6. Battle.net
7. Heroic, Lutris, Legendary, and Bottles on SteamOS/Bazzite

Each launcher should implement the shared read-only `SourceAdapter` contract and return stable `SourceLibraryItem` records plus explicit issues. Import adapters must not modify launcher files.

## Epic Games Launcher

### Primary implementation reference

The open-source Legendary client currently reads Epic Games Launcher manifests from:

```text
%PROGRAMDATA%\Epic\EpicGamesLauncher\Data\Manifests
```

It loads files ending in `.item` as JSON and indexes them by `AppName`.

Reference:

- `legendary-gl/legendary/legendary/lfs/egl.py`
- `legendary-gl/legendary/legendary/models/egl.py`

### Useful manifest fields

| Epic field | Steam Shortcut Studio use |
| --- | --- |
| `DisplayName` | Preferred display title |
| `AppName` | Fallback title and external identity |
| `CatalogNamespace` + `CatalogItemId` | Strong external identity |
| `InstallLocation` | Installation root |
| `LaunchExecutable` | Authoritative launch target relative to the install root |
| `LaunchCommand` | Launch arguments |
| `AppVersionString` | Installed version |
| `InstallSize` | Installed size |
| `InstallationGuid` | Additional installation evidence |
| `MainGameAppName` | Base-game relationship evidence |
| `bIsExecutable` | Skip non-executable components |
| `bIsIncompleteInstall` | Skip incomplete installations |
| `bCanRunOffline` | Informational metadata |
| `bNeedsValidation` | Surface a review/status warning later |

### Safety rules

- Read `.item` files only.
- Never rewrite, delete, or normalize Epic manifests.
- Skip incomplete installations and explicitly non-executable components.
- Keep malformed files isolated so one bad manifest cannot block the whole scan.
- Retain entries with a missing launch executable for manual review rather than inventing one.
- Flag launch targets outside `InstallLocation` for review.
- Do not require Windows paths to exist when parsing fixtures or a library copied from another machine.
- Prefer catalog identity over title matching.

### Current implementation

`steam_shortcut_studio/sources/epic.py` implements the initial read-only adapter. It is not yet connected to the production scan UI.

## Shared Adapter Requirements

Every future adapter should provide:

- Stable source-specific ID
- Display title
- Source name
- External/store identity
- Installation path
- Launch target and arguments
- Working directory
- Platform
- Source record path
- Identity evidence
- Structured warnings/errors

Adapters should not return raw launcher-specific objects to the UI. Launcher data should be converted into the shared source model and later reconciled with the persistent library model.

## Next Research

### GOG Galaxy

Determine the safest read-only source of installed-game identity and launch data. Galaxy database access must use read-only SQLite mode and tolerate schema changes. Avoid taking locks on the live database.

### Playnite

Treat Playnite as a user-curated source. Preserve its game IDs, custom names, launch actions, and emulator associations. Do not assume every Playnite entry represents an installed native PC game.

### EA, Ubisoft, and Battle.net

Document each launcher's manifest/database ownership, locking behavior, installation state fields, launch protocol, and reliable external identity before implementation.
