# Steam Shortcut Studio Sprint Map

## Purpose

This file is the execution map for future development. It separates work that can be prepared in ChatGPT from work that requires Codex or another repository-capable coding environment.

The map is intentionally incremental. Do not jump directly to native Steam setting edits or launcher expansion before the transaction and test foundations are complete.

## Work Modes

### `CHAT`

Best for work that does not require running or changing the local application:

- Product decisions
- Research
- UX interviews
- UI mockups
- Architecture options
- Threat and failure analysis
- Acceptance criteria
- Test-case design
- Documentation
- Issue and sprint decomposition
- Reviewing Codex results and diffs
- Preparing compact Codex prompts

Chat work may update planning documents through the GitHub connector, but it should not claim that runtime behavior has been verified.

### `CODEX`

Required when the task needs repository access, code changes, execution, or validation:

- Refactoring Python modules
- Implementing UI components
- Editing VDF or Steam configuration handling
- Running tests
- Creating fixtures from sanitized files
- Exercising failure cases
- Measuring performance
- Building installers
- Debugging platform-specific behavior
- Committing implementation changes

### `MIXED`

Chat prepares decisions, specifications, risk controls, and acceptance tests. Codex implements and verifies them. Most important sprints use this mode.

## Sprint Rules

1. Read [PRODUCT_ROADMAP.md](PRODUCT_ROADMAP.md), [UI_UX_TARGET.md](UI_UX_TARGET.md), and [SPRINT_STATUS.md](SPRINT_STATUS.md) before beginning.
2. Work only on the active sprint unless a prerequisite defect blocks it.
3. Keep changes small enough to review and revert.
4. Do not combine a UI-framework migration with Steam-write changes.
5. Add or update tests with every behavior change.
6. Record completed tasks and evidence in `SPRINT_STATUS.md`.
7. Do not mark a sprint complete because code was written. Mark it complete only when acceptance criteria pass.
8. Stop and document uncertainty when a Steam-owned file format or field is not understood.
9. Preserve existing capabilities unless the sprint explicitly replaces them.
10. Prefer adapters and services over additional logic in the main UI module.

## Standard Sprint Output

Every sprint should produce:

- Scope summary
- Files changed
- Tests added or updated
- Commands run
- Results
- Known limitations
- Follow-up work
- Updated `SPRINT_STATUS.md`

---

# Track A — Chat-First Planning and Research

These tasks can be advanced without waiting for Codex, although implementation still belongs in the engineering sprints.

## CHAT-A1 — Native Steam Field Research

**Mode:** CHAT

### Objective

Create a field-by-field safety matrix before allowing edits to native Steam game settings.

### Research Questions

- Which file owns each field?
- Is the field global, per-user, or per-machine?
- Can Steam overwrite it?
- Must Steam be closed?
- Does the format vary by operating system?
- What constitutes a valid value?
- How can unknown data be preserved?
- How can a change be rolled back?

### Candidate Fields

- Artwork
- Launch options
- Compatibility tool
- Hidden state
- Favorite state
- Collections/tags
- Per-game notes
- Custom title/display behavior

### Deliverable

`docs/NATIVE_STEAM_FIELD_MATRIX.md`

### Stop Condition

Any field without reliable ownership, validation, and rollback information remains read-only.

## CHAT-A2 — UI Component Specification

**Mode:** CHAT

### Objective

Turn the approved mockup direction into implementation-ready component behavior.

### Tasks

- Define every screen and component state.
- Define keyboard interactions.
- Define empty, loading, error, and disabled states.
- Define narrow-window behavior.
- Define copy for safety warnings and review reasons.
- Define bulk artwork dialog behavior.

### Deliverable

Updates to `UI_UX_TARGET.md` or focused component specifications.

## CHAT-A3 — Artwork Confidence Policy

**Mode:** CHAT

### Objective

Define the exact policy for automatic artwork selection.

### Tasks

- Identity evidence weights
- Edition conflict rules
- Complete-set coherence rules
- Resolution and aspect-ratio requirements
- Provider priority
- Manual lock behavior
- Confidence thresholds
- Review reasons

### Deliverable

`docs/ARTWORK_MATCH_POLICY.md`

## CHAT-A4 — Launcher Adapter Research

**Mode:** CHAT

### Objective

Document reliable manifest locations and identity fields before adapters are implemented.

### Priority

1. Epic
2. GOG
3. Playnite
4. EA App
5. Ubisoft Connect
6. Battle.net
7. Microsoft Store/Xbox feasibility
8. Heroic
9. Lutris
10. Legendary
11. Bottles

