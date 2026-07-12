# Steam Shortcut Studio CLI

The CLI exposes the new read-only launcher discovery, persistent library, and transaction-history foundations before the modern GUI is connected to them.

It does not write Steam shortcuts or artwork.

## Epic Scan

Use Epic's default manifest directory and the default local library database:

```powershell
python -m steam_shortcut_studio.cli scan-epic
```

Use explicit paths:

```powershell
python -m steam_shortcut_studio.cli scan-epic `
  --manifest-dir "C:\ProgramData\Epic\EpicGamesLauncher\Data\Manifests" `
  --database "$env:APPDATA\SteamShortcutStudio\library.sqlite3"
```

Machine-readable output:

```powershell
python -m steam_shortcut_studio.cli scan-epic --json
```

Exit codes:

- `0`: authoritative scan completed and was persisted
- `2`: scan was blocked or partial; stored presence was left unchanged
- `1`: command or local I/O error

A missing manifest directory, malformed manifest, source mismatch, or adapter crash does not mark previously stored games missing.

## List Persistent Library

```powershell
python -m steam_shortcut_studio.cli list-library
```

Useful options:

```powershell
python -m steam_shortcut_studio.cli list-library --source epic
python -m steam_shortcut_studio.cli list-library --include-missing
python -m steam_shortcut_studio.cli list-library --json
```

The list uses effective values after manual overrides and includes artwork locks and rejected matches in JSON output.

## Launcher Scan History

```powershell
python -m steam_shortcut_studio.cli scan-history
python -m steam_shortcut_studio.cli scan-history --source epic --limit 20 --json
```

## Transaction and Restore-Point History

```powershell
python -m steam_shortcut_studio.cli transaction-history
python -m steam_shortcut_studio.cli transaction-history --json
```

This command is read-only. It reports transaction state and whether a restore backup exists, but does not restore or delete files.

## Default Paths

Library database:

```text
Windows:
%APPDATA%\SteamShortcutStudio\library.sqlite3

Linux:
~/.config/SteamShortcutStudio/library.sqlite3
```

Epic manifests:

```text
%PROGRAMDATA%\Epic\EpicGamesLauncher\Data\Manifests
```
