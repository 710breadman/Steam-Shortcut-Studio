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

- [x] Extract current provider searches from `ui.py`
- [x] Convert provider responses into validated coordinator outcomes
- [x] Persist accepted/rejected candidate decisions through the library store
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
- [x] Persistent library row mapping is shared through a production package view model
- [x] Manual-title-aware ordering
- [x] Multi-game selection
- [x] Prototype selection state uses shared `SelectionState`
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
- [x] Persistent library snapshot display update and loaded-status text are produced outside `ui.py`
- [x] Persistent library detail notes and read-only reason text are produced outside `ui.py`
- [x] Stored library rows remain read-only in the legacy Steam write path
- [x] Legacy UI can queue Epic, Steam, and folder source scans through `LibraryController`
- [x] Poll `BackgroundJobQueue` events from the UI thread for source-scan jobs
- [x] Production table exposes persistent source, platform/size, and status columns for controller-backed rows
- [x] Persistent library table row mapping is available outside the prototype package
- [x] Production table stored-row values use the shared modern library row model
- [x] Production table filtering and filter status text use the shared modern library view model
- [x] Production table column and preset sorting use the shared modern library view model
- [x] Production table row value assembly uses the shared modern library view model
- [x] Production table row tags and column display state use the shared modern library view model
- [x] Persistent row checkbox and selection-menu actions mutate `SelectionState` by stable library ID
- [x] Shift-clicking persistent row checkboxes selects visible stable-ID ranges without touching hidden rows
- [x] Ctrl-clicking persistent table rows toggles stable-ID selection through `SelectionState`
- [x] Space toggles the focused persistent row through the same stable-ID selection path
- [x] Selection menu exposes explicit visible-scope actions and the table shows selected/visible counts
- [x] Selection menu exposes explicit current-filter actions alongside visible/all scopes
- [x] Selected/visible summary text is produced by a Tk-free selection summary model
- [x] Selection action status labels are produced by a Tk-free selection action model
- [x] Selected persistent item ID scope is resolved by a Tk-free adapter helper
- [x] Persistent artwork queue item scope and game lookup use Tk-free adapter helpers
- [x] Bulk stable-ID selection, inversion, and range selection are exposed through `LibraryController`
- [x] Source-scan terminal events surface review/failure issue codes from the Tk thread
- [x] Production table has a selected-row source refresh action backed by `LibraryController.selected_sources`
- [x] Selected source refresh adapter/unavailable planning is outside `ui.py`
- [x] Source refresh jobs show per-source queued/running progress from UI-polled job events
- [x] Reviewed/failed source refresh jobs can be retried through the controller queue
- [x] Reviewed source refresh jobs can be cleared after handling
- [x] Source-scan job IDs, progress, retry state, and finish summaries are extracted from `ui.py`
- [x] Source-scan empty/retry messages are produced outside `ui.py`
- [x] Combined Steam/folder scan readiness and step-count planning are extracted from `ui.py`
- [x] Combined Steam/folder scan progress and final status messages are extracted from `ui.py`
- [x] Folder-only scan root planning and status messages are extracted from `ui.py`
- [x] Steam-only scan path validation and status messages are extracted from `ui.py`
- [x] Steam live scan found-count status is extracted from `ui.py`
- [x] Scan result duplicate/shortcut merge logic is extracted from `ui.py`
- [x] Existing shortcut comparison planning is extracted from `ui.py`
- [x] Selected persistent rows can be queued through `BulkArtworkCoordinator` using real provider search and review-safe validated outcomes
- [x] Provider result conversion has a UI-independent adapter for real provider wiring
- [x] Current real artwork provider search orchestration is extracted behind a UI-independent `ArtworkProviderSearchService`
- [x] Metadata refresh target selection is extracted from `ui.py`
- [x] Metadata provider selection and `MetadataService` construction are extracted from `ui.py`
- [x] Artwork review dialog is backed by a UI-independent row mapper and shows selected slot previews
- [x] Artwork review selected/pending slot summaries are produced outside `ui.py`
- [x] Artwork review accept/reject/skip result messages are produced outside `ui.py`
- [x] Artwork review queue can skip pending candidates without persisting accept/reject decisions
- [x] Artwork review queue can retry selected pending items without rerunning accepted rows
- [x] Artwork queue item/submission status messages are produced outside `ui.py`
- [x] Artwork slot select/clear/refresh/open status messages are produced outside `ui.py`
- [x] Selection target and review-clear status messages are produced outside `ui.py`
- [x] Select-needing-artwork and select-new-shortcut target planning is extracted from `ui.py`
- [x] Select-needing-artwork and select-new-shortcut target application is extracted from `ui.py`
- [x] Steam write target selection and current-row fallback planning are extracted from `ui.py`
- [x] Backups action shows transaction history through a UI-independent view model
- [x] Transaction/history controller exposes backup and manifest open targets without Tk dependencies
- [ ] Extract scan orchestration from `ui.py`
- [x] Extract metadata/provider orchestration from `ui.py`
- [ ] Extract selection and bulk-action controllers
- [x] Extract transaction/history controller
- [ ] Build production modern library table using `LibraryStore`
- [ ] Use `SelectionState` instead of widget-local IDs
- [x] Connect the Backups view to transaction history
- [x] Connect the artwork review workspace to `BulkArtworkCoordinator`
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
python tests/selection_summary_test.py
python tests/selection_actions_test.py
python tests/transaction_test.py
python tests/file_transaction_test.py
python tests/shortcut_transaction_test.py
python tests/app_transaction_wiring_test.py
python tests/transaction_history_test.py
python tests/transaction_history_controller_test.py
python tests/transaction_history_view_test.py
python tests/job_queue_test.py
python tests/bulk_artwork_test.py
python tests/artwork_provider_adapter_test.py
python tests/artwork_queue_status_test.py
python tests/metadata_targets_test.py
python tests/metadata_service_factory_test.py
python tests/artwork_review_workspace_test.py
python tests/epic_source_test.py
python tests/steam_folder_source_test.py
python tests/scan_plan_test.py
python tests/library_store_test.py
python tests/source_scan_test.py
python tests/source_scan_ui_state_test.py
python tests/library_controller_test.py
python tests/ui_library_adapter_test.py
python tests/settings_store_test.py
python tests/cli_test.py
python tests/source_cli_test.py
python tests/image_validation_test.py
python tests/artwork_transaction_test.py
python tests/artwork_live_transaction_test.py
```

Optional modern UI import, persistent-library mapping, and prototype shell selection are tested separately on Windows and Ubuntu.

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
- Added stable-ID visible-range selection for persistent library checkbox rows
- Added keyboard Space selection for focused persistent rows through the shared stable-ID toggle path
- Added explicit Select/Clear/Invert visible commands plus a selected/visible count affordance in the production table toolbar
- Added source-scan event summaries that include review/failure issue codes in UI-thread status/log updates
- Added `Refresh Selected Sources`, which derives selected persistent source types from stable IDs and queues only those controller-backed scans
- Added `SelectedSourceScanPlan` so selected source refresh availability is computed outside `ui.py`
- Re-ran the full local Windows Python 3.11 CI-equivalent suite after selected source scan plan extraction; all commands in `Validation`, `tests/source_cli_test.py`, and optional prototype checks passed
- Added per-source progress summaries for queued/running source refresh jobs from immutable job events
- Added `LibraryController.retry_scan` plus a production `Retry Source Reviews` action for source refresh jobs that ended in review or failure
- Added `Clear Source Reviews` to dismiss remembered source refresh review/failure jobs after handling
- Added `Plan Selected Art`, which maps selected persistent rows to `BulkArtworkItem` records and runs them through the existing coordinator without Steam writes or live provider coupling
- Added `steam_shortcut_studio/artwork_provider_adapter.py` to convert provider assets into `ArtworkSearchOutcome` outside `ui.py`
- Re-ran the full local Windows Python 3.11 CI-equivalent suite on 2026-07-13; all production, source CLI, and optional prototype checks passed after installing `requirements-ui-prototype.txt` in the user site
- Added `steam_shortcut_studio/artwork_search_service.py` as a Tk-free real provider search boundary for Steam, SteamGridDB, Wikimedia, and RAWG candidates, plus `tests/artwork_search_service_test.py`
- Re-ran the full local Windows Python 3.11 CI-equivalent suite after the provider-service extraction; all commands in `Validation`, `tests/source_cli_test.py`, and optional prototype checks passed
- Connected `Plan Selected Art` to real provider search, download, and `validate_artwork_file` before producing review-safe `ArtworkSearchOutcome` records for `BulkArtworkCoordinator`
- Re-ran the full local Windows Python 3.11 CI-equivalent suite after validated provider outcomes were wired; all commands in `Validation`, `tests/source_cli_test.py`, and optional prototype checks passed
- Added controller persistence for artwork job results: accepted candidates become stored artwork locks and rejected candidates become `RejectedMatch` rows in `LibraryStore`
- Re-ran the full local Windows Python 3.11 CI-equivalent suite after artwork result persistence; all commands in `Validation`, `tests/source_cli_test.py`, and optional prototype checks passed
- Added production table controls to show persisted artwork decision counts and clear rejected artwork candidates for selected persistent rows
- Re-ran the full local Windows Python 3.11 CI-equivalent suite after artwork decision controls; all commands in `Validation`, `tests/source_cli_test.py`, and optional prototype checks passed
- Added production accept/reject actions for latest review-needed artwork results on selected persistent rows
- Re-ran the full local Windows Python 3.11 CI-equivalent suite after artwork review actions; all commands in `Validation`, `tests/source_cli_test.py`, and optional prototype checks passed
- Added an artwork decisions dialog that lists pending review candidates with slot, candidate ID, and validated file path for selected persistent rows
- Re-ran the full local Windows Python 3.11 CI-equivalent suite after the artwork decisions dialog; all commands in `Validation`, `tests/source_cli_test.py`, and optional prototype checks passed
- Added Ctrl-click additive selection for persistent table rows through the controller-backed stable-ID selection path
- Re-ran the full local Windows Python 3.11 CI-equivalent suite after Ctrl-click selection wiring; all commands in `Validation`, `tests/source_cli_test.py`, and optional prototype checks passed
- Moved persistent table bulk selection, inversion, and range selection operations onto `LibraryController` helpers with Tk-free tests
- Re-ran the full local Windows Python 3.11 CI-equivalent suite after controller selection extraction; all commands in `Validation`, `tests/source_cli_test.py`, and optional prototype checks passed
- Added a UI-independent artwork review row mapper and upgraded the artwork decisions dialog with per-slot preview/details for pending provider candidates
- Re-ran the full local Windows Python 3.11 CI-equivalent suite after artwork review slot previews; all commands in `Validation`, `tests/source_cli_test.py`, and optional prototype checks passed
- Added `ArtworkReviewSummary` so selected item, pending item, and pending slot counts are tested outside `ui.py`
- Re-ran the full local Windows Python 3.11 CI-equivalent suite after artwork review summary extraction; all commands in `Validation`, `tests/source_cli_test.py`, and optional prototype checks passed
- Moved selected pending artwork review result lookup into `artwork_review_workspace.py`
- Added artwork review action message helpers so accept/reject/skip result text is tested outside `ui.py`
- Re-ran the full local Windows Python 3.11 CI-equivalent suite after artwork review action summary extraction; all commands in `Validation`, `tests/source_cli_test.py`, and optional prototype checks passed
- Moved artwork review selection-required and no-pending messages into `artwork_review_workspace.py`
- Added `artwork_queue_status.py` so artwork queue item/submission status text is tested outside `ui.py`
- Re-ran the full local Windows Python 3.11 CI-equivalent suite after artwork queue status extraction; all commands in `Validation`, `tests/source_cli_test.py`, and optional prototype checks passed
- Added `SourceScanUiState` to own source-scan job tracking, progress summaries, retry state, and finish summaries outside `ui.py`
- Re-ran the full local Windows Python 3.11 CI-equivalent suite after source-scan UI state extraction; all commands in `Validation`, `tests/source_cli_test.py`, and optional prototype checks passed
- Added a production `Backups` action that reads verified transaction history through a UI-independent view model and lists restore-backup availability plus manifest paths
- Re-ran the full local Windows Python 3.11 CI-equivalent suite after connecting the Backups view to transaction history; all commands in `Validation`, `tests/source_cli_test.py`, and optional prototype checks passed
- Moved production Backups detail text into the transaction history view model for modern UI reuse
- Added `Skip Art Review` controls that dismiss pending review candidates without storing accept/reject decisions, backed by a UI-independent slot-count helper
- Re-ran the full local Windows Python 3.11 CI-equivalent suite after artwork review skip controls; all commands in `Validation`, `tests/source_cli_test.py`, and optional prototype checks passed
- Added `Retry Art Review` controls that requeue only selected pending review items through `BulkArtworkCoordinator`
- Re-ran the full local Windows Python 3.11 CI-equivalent suite after artwork review retry controls; all commands in `Validation`, `tests/source_cli_test.py`, and optional prototype checks passed
- Marked the artwork review workspace as connected to `BulkArtworkCoordinator`: pending review rows are built from coordinator job results and retry requeues selected pending items through the coordinator
- Re-ran the full local Windows Python 3.11 CI-equivalent suite after marking artwork review workspace/coordinator connection complete; all commands in `Validation`, `tests/source_cli_test.py`, and optional prototype checks passed
- Moved artwork decisions dialog header, empty-state, detail, and status text into `artwork_review_workspace.py`
- Added explicit current-filter select/clear/invert commands so matching-filter scope is visible alongside all/visible scopes
- Re-ran the full local Windows Python 3.11 CI-equivalent suite after current-filter selection commands; all commands in `Validation`, `tests/source_cli_test.py`, and optional prototype checks passed
- Moved selected metadata refresh empty-state and completion text into `metadata_targets.py`
- Added `TransactionHistoryController` so the Backups UI gets history rows, backup folder targets, and manifest targets through a Tk-free controller
- Re-ran the full local Windows Python 3.11 CI-equivalent suite after transaction/history controller extraction; all commands in `Validation`, `tests/source_cli_test.py`, and optional prototype checks passed
- Added `CombinedScanPlan` so combined Steam/folder scan readiness and progress step counts are decided outside `ui.py`
- Re-ran the full local Windows Python 3.11 CI-equivalent suite after combined scan plan extraction; all commands in `Validation`, `tests/source_cli_test.py`, and optional prototype checks passed
- Added `CombinedScanCounts` and combined-scan message helpers so scan progress/final status text is tested outside `ui.py`
- Re-ran the full local Windows Python 3.11 CI-equivalent suite after combined scan status extraction; all commands in `Validation`, `tests/source_cli_test.py`, and optional prototype checks passed
- Added `FolderScanPlan` and folder scan message helpers so folder-only scan planning/status text is tested outside `ui.py`
- Re-ran the full local Windows Python 3.11 CI-equivalent suite after folder scan plan extraction; all commands in `Validation`, `tests/source_cli_test.py`, and optional prototype checks passed
- Added `SteamScanPlan` and Steam scan message helpers so Steam-only scan validation/status text is tested outside `ui.py`
- Re-ran the full local Windows Python 3.11 CI-equivalent suite after Steam scan plan extraction; all commands in `Validation`, `tests/source_cli_test.py`, and optional prototype checks passed
- Moved scan validation warning text for combined, folder, and Steam scans into `scan_plan.py`
- Added a Tk-free `SelectionSummary` model for selected/visible table status text
- Re-ran the full local Windows Python 3.11 CI-equivalent suite after selection summary extraction; all commands in `Validation`, `tests/source_cli_test.py`, and optional prototype checks passed
- Added mixed selection summary counting so persistent rows use controller `SelectionState` IDs while transient scan rows keep local flags
- Added `selection_actions.py` so selection command status labels are tested outside `ui.py`
- Re-ran the full local Windows Python 3.11 CI-equivalent suite after selection action status extraction; all commands in `Validation`, `tests/source_cli_test.py`, and optional prototype checks passed
- Added `selected_visible_library_item_ids` so visible selected persistent-row scope is tested outside `ui.py`
- Re-ran the full local Windows Python 3.11 CI-equivalent suite after selected persistent scope extraction; all commands in `Validation`, `tests/source_cli_test.py`, and optional prototype checks passed
- Added `library_games_by_item_id` and reused selected persistent scope for artwork queue planning outside `ui.py`
- Re-ran the full local Windows Python 3.11 CI-equivalent suite after persistent artwork queue scope extraction; all commands in `Validation`, `tests/source_cli_test.py`, and optional prototype checks passed
- Replaced prototype-local selected ID storage with shared `SelectionState` while keeping the read-only modern shell behavior intact
- Re-ran the full local Windows Python 3.11 CI-equivalent suite after prototype `SelectionState` wiring; all commands in `Validation`, `tests/source_cli_test.py`, and optional prototype checks passed
- Added `metadata_targets.py` so selected/current metadata-refresh target selection and native Steam exclusion are tested outside `ui.py`
- Re-ran the full local Windows Python 3.11 CI-equivalent suite after metadata target extraction; all commands in `Validation`, `tests/source_cli_test.py`, and optional prototype checks passed
- Added `metadata_service_factory.py` so metadata provider toggles and `MetadataService` construction are tested outside `ui.py`
- Re-ran the full local Windows Python 3.11 CI-equivalent suite after metadata service factory extraction; all commands in `Validation`, `tests/source_cli_test.py`, and optional prototype checks passed

## Known Risks

- `ui.py` still contains too many responsibilities
- Current provider download, auto-selection, and review presentation still run through the legacy UI path
- The prototype must not become a second implementation of domain logic
- Native Steam setting ownership varies by platform and may be overwritten by Steam
- The custom VDF parser needs broader fixtures before supporting unknown future field types
- New launcher database adapters must avoid locking or modifying live launcher data

## Exact Next Action

Connect the production modern library table and selected-item actions incrementally on top of the controller-backed source scan bridge.

Next controller-backed UI work:

1. Build the fuller artwork review workspace around persisted candidates and slot previews.
2. Preserve stored-row read-only behavior in all Steam write paths.
3. Keep the legacy scan/write workflows available during migration.
4. Add no new Steam writes.

## Next Codex Prompt

```text
Read CODEX_START_HERE.md and all linked docs. The shortcut and artwork write paths are already transactional, verified, and live. Do not rebuild them. Work on issue #4 / Sprint 04 only: extract a production library controller/service boundary from ui.py. It must read LibraryStore records, run SourceScanCoordinator jobs through BackgroundJobQueue, expose immutable library rows/events, and keep the legacy UI operational. No full UI rewrite in one change. No new Steam fields or write paths. Use stable IDs. Add controller tests without constructing a Tk window. Run the complete existing suite and update SPRINT_STATUS with exact evidence. Small reviewable commits.
```