### Deliverable

`docs/SOURCE_ADAPTER_MATRIX.md`

## CHAT-A5 — Test and Failure Matrix

**Mode:** CHAT

### Objective

Create reusable test scenarios for safety-critical and batch behavior.

### Coverage

- Missing Steam files
- Malformed VDF
- Interrupted write
- Permission failure
- Steam running
- Backup failure
- Read-back mismatch
- Duplicate shortcuts
- Cancelled bulk job
- Provider timeout
- Invalid image
- Wrong-game artwork
- Manual artwork lock
- Partial batch failure

### Deliverable

`docs/TEST_MATRIX.md`

---

# Track B — Codex Implementation Sprints

## Sprint 00 — Baseline and Repository Audit

**Mode:** MIXED

### Objective

Establish a trustworthy baseline and identify exact change boundaries before refactoring.

### Chat Work

- Review current architecture and known risks.
- Confirm product scope and non-goals.
- Prepare the audit checklist.
- Review Codex findings and resolve ambiguous priorities.

### Codex Work

- Run the existing test suite.
- Record supported Python and platform assumptions.
- Inventory modules and responsibilities.
- Map every code path that writes Steam-owned files.
- Map artwork cache and provider flows.
- Measure `ui.py` responsibilities and dependency directions.
- Record current startup, scan, artwork, preview, and write workflows.
- Create a sanitized fixture strategy.

### Deliverables

- `docs/CURRENT_ARCHITECTURE.md`
- `docs/WRITE_PATH_AUDIT.md`
- Updated `SPRINT_STATUS.md`
- Baseline test result

### Acceptance Criteria

- Existing tests have a recorded pass/fail baseline.
- Every known Steam-write entry point is listed.
- No implementation refactor has started without a dependency map.

### Stop Conditions

- Repository cannot run in the available environment.
- Test failures are unexplained.
- Steam write paths cannot be identified confidently.

---

## Sprint 01 — Transactional Steam Write Service

**Mode:** MIXED

### Objective

Create one controlled path for Steam-owned file changes.

### Chat Work

- Define transaction states and user-facing failure messages.
- Define backup manifest fields.
- Define rollback acceptance tests.
- Review the planned API and failure model.

### Codex Work

- Create a transaction/change-plan model.
- Extract Steam writing from UI callbacks.
- Stage writes in temporary files or directories.
- Create backups before mutation.
- Validate staged output.
- Replace destination safely where supported.
- Read back and validate final output.
- Roll back automatically on failure.
- Add structured logs and transaction identifiers.
- Ensure unknown VDF fields are preserved.

### Deliverables

- Transaction service
- Backup manifest format
- Validation result model
- Rollback service
- Failure-injection tests

### Acceptance Criteria

- UI code does not directly write `shortcuts.vdf` or grid artwork.
- A simulated failure after backup restores the original fixture.
- A read-back mismatch triggers rollback.
- A successful transaction produces a usable restore point.
- Repeated application is idempotent where expected.

### Stop Conditions

- Parser round-trip loses unknown data.
- Backups cannot be verified.
- Rollback is not dependable in fixtures.

---

## Sprint 02 — Test Suite Split and Safety Fixtures

**Mode:** CODEX

### Objective

Replace dependence on one broad smoke test with focused, maintainable tests.

### Codex Work

- Split tests by domain.
- Add sanitized VDF fixtures.
- Add valid, malformed, truncated, and unknown-field fixtures.
- Add artwork filename and path fixtures.
- Add transaction and rollback tests.
- Add platform-path tests.
- Add image validation tests.
- Add test helpers for temporary Steam directories.

### Suggested Layout

```text
tests/
  unit/
  integration/
  fixtures/
  helpers/
```

### Acceptance Criteria

- Tests can run without a real Steam installation.
- Safety-critical tests are individually identifiable.
- Failures identify the affected service rather than only failing a monolithic smoke run.

---

## Sprint 03 — UI Architecture Extraction

**Mode:** MIXED

### Objective

Break the oversized UI module into stable boundaries without changing the visible product substantially.

### Chat Work

- Review proposed component boundaries.
- Decide naming and navigation model.
- Confirm no feature is accidentally dropped.

### Codex Work

- Introduce `ui/components`, `ui/views`, and controller/service boundaries.
- Extract theme tokens.
- Extract background-job presentation interfaces.
- Move scan, metadata, artwork, and write orchestration out of widget code.
- Keep a compatibility layer as needed during migration.
- Add focused tests for controller behavior.

