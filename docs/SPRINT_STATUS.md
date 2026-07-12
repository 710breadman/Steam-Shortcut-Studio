# Steam Shortcut Studio Sprint Status

## Start Here

This is the persistent handoff for ChatGPT, Codex, and future development sessions.

Before changing code:

1. Read `CODEX_START_HERE.md` and its linked documents.
2. Inspect the current branch and recent merged pull requests.
3. Run the baseline tests relevant to the work.
4. Keep UI refactoring, launcher adapters, and Steam-write changes in separate pull requests.
5. Update this file with evidence before ending an implementation session.

## Current Position

- **Completed:** Sprint 00 — Baseline and Repository Audit
- **Completed:** Sprint 01 — Transactional `shortcuts.vdf`
- **Completed:** Sprint 02 — Transaction History Foundation
- **Completed:** Sprint 03 — Atomic Artwork Validation and Rollback
- **Foundation complete:** Sprint 05 — Stable Library Identity and Persistence
- **Foundation complete:** Sprint 07 — Background Job Queue
- **Foundation complete:** Sprint 09-10 — Artwork Policy and Selected-Game Coordinator
- **First launcher complete:** Epic Games Launcher read-only manifest adapter
- **Current controller foundation:** Tk-free persistent `LibraryController`
- **Additional sources complete:** read-only native Steam and loose-folder adapters
- **Current active engineering track:** Production modern-library UI integration
- **Next visible milestone:** Production modern library view backed by persistent data
- **Priority feature after that:** Real provider integration for `Find Artwork for Selected`

## Approved Product Decisions

- Personal library first
- Native Steam and non-Steam games in one library
- Launcher manifests preferred; folder scanning remains fallback
- Windows launcher support before SteamOS/Bazzite adapters
- Safe automation only; risky or uncertain changes require review
- Strong complete artwork matches may auto-apply
- Weak, incomplete, conflicting, or manually locked artwork requires review
- Game installation files are never modified
- Accent/theme options remain
- Modern dark blue UI by default

## Production Safety — Complete

### Transactional Shortcut Writes

- [x] Production desktop `upsert_games` routes through the strict transaction service
- [x] Proposed VDF is staged and parsed before apply
- [x] Existing active VDF is backed up in an app-owned transaction directory
- [x] Original, staged, and written SHA-256 hashes are recorded
- [x] Same-directory atomic replacement is used
- [x] Written VDF is read back and verified
- [x] Unrelated shortcuts and user-managed fields are preserved
- [x] Verification failure restores the exact original
- [x] Newly created files are removed after failed transactions
- [x] Malformed active VDF blocks the write and remains untouched
- [x] Preview clearly reports the blocked condition

### Atomic Artwork Writes

- [x] Every source image is decoded before production writes
- [x] A game’s grid, wide, hero, logo, and icon changes are planned as one set
- [x] Stale alternate-extension files are included in the same transaction
- [x] Every affected existing file is backed up before the first change
- [x] Written files are decoded and hash-verified
- [x] Failure restores the entire previous artwork set
- [x] Newly created artwork is removed after failure
- [x] Production no-op is preserved when the selected file is already the exact target
- [x] Old smoke fixtures use real images instead of arbitrary bytes

### Transaction History

- [x] Transaction manifests can be listed newest-first
- [x] Restore-backup availability is detectable
- [x] Invalid manifests are isolated and reported
- [x] Conservative retention candidates can be calculated
- [x] Retention helpers never delete files automatically

## Persistent Library — Complete Foundation

- [x] Versioned SQLite schema
- [x] Stable source-specific library IDs
- [x] Normalized source records and identity evidence
- [x] Presence and missing/reappearing state across authoritative scans
- [x] Manual display-title override
- [x] Manual launch target, arguments, and working-directory overrides
- [x] Personal notes
- [x] Artwork slot locks
- [x] Rejected provider candidates
- [x] Scan history
- [x] Explicit SQLite connection closing on Windows and Linux
- [x] Future unsupported schema versions fail safely

## Launcher Sources

### Epic Games Launcher — Complete Read-Only Adapter

- [x] Reads `%PROGRAMDATA%\Epic\EpicGamesLauncher\Data\Manifests\*.item`
- [x] Uses catalog namespace and item ID as strong identity
- [x] Reads display title, install path, launch target, arguments, version, and size
- [x] Skips incomplete installs and non-executable components
- [x] Isolates malformed manifests
- [x] Flags missing or outside-install launch targets for review
- [x] Partial or unavailable scans never mark stored games missing
- [x] CLI can scan and persist Epic games

