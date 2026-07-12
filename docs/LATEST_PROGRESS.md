# Latest Project Progress

Updated after the production controller and three-source persistent library foundations were completed.

## Production-Safe and Live

- Transactional `shortcuts.vdf` writes
- Malformed active VDF blocking
- Staged validation and read-back verification
- Automatic shortcut rollback
- Atomic per-game Steam artwork-set writes
- Invalid-image blocking before writes
- Full artwork-set rollback and stale extension cleanup
- Transaction and restore-point history

## Persistent Personal Library

The app-owned SQLite library now supports:

- Native Steam games
- Epic Games Launcher games
- Loose/local game folders
- Stable source IDs
- Missing/reappearing state
- Manual title and launch overrides
- Personal notes
- Artwork slot locks
- Rejected artwork candidates
- Scan history

Unavailable or partial source scans do not mark existing games missing.

## Usable Commands

Epic:

```powershell
python -m steam_shortcut_studio.cli scan-epic
```

Native Steam:

```powershell
python -m steam_shortcut_studio.source_cli scan-steam `
  --steam-root "C:\Program Files (x86)\Steam"
```

Loose/local folder:

```powershell
python -m steam_shortcut_studio.source_cli scan-folder `
  --root "D:\PC Games"
```

Inspect stored library:

```powershell
python -m steam_shortcut_studio.cli list-library
```

Open real stored games in the approved modern read-only interface:

```powershell
python -m pip install -r requirements-ui-prototype.txt
python prototypes/modern_library.py
```

## Completed Modernization Foundations

- Tk-free immutable `LibraryController`
- Stable `SelectionState`
- Bounded `BackgroundJobQueue`
- UI-safe immutable events
- Selected-game artwork coordinator
- Missing-only, all-unlocked, and complete-set artwork modes
- Automatic accept/review/reject policy routing
- Twenty-item queue tests
- Read-only modern dark-blue prototype with real persistent data

## Remaining High-Priority Work

1. Connect `LibraryController` to the production legacy UI incrementally.
2. Replace the production game list with the modern multi-select table.
3. Extract artwork/metadata provider orchestration from `ui.py`.
4. Connect real provider results to `BulkArtworkCoordinator`.
5. Build the production artwork review queue and progress controls.
6. Connect transaction history to the production Backups view.
7. Add GOG, Playnite, EA, Ubisoft, and Battle.net adapters.
8. Expand safe native Steam controls only after field ownership research and rollback tests.

## Work Boundary

Do not rebuild transaction, queue, persistence, source-adapter, or selection foundations. The next engineering work should consume them through controller/view boundaries.
