# Steam Shortcut Studio Product Roadmap

## Product Direction

Steam Shortcut Studio is a personal-library manager for Steam and non-Steam games. It should make large libraries easier to import, identify, repair, customize, and maintain without becoming a replacement game launcher.

The product should treat these as first-class library items:

- Native Steam games
- Existing non-Steam shortcuts
- Loose or portable game folders
- Windows launcher libraries
- SteamOS/Bazzite launcher libraries in a later phase

The app should prioritize safety, reversible changes, clear previews, and useful bulk actions.

## North Star

A user should be able to scan a personal game library, select many games, find matching metadata and artwork, review only uncertain results, and safely apply the approved changes to Steam.

The core experience should be:

1. Detect Steam and configured library sources.
2. Scan or import games.
3. Identify games and launch targets with visible confidence.
4. Select one or many games.
5. Find metadata and complete artwork sets in bulk.
6. Automatically accept only high-confidence, low-risk results.
7. Route uncertain results into a review queue.
8. Preview all Steam changes.
9. Create a backup.
10. Apply, verify, and retain a rollback point.

## Non-Negotiable Safety Rules

1. Never modify installed game files.
2. Never silently overwrite manual artwork choices.
3. Never write launch, compatibility, or native Steam settings without a preview.
4. Back up every Steam-owned file before changing it.
5. Write through a transaction service rather than directly from UI code.
6. Read back and validate every changed file after writing.
7. Roll back automatically when validation fails.
8. Preserve unknown fields and unsupported data.
9. Keep advanced or experimental native-Steam edits behind explicit warnings.
10. Record why every automatic decision was considered safe.

## Target User Experience

The approved UI direction is a polished dark desktop application with:

- A left navigation sidebar
- A compact top command bar
- A central searchable and sortable game table
- Multi-selection and contextual bulk actions
- A right-side inspector for artwork, metadata, launch settings, safety, and history
- A visible theme selector with multiple accent colors
- Clear states for safe automation, review required, protected native Steam data, failure, and rollback

See [UI_UX_TARGET.md](UI_UX_TARGET.md) for the full design specification.

## Highest-Priority Feature: Bulk Artwork Search

Bulk artwork search must be a first-class workflow.

A user must be able to:

- Select multiple games in the library table
- Choose `Find Artwork for Selected`
- Choose whether to fill missing slots only or reconsider all unlocked slots
- Process the selection through a background job queue
- See progress per game and for the whole batch
- Automatically accept only high-confidence matches
- Review incomplete, conflicting, or weak matches
- Cancel the remaining queue
- Retry failed jobs
- Preserve manually locked artwork

Every selected game should finish in one of these states:

- Artwork ready
- Applied automatically
- Needs review
- No acceptable match
- Skipped
- Failed
- Cancelled

## Product Scope

### In Scope

- Scanning native Steam games, existing shortcuts, folders, and supported launcher manifests
- Launch-target detection and manual override
- Native and non-Steam artwork management
- Metadata, notes, tags, and safe user-controlled settings
- Bulk selection and batch actions
- Backup, preview, verification, history, and rollback
- Windows-first launcher integration
- SteamOS/Bazzite support after the Windows workflow is stable
- Theme and accent-color customization

### Out of Scope for the Near Term

- Replacing Steam as the primary launcher
- Social features
- Store purchasing
- Cloud game streaming
- Editing installed game binaries or application content
- ROM and emulator management until PC-game workflows are mature
- Automatic modification of poorly understood Steam fields

## Roadmap Phases

## Phase 0 — Safety Foundation

### Goal

Make every Steam write transactional, verifiable, and reversible before expanding editing capabilities.

### Deliverables

- Transaction service
- Backup manifest
- Atomic or staged writes
- Read-back validation
- Automatic rollback on failure
- Restore-point history
- Write simulation/dry run
- Structured change plan
- Safety test fixtures

### Exit Criteria

- A failed write cannot leave the tested Steam fixtures corrupted.
- A successful write can be validated and restored.
- UI code cannot directly write Steam files.

## Phase 1 — Architecture and Modern UI Foundation

### Goal

Split the current large UI module into maintainable views, components, controllers, and services while creating the approved modern shell.

### Deliverables

- UI package structure
- Theme token system
- Reusable buttons, cards, tabs, badges, and panels
- Left sidebar
- Top command bar
- Library workspace shell
- Right inspector shell
- Responsive resizing rules

### Exit Criteria

- Existing workflows remain usable.
- The main window follows the approved information architecture.
- Theme colors are data-driven rather than hardcoded per widget.

## Phase 2 — Library Table and Selection Model

### Goal

Create a scalable central library view that supports efficient single-game and multi-game work.

### Deliverables

- Searchable and sortable game table
- Row checkboxes
- Shift-range selection
- Additive selection
- Select-all-in-filter
- Selection summary
- Saved selection state during safe refreshes
- Contextual bulk-action bar
- Filters for source, status, artwork, native Steam, and review state

### Exit Criteria

- Hundreds of entries remain usable and responsive.
- Multiple games can be selected reliably.
- Bulk actions operate only on the intended selection.

## Phase 3 — Background Jobs and Bulk Workflows

### Goal

Add a reusable queue for scan, metadata, artwork, and validation tasks.

### Deliverables

- Job model and queue service
- Worker limits
- Cancellation
- Retry
- Per-job and aggregate progress
- Structured failures
- Persistent or recoverable batch summary
- Bulk scan selected
- Bulk refresh metadata selected
- Bulk preview selected

### Exit Criteria

