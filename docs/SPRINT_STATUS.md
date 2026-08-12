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
- **Write loop complete:** modern shell Apply Changes writes real shortcuts *and* copies locked artwork into Steam's grid folder
- **Bulk artwork complete:** `Auto-Art` / `Find Art` submit through `BulkArtworkCoordinator` into a real review queue on the Artwork screen
- **Shipping complete:** the modern shell is the default interface in packaged builds; `main.py --classic` opens the legacy window
- **Scoring complete:** `artwork_scoring.py` produces real confidence from provider evidence, so strong complete matches auto-accept
- **Current active engineering track:** Remaining Windows launcher adapters (GOG, Playnite, EA, Ubisoft, Battle.net)
- **Next visible milestone:** One library covering every launcher on the machine
- **Launcher fix:** `run.ps1` and `run.bat` now require a Python with `customtkinter`, so repo launch helpers open the modern shell instead of the bundled legacy fallback.
- **Priority feature after that:** Remaining Windows launcher adapters (GOG, Playnite, EA, Ubisoft, Battle.net)
- **Latest UI slice:** `steam_shortcut_studio/modern_shell.py` is the shipped default interface. `main.py` opens it, `main.py --classic` opens the original window, and `run.bat` / `run.ps1` now both run that same entry point. It reads the real persistent library through `LibraryController` / `LibraryStore`, runs every long operation on `BackgroundJobQueue` with Tk-thread polling, and has no mock game data left. Apply Changes performs real transactional shortcut writes *and* real locked-artwork copies into Steam's grid folder in one pass; per-slot and bulk artwork matching are both live.
- **Verification note, 2026-08-12:** every `tests/*_test.py` suite in the repo passes on Windows / Python 3.11, plus `python -m compileall -q steam_shortcut_studio tests main.py` and the CI `ui-prototype` import check. Two suites (`prototype_library_test.py`, `prototype_shell_selection_test.py`) had to be repaired first — see the Validation log for details.

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
- [x] Connect progress, review, retry, and apply controls to the legacy production UI
- [x] Connect bulk `Find Artwork for Selected` to the modern shell behind a real review queue

Both UIs are now wired. The legacy path uses `queue_persistent_artwork_searches`
plus the artwork decisions dialog; the modern shell's top-bar `Auto-Art` tile and
bulk `Find Art` button submit selected rows through `BulkArtworkCoordinator` and
land the results in the Artwork screen's review queue. Both share one real
provider searcher (`artwork_bulk_search.build_provider_searcher`) rather than
keeping a closure each.

Per-slot Auto Match / Replace deliberately bypass the coordinator: a per-slot
click is already one supervised action.

## Modern UI

### Modern Shell — Live and Shipped

The shell lives at `steam_shortcut_studio/modern_shell.py` and is the default
interface in packaged builds, not a prototype in any sense.

```text
python -m pip install -r requirements.txt
python main.py                 # modern shell (default)
python main.py --classic       # original window
python prototypes/modern_library.py   # dev launcher, same shell
```

Implemented:

- [x] Approved dark blue three-column shell
- [x] Accent palette selector
- [x] Left navigation and compact command bar
- [x] Persistent library titles, source, platform, size, and status
- [x] Persistent library row mapping is shared through a production package view model
- [x] Manual-title-aware ordering
- [x] Multi-game selection
- [x] Selection state uses shared `SelectionState` through `LibraryController`
- [x] Startup active-row choice uses Tk-free `initial_active_item_id`
- [x] Contextual bulk action bar
- [x] Artwork inspector with real locked-slot state
- [x] Missing and review states
- [x] Real Steam / Epic / local-folder scans through `LibraryController.scan_source`
- [x] Tools, Settings, and About screens backed by `SettingsStore`
- [x] Backups screen shows both shortcut and artwork transactions
- [x] Windows and Linux import/mapping tests

Write path (all through the existing, unmodified transaction services):

- [x] Apply Changes writes shortcuts via `shortcut_transactions.upsert_games_transactional`
- [x] Apply Changes copies locked artwork via `artwork.copy_all_artwork_to_steam`
- [x] Both run in one background job inside one Steam-closed window
- [x] Preview and confirm report shortcut and artwork eligibility separately, with per-row skip reasons
- [x] Per-game artwork failures are surfaced, not swallowed as legacy `ui.py` does
- [x] Per-slot Auto Match / Replace / Clear operate on local cache + SQLite only