### Remaining Windows Sources

1. GOG Galaxy
2. Playnite
3. EA app
4. Ubisoft Connect
5. Battle.net

Every new adapter must remain read-only and use the shared `SourceAdapter` model.

### Native Steam and Loose Folder — Complete Read-Only Adapters

- [x] Native Steam adapter maps installed Steam games to stable library records
- [x] Loose-folder adapter persists existing scanner results without writing Steam
- [x] Missing roots and scan failures are non-authoritative and preserve prior presence
- [x] Steam and folder scan CLI commands persist through `SourceScanCoordinator`
- [x] Folder titles keep real title words such as `Game`

## Bulk Work — Complete Foundation

### Selection

- [x] Stable selected IDs
- [x] Active inspector focus separated from bulk selection
- [x] Ordered selected-item resolution

### Background Queue

- [x] Bounded workers
- [x] UI-safe immutable events
- [x] Per-item progress
- [x] Aggregate summaries
- [x] Cancellation
- [x] Isolated failures
- [x] Selective retry
- [x] Review state
- [x] Twenty-item batch tests

### Find Artwork for Selected

- [x] One job per selected stable library ID
- [x] Missing Slots Only mode
- [x] All Unlocked Slots mode
- [x] Complete Set mode
- [x] Manual lock protection
- [x] Strong match → automatic-accept decision
- [x] Weak/conflicting match → review decision
- [x] Invalid/empty result → reject/skip decision
- [x] Valid image metadata and perceptual duplicate foundation
- [x] Atomic production apply service

Remaining:

- [ ] Extract current provider searches from `ui.py`
- [ ] Convert provider responses into validated coordinator outcomes
- [ ] Persist accepted/rejected candidate decisions through the library store
- [ ] Connect progress, review, retry, and apply controls to the production modern UI

## Modern UI

### Read-Only Prototype — Complete

Run the design mock:

```text
python -m pip install -r requirements-ui-prototype.txt
python prototypes/modern_shell.py
```

Run with real persistent library data:

```text
python -m steam_shortcut_studio.cli scan-epic
python prototypes/modern_library.py
```

Implemented:

- [x] Approved dark blue three-column shell
- [x] Accent palette selector
- [x] Left navigation and compact command bar
- [x] Persistent library titles, source, platform, size, and status
- [x] Manual-title-aware ordering
- [x] Multi-game selection
- [x] Contextual bulk action bar
- [x] Visible `Find Art` action
- [x] Artwork inspector and match panel
- [x] Backup/verification/rollback cards
- [x] Missing and review states
- [x] Apply disabled in the prototype
- [x] Windows and Linux import/mapping tests

### Production UI — Remaining

- [x] Tk-free persistent `LibraryController` foundation
- [x] Legacy UI can load persistent library rows through the controller
- [x] Stored library rows remain read-only in the legacy Steam write path
- [x] Legacy UI can queue Epic, Steam, and folder source scans through `LibraryController`
- [x] Poll `BackgroundJobQueue` events from the UI thread for source-scan jobs
- [x] Production table exposes persistent source, platform/size, and status columns for controller-backed rows
- [x] Persistent row checkbox and selection-menu actions mutate `SelectionState` by stable library ID
- [ ] Extract scan orchestration from `ui.py`
- [ ] Extract metadata/provider orchestration from `ui.py`
- [ ] Extract selection and bulk-action controllers
- [ ] Extract transaction/history controller
- [ ] Build production modern library table using `LibraryStore`
- [ ] Use `SelectionState` instead of widget-local IDs
- [ ] Connect the Backups view to transaction history
- [ ] Connect the artwork review workspace to `BulkArtworkCoordinator`
- [ ] Keep legacy UI operational during incremental migration

## Usable Commands Today

```text
python -m steam_shortcut_studio.cli scan-epic
python -m steam_shortcut_studio.source_cli scan-steam --steam-root "C:\Program Files (x86)\Steam"
python -m steam_shortcut_studio.source_cli scan-folder --root "D:\PC Games"
python -m steam_shortcut_studio.cli list-library
python -m steam_shortcut_studio.cli scan-history
python -m steam_shortcut_studio.cli transaction-history
python prototypes/modern_library.py
```

The CLI and prototype do not write Steam shortcuts or artwork.

## Merged Pull Requests