### Acceptance Criteria

- Main window creation remains understandable.
- Domain services do not import UI modules.
- UI views depend on controller interfaces rather than implementation internals.
- Existing workflows still start and run.

### Stop Conditions

- Refactor begins changing write behavior.
- A framework migration is introduced without a separate decision record.

---

## Sprint 04 — Design System and Modern Application Shell

**Mode:** MIXED

### Objective

Implement the approved visual direction without yet rebuilding every feature panel.

### Chat Work

- Finalize theme presets and semantic tokens.
- Review component states and visual hierarchy.
- Provide additional mockups where a component remains ambiguous.

### Codex Work

- Implement semantic theme tokens.
- Build reusable buttons, cards, tabs, badges, and inputs.
- Build the left sidebar.
- Build the compact top command bar.
- Build the main library/inspector split.
- Add theme accent switching.
- Add resizing and scaling behavior.
- Retain access to existing functionality during migration.

### Acceptance Criteria

- Main layout resembles the approved dark blue mockup direction.
- Accent themes change through tokens.
- Status colors remain semantically consistent.
- App is usable at 100%, 125%, and 150% scaling.
- Existing settings remain loadable or migrate safely.

---

## Sprint 05 — Unified Library Model and Persistence

**Mode:** MIXED

### Objective

Create a stable identity model that supports native Steam, shortcuts, folders, and future launcher adapters.

### Chat Work

- Review data fields and identity evidence.
- Define duplicate-resolution user stories.
- Define migration expectations.

### Codex Work

- Implement `LibraryItem` and source records.
- Introduce stable internal IDs.
- Add SQLite or an equivalent structured persistence layer.
- Persist manual launch choices.
- Persist manual artwork locks and selections.
- Persist rejected matches.
- Persist scan and transaction history references.
- Add migration/version handling.

### Acceptance Criteria

- Rescanning does not discard manual launch or artwork choices.
- Native Steam entries and non-Steam entries are distinguishable.
- Source identity and confidence evidence are retained.
- Persistence migrations are tested.

---

## Sprint 06 — Modern Library Table and Multi-Selection

**Mode:** MIXED

### Objective

Build the central library table and reliable selection behavior.

### Chat Work

- Review column priority and responsive collapse behavior.
- Define selection wording and confirmation rules.
- Review empty and error states.

### Codex Work

- Build searchable/sortable library table.
- Add checkbox selection.
- Add Shift-range selection.
- Add Ctrl additive selection on Windows.
- Add select-all-visible.
- Add select-all-matching-filter.
- Add persistent selection summary.
- Add source, Steam state, artwork, and review filters.
- Add contextual bulk-action bar.
- Ensure the active inspector row is distinct from bulk selection.

### Acceptance Criteria

- Multiple games can be selected and deselected predictably.
- Bulk actions receive exactly the selected IDs.
- Filtering does not silently change the action scope.
- Selection remains responsive with a representative large library.
- Keyboard navigation works for core actions.

---

## Sprint 07 — Background Job Queue

**Mode:** CODEX

### Objective

Create a reusable, cancellable queue for scan, metadata, artwork, and validation tasks.

### Codex Work

- Define job states and result types.
- Add bounded workers.
- Add cancellation tokens.
- Add retry handling.
- Add per-game progress.
- Add aggregate progress.
- Add structured provider and validation errors.
- Add UI-safe event delivery.
- Add job summary persistence or export.

### Acceptance Criteria

- The UI remains responsive during a large mock batch.
- Cancellation prevents new queued jobs from starting.
- A failed job does not fail the whole batch.
- Retry reprocesses only eligible failed jobs.
- Closing the app during work is handled safely.

---

## Sprint 08 — Bulk Scan and Metadata Actions

**Mode:** CODEX

### Objective

Prove the selection and queue architecture before adding artwork complexity.

### Codex Work

- Implement `Scan Selected`.
- Implement `Refresh Metadata for Selected`.
- Add eligibility checks.
- Add progress and result summaries.
- Preserve manual overrides.
- Add preview-only mode where appropriate.

### Acceptance Criteria

- Selected-only scope is respected.
- Manual launch targets remain unchanged unless explicitly reset.
- Batch results are reviewable by game.
- Partial failures are isolated and retryable.

---

## Sprint 09 — Artwork Validation and Match Policy Engine

**Mode:** MIXED

### Objective

Create the evidence and validation layer needed for safe bulk artwork.

### Chat Work

