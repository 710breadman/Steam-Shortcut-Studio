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

Open the real modern interface (this one can write Steam, but only via Apply
Changes, and only through the verified transaction services):

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

1. Build the bulk artwork review queue in the modern shell, then wire the
   top-bar `Auto-Art` tile and bulk `Find Art` button to
   `BulkArtworkCoordinator` behind it. This is the only functional stub left in
   the modern shell.
2. Replace the hardcoded 70/60 confidence placeholders with real identity and
   set-coherence scoring, so `ArtworkMatchPolicy`'s auto-accept path (92/85)
   becomes reachable instead of routing every match to review.
3. Add GOG, Playnite, EA, Ubisoft, and Battle.net adapters.
4. Reduce `ui.py` (still 5,600+ lines) as the modern shell takes over its
   workflows; retire legacy paths only once the modern equivalent is proven.
5. Expand safe native Steam controls only after field ownership research and
   rollback tests.

## Completed Since the Last Revision

- `LibraryController` is connected to both the legacy UI and the modern shell.
- Artwork and metadata provider orchestration is extracted from `ui.py`.
- Real provider results reach `BulkArtworkCoordinator` on the legacy path.
- Transaction history is connected to the Backups views, including artwork
  transactions, which were previously invisible everywhere.
- The modern shell writes real shortcuts and copies real locked artwork into
  Steam through the existing verified transaction services.

## Work Boundary

Do not rebuild transaction, queue, persistence, source-adapter, or selection foundations. The next engineering work should consume them through controller/view boundaries.