- **#1:** Architecture, roadmap, CI, selection/job/policy/transaction contracts
- **#8:** Verified file transaction engine and strict shortcut service
- **#9:** Read-only modern UI shell
- **#10:** Image validation and perceptual duplicate foundation
- **#11:** Production shortcut transaction integration
- **#14:** Transaction-history foundation
- **#15:** Bounded background queue
- **#16:** Selected-game artwork coordinator
- **#17:** Epic manifest adapter
- **#18:** SQLite library persistence
- **#19:** Conservative launcher scan persistence
- **#20:** Library and Epic scan CLI
- **#22:** Atomic artwork-set transaction engine
- **#23:** Production atomic artwork integration
- **#25:** Persistent-library modern UI prototype
- **#26:** Current status and handoff refresh
- **#27:** Tk-free persistent library controller
- **#28:** Native Steam and loose-folder source adapters

## Issue State

- **#2:** Closed — transactional `shortcuts.vdf` complete
- **#3:** Closed — transaction history and atomic artwork complete
- **#4:** Open — controller foundation complete; production UI wiring remains
- **#5:** Open — production multi-select UI remains; queue and controller foundations complete
- **#6:** Open — real provider/UI integration remains; coordinator and atomic apply complete
- **#7:** Open — production adaptation remains; real-data prototype complete

## Validation

GitHub Actions runs production tests on:

- Windows
- Ubuntu
- Python 3.11
- Python 3.13

Current suites include:

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
python tests/steam_folder_source_test.py
python tests/library_store_test.py
python tests/source_scan_test.py
python tests/library_controller_test.py
python tests/ui_library_adapter_test.py
python tests/settings_store_test.py
python tests/cli_test.py
python tests/source_cli_test.py
python tests/image_validation_test.py
python tests/artwork_transaction_test.py
python tests/artwork_live_transaction_test.py
```

Optional modern UI import and persistent-library mapping are tested separately on Windows and Ubuntu.

Latest local integration evidence, 2026-07-12:

- Merged `agent/library-controller`, `agent/steam-folder-source-adapters`, and `agent/current-status-refresh` into an integration branch from `origin/main`
- Fixed local-folder title cleaning so `Example Game` remains `Example Game`
- Ran every command listed above on Windows; all passed
- Added `steam_shortcut_studio/ui_library_adapter.py` and a legacy `Library` action that loads stored rows through `LibraryController`
- Verified stored library rows do not become shortcut/artwork write candidates in the legacy adapter
- Created local `codex/merge-issues` and ancestry-merged stale `agent/*` branch tips with the `ours` strategy because their trees were older than `origin/main`
- Added a legacy `Sync Sources` action that queues Epic, Steam, and configured folder scans through `LibraryController.scan_source`
- Added Tk-thread polling for controller `BackgroundJobQueue` events, persistent-row refresh after scan terminal/review events, and cancellation wiring for active source scans
- Ran the full local Windows suite listed in `Validation`; all passed
- Added production table columns for persistent source/platform/status data, migrated legacy saved column preferences to include them, and added tests plus CI steps for settings/UI adapter/controller coverage
- Routed persistent table selection changes through stable library IDs and mirrored `SelectionState` back to displayed rows

## Known Risks

- `ui.py` still contains too many responsibilities
- Current provider matching/search orchestration remains coupled to the legacy UI
- The prototype must not become a second implementation of domain logic
- Native Steam setting ownership varies by platform and may be overwritten by Steam
- The custom VDF parser needs broader fixtures before supporting unknown future field types
- New launcher database adapters must avoid locking or modifying live launcher data

## Exact Next Action

Connect the production modern library table and selected-item actions incrementally on top of the controller-backed source scan bridge.

Next controller-backed UI work:

1. Add Shift/Ctrl range/additive gestures for persistent library rows using stable IDs.
2. Preserve stored-row read-only behavior in all Steam write paths.
3. Surface source-scan review/failure details without letting worker threads touch widgets.
4. Keep the legacy scan/write workflows available during migration.
5. Add no new Steam writes.

## Next Codex Prompt

```text
Read CODEX_START_HERE.md and all linked docs. The shortcut and artwork write paths are already transactional, verified, and live. Do not rebuild them. Work on issue #4 / Sprint 04 only: extract a production library controller/service boundary from ui.py. It must read LibraryStore records, run SourceScanCoordinator jobs through BackgroundJobQueue, expose immutable library rows/events, and keep the legacy UI operational. No full UI rewrite in one change. No new Steam fields or write paths. Use stable IDs. Add controller tests without constructing a Tk window. Run the complete existing suite and update SPRINT_STATUS with exact evidence. Small reviewable commits.
```