- Complete `ARTWORK_MATCH_POLICY.md`.
- Define automatic-acceptance thresholds.
- Define edition and set-coherence rules.
- Review real examples of false matches.

### Codex Work

- Validate downloaded content as a decodable image.
- Record dimensions, aspect ratio, format, and file size.
- Reject HTML/error responses and invalid payloads.
- Add perceptual or content duplicate detection where appropriate.
- Namespace cache entries by source, identity, slot, and URL/content hash.
- Implement match evidence and confidence calculation.
- Implement complete-set coherence checks.
- Add policy tests.

### Acceptance Criteria

- Invalid images cannot enter an apply plan.
- Wrong dimensions or ratios are visible and handled by policy.
- Conflicting editions require review.
- Automatic decisions include machine-readable reasons.

---

## Sprint 10 — Find Artwork for Selected

**Mode:** MIXED

### Objective

Deliver the requested bulk artwork workflow.

### Chat Work

- Review dialog wording and defaults.
- Define summary and review states.
- Review thresholds after fixture runs.

### Codex Work

- Add `Find Artwork for Selected` to the command bar and bulk-action bar.
- Add modes:
  - Missing slots only
  - All unlocked slots
  - Complete set only
- Queue one artwork job per selected game.
- Search enabled providers.
- Validate candidates.
- Score identity and set coherence.
- Auto-accept only when policy allows.
- Route uncertain results into review.
- Preserve manual locks.
- Add cancel, retry, skip, and summary actions.
- Add tests for batches of at least 20 items.

### Acceptance Criteria

- One action processes multiple selected games.
- The UI remains responsive.
- Strong matches may be accepted automatically.
- Weak, incomplete, or conflicting matches do not apply silently.
- Manual artwork is never overwritten without explicit permission.
- Each item ends in a defined result state.
- Failed items can be retried without rerunning successful items.

---

## Sprint 11 — Artwork Workspace and Candidate Review

**Mode:** MIXED

### Objective

Implement the polished artwork-focused right inspector from the approved UI direction.

### Chat Work

- Review slot labels, evidence wording, and candidate ordering.
- Create focused mockups for edge cases.

### Codex Work

- Build slot cards for portrait/grid, wide, hero, logo, and icon.
- Add current/proposed comparison.
- Add source and confidence display.
- Add Auto Match, Review Matches, Replace, Import, Lock, Clear, and Restore actions.
- Build candidate browser.
- Build review queue.
- Add keyboard actions for accept, skip, and next.

### Acceptance Criteria

- Every artwork slot is understandable and editable.
- Source and match evidence are visible.
- Review can be completed without returning to the main table for every item.
- Locks persist across rescans and provider refreshes.

---

## Sprint 12 — Preview, Apply Selected, and Restore UI

**Mode:** MIXED

### Objective

Expose the transaction system clearly in the modern interface.

### Chat Work

- Review safety language.
- Define confirmation thresholds.
- Define restore preview wording.

### Codex Work

- Build selected-item change preview.
- Separate safe artwork changes from launch/compatibility changes.
- Show files and fields affected.
- Show backup readiness.
- Apply only approved changes.
- Show write verification results.
- Build transaction history.
- Build restore-point browser.
- Add restore preview and verification.

### Acceptance Criteria

- User can see exactly what will change.
- No apply action bypasses transaction services.
- Verification status is truthful.
- A previous tested transaction can be restored from the UI.

---

## Sprint 13 — Native Steam Safe Controls

**Mode:** MIXED

### Prerequisite

`NATIVE_STEAM_FIELD_MATRIX.md` must exist and approve each implemented field.

### Objective

Add practical native Steam customization while leaving uncertain fields read-only.

### Chat Work

- Finish field research.
- Review field-specific warnings.
- Confirm which fields are safe enough for this release.

### Codex Work

- Implement approved fields one at a time.
- Add original/proposed value display.
- Add explicit review for launch and compatibility changes.
- Preserve unknown fields.
- Add per-field validation and rollback tests.
- Keep unsupported fields read-only.

### Acceptance Criteria

- Every writable field has ownership, validation, and rollback documentation.
- Native Steam edits are opt-in and reversible.
- Game installation files are never touched.
- Steam restarts or overwrites are handled and documented.

### Stop Conditions

- Field behavior differs unpredictably across tested environments.
- Unknown data cannot be preserved.
- Steam immediately destroys or rewrites the change without a stable strategy.

---

## Sprint 14 — Source Adapter Framework

**Mode:** MIXED

### Objective

Create a plugin-like source interface before implementing many launchers.