- The UI remains responsive during a large batch.
- Cancelling a batch does not corrupt partial results.
- Failures are isolated to individual items.

## Phase 4 — Bulk Artwork Search and Review

### Goal

Deliver the primary batch-artwork workflow.

### Deliverables

- `Find Artwork for Selected`
- Artwork-slot policy controls
- Provider prioritization
- Match scoring and evidence
- Complete-set coherence checks
- Image validation and dimension checks
- Manual-art locks
- Review queue
- Batch result summary
- Missing-only and replace-unlocked modes

### Exit Criteria

- At least 20 selected games can be processed in one batch.
- High-confidence matches can be accepted automatically under configured rules.
- Weak or conflicting matches never apply silently.
- Manual artwork remains untouched unless explicitly unlocked.

## Phase 5 — Artwork Workspace

### Goal

Create a polished, slot-based editor for individual and batch results.

### Deliverables

- Portrait/grid slot
- Wide capsule slot
- Hero slot
- Logo slot
- Icon slot
- Candidate browser
- Source filters
- Before/after comparison
- Local file and clipboard import
- Slot lock/unlock
- Crop/fit controls where safe
- Per-slot confidence and source evidence

### Exit Criteria

- Every Steam artwork slot can be inspected and intentionally changed.
- The user can understand where each selected asset came from.
- A complete set looks coherent rather than assembled from unrelated games or editions.

## Phase 6 — Native Steam Controls

### Goal

Allow practical customization of native Steam games without endangering the library.

### Initial Safe Scope

- Custom artwork
- Personal notes stored by Steam Shortcut Studio
- App-managed tags and labels where supported
- Explicitly supported launch options
- Compatibility-tool choices where the storage format is understood and tested
- Restore to original values

### Required Research Gate

Before implementing a native Steam field, document:

- Which Steam file owns the value
- Whether Steam may overwrite it
- Whether Steam must be closed
- How unknown fields are preserved
- How the value is validated
- How rollback works
- Windows and Linux behavior

### Exit Criteria

- Native-game changes are opt-in, previewed, and reversible.
- Unsupported fields remain read-only.
- No game files are modified.

## Phase 7 — Windows Launcher Imports

### Goal

Prefer authoritative launcher manifests over folder-name guessing.

### Priority Order

1. Epic Games Store
2. GOG/GOG Galaxy
3. Playnite
4. EA App
5. Ubisoft Connect
6. Battle.net
7. Microsoft Store/Xbox where feasible and safe

### Deliverables

- `SourceAdapter` interface
- External identity storage
- Install-path and launch-command extraction
- Duplicate reconciliation
- Adapter diagnostics
- Folder-scanning fallback

### Exit Criteria

- Supported manifests produce more reliable identities than folder scanning.
- Duplicate copies and existing Steam shortcuts can be reconciled rather than blindly added.

## Phase 8 — SteamOS and Bazzite Sources

### Goal

Extend the stable source-adapter model to Linux gaming tools.

### Priority Order

1. Heroic
2. Lutris
3. Legendary
4. Bottles
5. Flatpak-aware paths

### Exit Criteria

- Windows behavior is not regressed.
- Platform-specific commands and compatibility settings are represented explicitly.
- Linux tests cover common SteamOS/Bazzite paths.

## Phase 9 — Quality, Packaging, and Release

### Goal

Make the app dependable for regular personal use.

### Deliverables

- Split test suite
- Fixture-driven VDF and config tests
- Failure-injection tests
- Performance checks
- Diagnostics export
- Installer or portable build
- Upgrade-safe settings migration
- User documentation
- Release checklist

### Exit Criteria

- The main workflows pass on supported Windows environments.
- Linux smoke tests pass where supported.
- A user can install, configure, back up, restore, and troubleshoot without reading source code.

## Core Data Model Direction

A unified library item should retain both normalized data and source evidence.

```text
LibraryItem
- internal_id
- title
- normalized_title
- source_type
- source_external_id
- source_record
- install_path
- launch_target
- launch_arguments
- working_directory
- platform
- native_steam_app_id
- existing_shortcut_id
- release_year
- developer
- publisher
- artwork_slots
- manual_locks
- confidence
- evidence
- proposed_changes
- original_values
```

Suggested source types:

```text
native_steam
existing_shortcut
folder_scan
epic
gog
playnite
ea
ubisoft
battlenet
microsoft_store
heroic
lutris
legendary
bottles
```

## Automation Policy

### May Auto-Apply

Only when all configured safety rules pass, such as:

- Identity is based on an exact external/store identifier or equivalent authoritative evidence.
- Artwork belongs to the same game and edition.
- Image files decode successfully and meet slot requirements.
- No manual artwork lock is present.
- The operation does not modify launch behavior or advanced native Steam settings.
- A backup and rollback path exist.

### Must Require Review

- Ambiguous title matches
- Conflicting editions or release years
- Multiple plausible launch targets
- Incomplete artwork sets when replacement policy expects a full set
- Existing manual artwork
- Native Steam launch or compatibility changes
- Unknown or unsupported Steam fields
- Provider failures that reduce confidence

## Success Metrics

- Percentage of scanned games correctly identified without correction
- Percentage of artwork batches completed without manual intervention
- False-positive automatic artwork rate
- Number of manual artwork choices later overwritten: target zero
- Write-verification success rate
- Rollback success rate
- Median time to process 20 selected games
- Number of direct Steam-write paths outside the transaction service: target zero

## Planning Documents

- [UI/UX Target](UI_UX_TARGET.md)
- [Sprint Map](SPRINT_MAP.md)
- [Sprint Status](SPRINT_STATUS.md)