Bulk artwork review queue (live):

- [x] Top-bar `Auto-Art` and bulk `Find Art` submit selected rows through `BulkArtworkCoordinator`
- [x] Submission scope is an explicit `SelectionState` built from the passed IDs, so a retry cannot widen into the live table selection
- [x] Both UIs share one real provider searcher, `artwork_bulk_search.build_provider_searcher`
- [x] `ArtworkReviewQueue` holds `NEEDS_REVIEW` results Tk-free; auto-accepted and policy-rejected decisions persist themselves through `LibraryController`
- [x] Artwork screen shows pending items with per-slot candidate previews decoded from the validated cache file
- [x] Accept / Reject / Skip / Retry per item, plus Accept All / Reject All / Skip All
- [x] Accept locks locally only — Apply Changes stays the single path into Steam
- [x] Failed jobs surface their error instead of being queued as reviewable

Shipping and polish (live):

- [x] The shell is packaged and shipped — `main.py` opens it by default, `--classic` opens the legacy window, and a missing GUI dependency degrades to the classic window instead of failing to start
- [x] `requirements.txt`, the PyInstaller spec, and the Linux release build all collect `customtkinter`
- [x] `run.bat` and `run.ps1` run the same entry point as a packaged build (they previously launched two *different* UIs)
- [x] Artwork tab shows the real locked image, its provider, and an explicit "file missing" state when the cache entry is gone
- [x] Footer cancel control appears while this shell's jobs are in flight
- [x] About screen exposes settings path, library database path, and a way into the classic interface
- [x] Details tab edits manual overrides (title, launch target, arguments, working directory, notes) with a reset-to-source action — previously the shell could only display them, forcing users into the classic UI to rename a game
- [x] Empty-state guidance on the Library screen, distinguishing an empty library (offering the three scans) from a filter that hides everything (offering to clear it)
- [x] Closing the window cancels the poll loop and releases `LibraryController`'s worker threads, which previously stayed alive after the window was gone
- [x] The `LAST PLAYED` column shows Steam's own record and is sortable; it previously showed a hardcoded em dash for every row

Confidence scoring (live):

- [x] `artwork_scoring.py` scores identity and set coherence from real provider evidence — no placeholders remain
- [x] `artwork_search_service` stamps match provenance (`sss_match`) so scoring knows whether a game was resolved by AppID or by name
- [x] Identity is the weakest slot's confidence, not the average, so one wrong image cannot ride along with four certain ones
- [x] Edition and year conflicts populate `ArtworkEvidence`, and are suppressed for identifier-resolved matches (the policy checks conflicts before scores, so a certain match must not be sent to review over edition wording)
- [x] Wrong-shape images and name-resolved provider spread reduce set coherence
- [x] Strong complete matches now reach `AUTO_ACCEPT`; weak ones still route to the review queue and wrong games are rejected
- [x] The review queue shows the measured confidence and the reason for it

Not yet done:

- [ ] Validate the scoring thresholds against a labelled corpus of real matches
- [ ] Per-slot candidate alternatives in the review queue (it shows the one validated candidate per slot the searcher selected)
- [ ] Cancel control for in-flight bulk artwork jobs in the modern shell
- [ ] Extensions screen (placeholder text only)
- [ ] `_visible_rows` search/filter/sort still duplicates `modern_library_view.py` logic instead of reusing it

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
- [x] Artwork planning empty-state messages are produced outside `ui.py`
- [x] Artwork slot select/clear/refresh/open status messages are produced outside `ui.py`
- [x] Selection target and review-clear status messages are produced outside `ui.py`
- [x] Select-needing-artwork and select-new-shortcut target planning is extracted from `ui.py`
- [x] Select-needing-artwork and select-new-shortcut target application is extracted from `ui.py`
- [x] Steam write target selection and current-row fallback planning are extracted from `ui.py`
- [x] Backups action shows transaction history through a UI-independent view model
- [x] Transaction/history controller exposes backup and manifest open targets without Tk dependencies
- [x] Extract scan orchestration from `ui.py`
- [x] Extract metadata/provider orchestration from `ui.py`
- [x] Extract selection and bulk-action controllers
- [x] Extract transaction/history controller
- [x] Build production modern library table using `LibraryStore`
- [x] Use `SelectionState` instead of widget-local IDs
- [x] Connect the Backups view to transaction history
- [x] Connect the artwork review workspace to `BulkArtworkCoordinator`
- [x] Keep legacy UI operational during incremental migration

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

