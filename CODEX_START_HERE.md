# Codex Start Here

Read this file before changing Steam Shortcut Studio.

## Current Reality

The project is past the initial safety and foundation stages.

Already implemented and merged:

- Transactional production `shortcuts.vdf` writes
- Malformed-file blocking instead of silent replacement
- Read-back verification and automatic rollback
- Atomic production artwork-set writes
- Image decoding, size limits, hashing, and perceptual duplicate support
- Transaction and restore-point history
- Stable selection state
- Bounded background job queue
- Selected-game artwork coordinator and match policy
- Persistent SQLite library state
- Conservative source-scan persistence
- Tk-free immutable `LibraryController`
- Read-only Epic Games Launcher manifest adapter
- Read-only native Steam library adapter
- Read-only loose/local folder adapter
- Epic, Steam, and folder scan CLIs
- Approved modern UI prototype using real stored library data

Do not recreate these systems or route around them.

## Read in This Order

1. `docs/SPRINT_STATUS.md`
2. `docs/PRODUCT_ROADMAP.md`
3. `docs/UI_UX_TARGET.md`
4. `docs/SPRINT_MAP.md`
5. `docs/CURRENT_ARCHITECTURE.md`
6. `docs/WRITE_PATH_AUDIT.md`
7. `docs/TRANSACTION_SERVICE_SPEC.md`
8. `docs/ARTWORK_MATCH_POLICY.md`
9. `docs/NATIVE_STEAM_FIELD_MATRIX.md`
10. `docs/LAUNCHER_IMPORT_RESEARCH.md`
11. `docs/CLI.md`
12. `docs/UI_FRAMEWORK_DECISION.md`
13. `docs/DEVELOPMENT_SETUP.md`

Then inspect the current repository. Documentation describes intent; code and tests describe the actual current state.

## Active Engineering Goal

Work on **incremental production modern-library integration** under issues #4, #5, and #7.

The immediate milestone is to connect the existing `LibraryController` to the production UI without replacing the whole application at once:

- Add a controller-backed library view adapter for the legacy UI.
- Render immutable `LibraryRow` data using stable IDs.
- Use `SelectionState` for active and bulk selection.
- Poll `BackgroundJobQueue` events from the Tk thread.
- Expose Epic, Steam, and folder scan actions through the controller.
- Keep all current legacy capabilities available during migration.
- Add no new Steam writes.

After that boundary is proven, migrate the modern table and then connect real artwork providers to `BulkArtworkCoordinator`.

## Required Safety Rules

- Do not modify game installation files.
- Do not add direct Steam writes.
- Do not bypass `shortcut_transactions.py` or `artwork_transactions.py`.
- Do not reintroduce malformed-VDF replacement behavior.
- Do not swallow artwork transaction failures and continue with a partial game set.
- Do not let worker threads touch UI widgets.
- Do not let partial or unavailable source scans mark stored games missing.
- Do not discard manual overrides, artwork locks, or rejected matches during rescans.
- Do not enable prototype Apply actions merely because the interface exists.
- Keep risky native Steam fields read-only until their ownership and rollback behavior are proven.

## Existing Building Blocks

Use these instead of creating duplicates:

```text
steam_shortcut_studio/selection.py
steam_shortcut_studio/jobs.py
steam_shortcut_studio/job_queue.py
steam_shortcut_studio/library_controller.py
steam_shortcut_studio/library_store.py
steam_shortcut_studio/source_scans.py
steam_shortcut_studio/sources/base.py
steam_shortcut_studio/sources/epic.py
steam_shortcut_studio/sources/steam.py
steam_shortcut_studio/sources/local.py
steam_shortcut_studio/cli.py
steam_shortcut_studio/source_cli.py
steam_shortcut_studio/artwork_policy.py
steam_shortcut_studio/bulk_artwork.py
steam_shortcut_studio/image_validation.py
steam_shortcut_studio/transactions.py
steam_shortcut_studio/file_transactions.py
steam_shortcut_studio/shortcut_transactions.py
steam_shortcut_studio/artwork_transactions.py
steam_shortcut_studio/transaction_history.py
```

Modern UI references:

```text
prototypes/modern_shell.py
prototypes/modern_library.py
docs/UI_UX_TARGET.md
```

## Current Usable Read-Only Workflows

```text
python -m steam_shortcut_studio.cli scan-epic
python -m steam_shortcut_studio.source_cli scan-steam --steam-root "C:\Program Files (x86)\Steam"
python -m steam_shortcut_studio.source_cli scan-folder --root "D:\PC Games"
python -m steam_shortcut_studio.cli list-library
python -m pip install -r requirements-ui-prototype.txt
python prototypes/modern_library.py
```

These scan commands write only the app-owned SQLite database. The prototype reads that database and does not write Steam.

## Validation Expectations

At minimum, run every suite touched by the change. Before completing a major integration PR, run the complete matrix represented in `.github/workflows/ci.yml` and `.github/workflows/source-cli.yml`.

Core commands include:

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
python tests/cli_test.py
python tests/source_cli_test.py
python tests/image_validation_test.py
python tests/artwork_transaction_test.py
python tests/artwork_live_transaction_test.py
```

Never mark work complete because code was written. Record commands and passing results in `docs/SPRINT_STATUS.md`.

## Work Separation

### Chat / Research

- UX decisions and mockups
- Launcher ownership/schema research
- Native Steam field research
- Acceptance criteria
- Threat/failure analysis
- Review of Codex diffs and CI evidence
- Documentation and sprint decomposition

### Codex Required

- Incremental `ui.py` refactoring
- Production controller/view integration
- Provider extraction and integration
- Production modern table and review workspace
- Additional launcher database adapters
- Running tests and failure injection
- Packaging and platform validation

### Mixed

Chat defines behavior, risks, wording, and acceptance criteria. Codex implements and validates. Most remaining major work is mixed.

## Required Session Output

At the end of a coding session, update `docs/SPRINT_STATUS.md` with:

- Scope completed
- Files changed
- Commands run
- Test and CI results
- Known limitations
- New risks or blockers
- Exact next action

Keep commits small, reviewable, and reversible.