### Chat Work

- Complete source adapter matrix.
- Define common fields and diagnostics.
- Review duplicate-resolution cases.

### Codex Work

- Implement `SourceAdapter` interface.
- Implement folder scanner adapter.
- Implement native Steam adapter.
- Implement existing shortcut adapter.
- Add adapter diagnostics and test fixtures.
- Add reconciliation service for duplicate identities.

### Acceptance Criteria

- New sources can be added without changing the main UI workflow.
- Source errors are isolated and reportable.
- Manifest identity is preferred over folder heuristics.

---

## Sprint 15 — Windows Launcher Adapters

**Mode:** MIXED

### Objective

Add Windows launchers in controlled, independently testable increments.

### Order

1. Epic
2. GOG
3. Playnite
4. EA App
5. Ubisoft Connect
6. Battle.net
7. Microsoft Store/Xbox feasibility

### Chat Work

- Validate current manifest research before each adapter.
- Update source matrix when formats change.

### Codex Work

For each adapter:

- Add detection.
- Add sanitized fixtures.
- Parse identity, install location, and launch command.
- Record source evidence.
- Reconcile existing Steam entries.
- Add diagnostics.
- Test missing and malformed manifests.

### Acceptance Criteria

- Each adapter passes its own fixtures.
- One broken launcher source does not block the whole scan.
- Duplicate entries are surfaced for reconciliation.

---

## Sprint 16 — SteamOS/Bazzite Adapters

**Mode:** MIXED

### Objective

Extend the stable source architecture to Linux gaming tools.

### Order

1. Heroic
2. Lutris
3. Legendary
4. Bottles
5. Flatpak-aware installation handling

### Codex Work

- Add platform-specific adapters.
- Preserve launch command semantics.
- Represent compatibility requirements explicitly.
- Add common SteamOS/Bazzite path fixtures.
- Verify Windows behavior remains unchanged.

### Acceptance Criteria

- Supported Linux sources import with correct commands.
- Platform-specific data is not forced into Windows assumptions.
- Windows regression tests remain green.

---

## Sprint 17 — Diagnostics, Performance, and Recovery

**Mode:** CODEX

### Objective

Make large-library problems diagnosable and recoverable.

### Codex Work

- Add diagnostics export with secrets removed.
- Add queue and provider timing metrics.
- Add scan performance measurements.
- Add cache maintenance tools.
- Add recovery startup when an incomplete transaction is detected.
- Add logs for match evidence and write verification.
- Add safe database integrity checks.

### Acceptance Criteria

- A user can export useful diagnostics without exposing API keys.
- Interrupted transactions are detected.
- Representative large-library operations remain usable.

---

## Sprint 18 — Packaging and Personal-Use Release

**Mode:** MIXED

### Objective

Create a dependable build for regular personal use.

### Chat Work

- Draft user setup, backup, restore, and troubleshooting documentation.
- Review release checklist and known limitations.

### Codex Work

- Create Windows packaging or portable build.
- Validate settings migration.
- Verify optional dependencies.
- Add release smoke test.
- Add versioning and changelog process.
- Add Linux packaging notes or build where supported.

### Acceptance Criteria

- Fresh install starts successfully.
- Upgrade retains settings and manual choices.
- Backup and restore are documented and tested.
- Release artifacts do not contain API keys, caches, logs, or personal paths.

---

# Recommended Execution Order

```text
00 Baseline Audit
01 Transactional Writes
02 Safety Tests
03 UI Architecture Extraction
04 Modern App Shell
05 Unified Library Model
06 Multi-Selection
07 Job Queue
08 Bulk Scan/Metadata
09 Artwork Policy Engine
10 Find Artwork for Selected
11 Artwork Workspace
12 Preview/Apply/Restore UI
13 Native Steam Controls
14 Source Adapter Framework
15 Windows Launchers
16 SteamOS/Bazzite
17 Diagnostics/Performance
18 Packaging/Release
```

## Parallel Chat Work

The following may advance while Codex works on early sprints:

```text
CHAT-A1 Native Steam Field Research
CHAT-A2 UI Component Specification
CHAT-A3 Artwork Confidence Policy
CHAT-A4 Launcher Adapter Research
CHAT-A5 Test and Failure Matrix
```

## Immediate Next Sprint

Begin with **Sprint 00 — Baseline and Repository Audit**.

Do not start the visual rewrite or native Steam controls first. The approved UI and bulk-art workflow are retained in the roadmap, but the transaction and architecture foundations must be established before the app receives broader write authority.