The CLI never writes Steam shortcuts or artwork — it only touches the app-owned
SQLite database. The modern shell (`prototypes/modern_library.py`) **does** write
Steam, but only when you click Apply Changes, and only through the verified
transaction services.

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
- **#4:** Closed — retired after branch cleanup
- **#5:** Closed — retired after branch cleanup
- **#6:** Closed — retired after branch cleanup
- **#7:** Closed — retired after branch cleanup

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

Modern shell integration evidence, 2026-08-11 to 2026-08-12 (commits `53c398b`, `3736998`, `b599cdc`):

- Replaced the mock-data modern prototype with a real `LibraryController` / `LibraryStore`-backed shell and pointed `run.bat` / `run.ps1` at it
- Added `ui_library_adapter.writable_game_from_library_row` / `writable_game_skip_reason` and wired Apply Changes to `shortcut_transactions.upsert_games_transactional`
- Added `ui_library_adapter.artwork_copy_skip_reason` / `native_steam_artwork_game_from_library_row` / `apply_locked_artwork` — the previously missing bridge from persisted `ArtworkLock` rows to the `DetectedGame.artwork` shape `copy_all_artwork_to_steam` consumes — and extended Apply Changes to copy artwork in the same pass
- Added `transaction_history.list_artwork_transaction_history`; artwork transactions were invisible on the Backups screen before this (wrong manifest filename/schema)
- Wired per-slot Auto Match / Replace to real provider search, download, and `validate_artwork_file`, locking results through `LibraryStore.set_artwork_lock`
- Verified live against a real Steam profile and real cached artwork: shortcut write, artwork copy under both a native Steam AppID and a computed non-Steam AppID, per-game failure isolation, and Backups visibility

Suite repair and full-suite evidence, 2026-08-12:

- Ran every `tests/*_test.py` on Windows / Python 3.11 and found `prototype_library_test.py` and `prototype_shell_selection_test.py` failing at import: the modern shell rewrite removed `MockGame`, `initial_selection_state`, `load_library_games`, and the prototype-local `format_size` those suites imported. The `ui-prototype` CI job asserted the same removed `load_library_games` symbol, so that job was red on `main` too.
- Retargeted `prototype_library_test.py` at `modern_library_view.load_modern_library_rows` / `format_size`, which is where that mapping behavior now lives; assertions are unchanged in substance
- Added Tk-free `modern_library_view.initial_active_item_id`, used it in `ModernShell._auto_select_first`, and retargeted `prototype_shell_selection_test.py` at it through a real `LibraryController`
- Corrected the `ui-prototype` import assertion in `.github/workflows/ci.yml`
- Re-ran the whole suite: every `tests/*_test.py` passes, plus `python -m compileall -q steam_shortcut_studio tests main.py` and the CI import check

Bulk artwork review queue, 2026-08-12:

- Added `steam_shortcut_studio/artwork_bulk_search.py` — one real provider searcher for bulk work, with the placeholder confidence constants named and documented in one place — and replaced legacy `ui.py`'s inline closure with it so there is a single implementation rather than one per UI
- Added `ArtworkReviewQueue`, `ArtworkQueueUpdate`, `artwork_job_status_text`, and `artwork_queue_progress_text` to `artwork_review_workspace.py`; the queue folds job events Tk-free and holds only `NEEDS_REVIEW` results
- Wired `ModernShell._start_bulk_auto_art` / `_submit_artwork_jobs` to `BulkArtworkCoordinator` and replaced the explanatory stub on the top-bar `Auto-Art` tile and the bulk bar's `Find Art` button
- Built the review queue section on the Artwork screen: per-item cards, per-slot candidate rows with real decoded thumbnails (monogram fallback when a file will not decode, never another game's art), a details dialog, and accept/reject/skip/retry plus batch actions
- Added `tests/artwork_bulk_search_test.py` (7 assertions incl. a regression guard that the placeholder scores can never clear `ArtworkMatchPolicy`'s auto thresholds) and 10 new cases in `tests/artwork_review_workspace_test.py`, covering the coordinator → queue → accept/reject chain against a real `LibraryStore`
- Added the new suite to `.github/workflows/ci.yml`
- Ran every `tests/*_test.py` on Windows / Python 3.11: all pass. Also constructed a real `ModernShell` against a temporary library and rendered all ten screens, including the review queue with one decodable and one missing candidate file, without error

Shipping the modern shell, 2026-08-12:

- Found that packaged releases shipped the **legacy** UI: `build-release.yml` builds `main.py` → `steam_shortcut_studio.app` → `.ui.main`, and `requirements.txt` did not even list `customtkinter`, so the modern shell could not have been packaged at all. Every modern-shell feature reached zero released users.
- Also found `run.ps1` launched the legacy UI while `run.bat` launched the modern shell — the two dev launchers disagreed about what the app is.
- Moved `prototypes/modern_shell.py` to `steam_shortcut_studio/modern_shell.py` and converted it to relative imports; `prototypes/modern_library.py` remains as the dev launcher
- Rewrote `main.py` as a real entry point: modern shell by default, `--classic` for the legacy window, `--database` / `--include-missing` pass-through, and an `ImportError` fallback to the classic window so a packaging mistake degrades the interface instead of leaving no app. Unexpected errors still propagate rather than being masked by the fallback.
- Added `customtkinter` to `requirements.txt`, `SteamShortcutStudio.spec` (`collect_all`, needed for its theme JSON), and the Linux `--collect-all` list
- Pointed `run.bat` and `run.ps1` at `main.py` so developers run exactly what users run
- Added `tests/entry_point_test.py` (5 cases: default routing, `--classic`, argument pass-through, the degrade-to-classic path, and a guard that a real failure is not silently swallowed) and wired it into CI
- Artwork tab now renders the real locked image with its provider, and distinguishes "✓ Locked" from "⚠ Locked, file missing" instead of showing a confident check for an unusable lock
- Added a footer Cancel control that cancels this shell's in-flight jobs cooperatively
- Re-ran every `tests/*_test.py`: all pass. Re-ran the shell smoke render with a real locked PNG plus a lock pointing at a deleted file; all ten screens render.
- **Not verified here:** no PyInstaller build was run (PyInstaller is not installed in this environment), so the packaging changes are correct by inspection but unproven. Build both targets before tagging a release.

Real artwork confidence scoring, 2026-08-12:

- Added `steam_shortcut_studio/artwork_scoring.py`: a pure, network-free, Tk-free scorer. Identity is decided by *how the match was established* — an AppID the library row owns is certain (100), a provider ID resolved from that AppID is near-certain (97), a name match is a provider-trust ceiling scaled by `scanner.similarity`, and an unverifiable match is capped at 80, below the policy's 92 threshold, on purpose.
- Identity for a set is the **minimum** across slots, not the mean: four certain slots must not carry one wrong image into an automatic apply.
- Added `stamp_match_provenance` to `artwork_search_service.py` and applied it at all six collection sites (official Steam, Steam Store, Wikimedia, RAWG, and both SteamGridDB paths). The service already refused weak title matches internally but only logged that reasoning; it is now data. Written into a copy of the payload so cached responses are not mutated.
- Populated `ArtworkEvidence.conflicting_edition` / `conflicting_year`, which nothing had ever set. Both are deliberately suppressed for identifier-resolved matches: `ArtworkMatchPolicy` checks conflict flags *before* any score, so raising them would have sent AppID-certain matches to review over edition wording.
- Set coherence penalises wrong-shape images per slot and provider spread — but only across *name-resolved* assets. Penalising Steam capsules plus a SteamGridDB icon that both answer one AppID put the most common good result one point from failing for no real reason.
- Removed the placeholder constants from `artwork_bulk_search.py` and gave `validated_artwork_assets_to_search_outcome` an optional `scorer` that runs against the assets actually selected (the only point where the winning candidate per slot is known). Selected assets carry the decoded file's real dimensions, so shape is judged on what was downloaded, not what the provider advertised.
- The review queue now shows the measured confidence and its top reason, which was previously forbidden because the number was a constant.
- Added `tests/artwork_scoring_test.py` (22 cases: provenance reading, identity per method, provider ceilings, conflict detection and its suppression, coherence penalties, weakest-link identity, range safety against hostile input, and end-to-end policy outcomes) and wired it into CI. Updated the bulk-search tests to assert real scores.
- Verified the resulting decisions across ten realistic scenarios: native Steam by AppID → auto-accept; SteamGridDB exact title → auto-accept; unverifiable, RAWG, Wikimedia, edition mismatch, mixed name-resolved sources, and incomplete sets → review; wrong game → reject.
- Every `tests/*_test.py` passes; the shell smoke render passes.

Editing, empty states, and clean shutdown, 2026-08-12:

- Added `steam_shortcut_studio/library_edits.py`. `LibraryStore.save_overrides` replaces every column, so a caller that supplies only the edited field silently erases the rest — every save now carries the complete set. An edit that matches the launcher's own value stores *no* override, so a value is never pinned and a later launcher rename still shows through.
- Added an editable Details tab to the modern shell (title, launch target, arguments, working directory, notes) with a reset-to-source action. The shell previously displayed these read-only, so renaming a game meant dropping into the classic UI.
- Added empty-state guidance to the Library screen, distinguishing "your library is empty" (offering Steam / Epic / folder scans, and saying plainly that scanning only reads) from "a filter hides everything" (offering to clear it). A first-run user previously saw a blank table with no explanation.
- Fixed a shutdown bug found while testing: the shell rescheduled its `after` poll forever and never closed `LibraryController`, so closing the window left the repeating callback firing against a torn-down widget tree and the job queue's workers alive. `WM_DELETE_WINDOW` now cancels the poll and closes the controller.
- Added `tests/library_edits_test.py` (9 cases including a real `LibraryStore` round trip proving an unrelated note survives a title-only save, and that reverting a title removes rather than pins the override) and wired it into CI.
- Verified interactively against a temporary library: empty-library screen, filtered-empty screen, Details tab, a save that created exactly the two intended overrides while correctly declining to override the two fields matching source, and a reset that cleared them all.

Real last-played data, 2026-08-12:

- Added `steam_shortcut_studio/steam_playtime.py`, reading `UserLocalConfigStore/Software/Valve/Steam/apps/<appid>/LastPlayed` from every user's `localconfig.vdf` through the existing `vdf.load_text_vdf` parser rather than a new one. Read-only; a missing, unreadable, or foreign file yields no data instead of an error, so the library still renders when Steam has never run. Multiple accounts merge to the most recent play.
- The modern shell's `LAST PLAYED` column previously showed a hardcoded em dash for every row. It now shows Steam's own record in human units and is sortable, with never-played rows grouped at one end rather than scattered by title. The map is parsed once per Steam path and re-read on Refresh Metadata.
- Nothing is invented for Epic or folder games: they have no equivalent record and keep an em dash. A blank cell is honest; a fabricated date is not.
- Added `tests/steam_playtime_test.py` (9 cases: the documented VDF path, never-played and malformed entries, Steam casing changes, unreadable/foreign files, multi-user merge, missing Steam path, recency wording, and a future timestamp not rendering as negative days) and wired it into CI.
- Verified against the real Steam install on the development machine: 166 AppIDs with genuine records, formatting spanning "4 weeks ago" to "5 years ago".

## Known Risks

- `ui.py` still contains too many responsibilities (5,600+ lines)
- Current provider download, auto-selection, and review presentation still run through the legacy UI path
- Confidence scoring (`artwork_scoring.py`) is real but young. Its provider ceilings and penalties are reasoned rather than measured against a labelled corpus; watch for auto-accepts that should not have been, and prefer tightening a ceiling over loosening the policy.
- Scoring depends on provenance stamped by `artwork_search_service`. An asset that reaches the scorer without a `sss_match` stamp scores as unverifiable (capped below auto-accept) — safe, but it silently costs auto-accepts. Any new provider path must stamp its assets.
- The modern shell must not become a second implementation of domain logic; `ModernShell._visible_rows` already duplicates search/filter/sort logic that `modern_library_view.py` owns
- The Backups screen caps rendering at the 50 most recent transactions; older restore points exist on disk but are not listed
- Two prototype suites silently broke when the modern shell was rewritten and were only caught by running the suite by hand — the `ui-prototype` CI job was red on `main` from `53c398b` until `2026-08-12`
- Native Steam setting ownership varies by platform and may be overwritten by Steam
- The custom VDF parser needs broader fixtures before supporting unknown future field types
- New launcher database adapters must avoid locking or modifying live launcher data

## Exact Next Action

**Already done — do not rebuild:** the modern shell's Apply Changes performs
real, verified `shortcuts.vdf` writes *and* real locked-artwork copies into
Steam's grid folder, both through the unmodified
`shortcut_transactions.upsert_games_transactional` /
`artwork.copy_all_artwork_to_steam` services, in one background job inside one
Steam-closed window. Per-slot Auto Match / Replace / Clear are live. Artwork
transactions are visible on the Backups screen via
`transaction_history.list_artwork_transaction_history`.

**Also done:** the bulk artwork review queue. `Auto-Art` and bulk `Find Art`
submit through `BulkArtworkCoordinator`; `ArtworkReviewQueue` holds the
`NEEDS_REVIEW` results; the Artwork screen renders them with per-slot previews
and accept/reject/skip/retry. Both UIs share
`artwork_bulk_search.build_provider_searcher`.

**Also done:** real confidence scoring (`artwork_scoring.py`). Identity comes
from how the match was established — an AppID the library row owns is certain,
a name match is capped by provider trust and scaled by title similarity, and an
unverifiable match is capped below auto-accept on purpose. Strong complete
matches auto-accept; everything else still routes to the review queue.

**Next:** validate the scoring against reality, then breadth.

1. Run bulk Auto-Art across a real library and check the auto-accepted matches
   are genuinely right. The thresholds in `artwork_scoring.py` are reasoned, not
   measured — this is the step that turns them from plausible into trusted.
2. Add the remaining Windows launcher adapters: GOG Galaxy, Playnite, EA app,
   Ubisoft Connect, Battle.net. All read-only, all through `SourceAdapter`,
   each independently shippable. Playnite first if you want leverage, since it
   already aggregates other launchers.
3. Then reduce `ui.py` as the modern shell covers more of its workflows.

Constraints that still hold:

1. Never present a number as confidence unless it is measured.
2. Any new provider path must stamp match provenance, or its assets silently
   score as unverifiable.
3. Keep the review queue as the destination for anything below threshold.
4. Never bypass `shortcut_transactions.py` / `artwork_transactions.py` for writes.
5. New launcher adapters must not lock or modify live launcher data.

## Next Codex Prompt

```text
Read CODEX_START_HERE.md and all linked docs. Already live, do not rebuild: the modern shell is the shipped default interface (steam_shortcut_studio/modern_shell.py, launched by main.py, --classic for the legacy window); transactional shortcut writes AND artwork copies in Apply Changes; per-slot Auto Match/Replace/Clear; the bulk artwork review queue (Auto-Art -> BulkArtworkCoordinator -> ArtworkReviewQueue -> the Artwork screen); and real confidence scoring in artwork_scoring.py fed by match provenance stamped in artwork_search_service.py. The next slice is breadth: add read-only source adapters for GOG Galaxy, Playnite, EA app, Ubisoft Connect, and Battle.net, one per PR, each through the shared SourceAdapter model, following sources/epic.py as the reference. Never lock or modify live launcher data; a partial or unavailable scan must never mark stored games missing; malformed manifests must be isolated and reported, not fatal. If an adapter can supply a Steam AppID or a canonical title, stamp it so artwork scoring can use it. Use stable IDs. Add tests without constructing a Tk window. Run every tests/*_test.py suite and update SPRINT_STATUS with exact evidence. Small reviewable commits.
```
