# Steam Shortcut Studio Sprint Status

## How to Use This File

This is the persistent handoff for ChatGPT, Codex, and future development sessions.

At the start of every coding session:

1. Read `CODEX_START_HERE.md`.
2. Read the linked roadmap, UI, architecture, audit, policy, and setup documents.
3. Confirm the active sprint and prerequisites below.
4. Inspect the repository before changing code.

At the end of every coding session:

1. Update completed checklist items.
2. Record files changed and commands run.
3. Record tests and CI results.
4. Record unresolved risks and blockers.
5. Set the exact next action.
6. Do not mark a sprint complete until its acceptance criteria pass.

## Current Position

- **Completed:** Sprint 00 — Baseline and Repository Audit
- **Active sprint:** Sprint 01 — Transactional Steam Write Service
- **Sprint 01 status:** Core service implemented and merged; live legacy/UI-path integration remains
- **Main branch foundation:** through commit `d2f918a`
- **Next sprint:** Sprint 02 — Transaction History and Restore Foundation
- **Priority feature:** Multi-select `Find Artwork for Selected`
- **UI direction:** Approved mockup #2; read-only modern shell prototype is merged
- **Safety priority:** Transaction, backup, verification, and rollback before broader native Steam editing

## Approved Product Decisions

- Personal library is the primary use case.
- Support native Steam games and non-Steam games.
- Prefer launcher manifests; use folder scanning as fallback.
- Windows launcher support comes before SteamOS/Bazzite expansion.
- Safe changes may automate; risky or uncertain changes require review.
- Strong, complete artwork matches may auto-apply under policy.
- Weak, incomplete, conflicting, or manually locked artwork requires review.
- Native Steam controls should be broad where practical, but must never break the library.
- Game installation files must never be modified.
- Theme/accent color options must remain.
- The approved UI direction is modern, dark, sleek, and blue by default.

## Completed Foundations

### Planning, Architecture, and Safety

- [x] Product roadmap and full sprint map
- [x] Chat/Codex/Mixed work separation
- [x] Current architecture audit
- [x] Steam/cache write-path audit
- [x] Transaction service specification
- [x] Sanitized fixture plan
- [x] Native Steam field safety matrix
- [x] Artwork automatic-acceptance policy
- [x] UI framework decision
- [x] Development setup and Codex entrypoint

### UI-Independent Models

- [x] Stable multi-selection state
- [x] Separate active inspector item from bulk selection
- [x] Job states, retry, cancellation, and batch summaries
- [x] Artwork auto-accept/review/reject policy model
- [x] Transaction plans, risk approvals, and verification results

### Test and CI Foundation

- [x] Existing smoke suite retained
- [x] Foundation tests
- [x] Transaction contract tests
- [x] Windows and Ubuntu matrix
- [x] Python 3.11 and 3.13 matrix
- [x] Optional UI prototype import validation on Windows and Linux

## Active Sprint 01 — Transactional `shortcuts.vdf`

### Implemented and Merged

- [x] Generic staged file transaction engine
- [x] App-owned transaction directory
- [x] Grouped backup and JSON manifest
- [x] SHA-256 hashing of original, staged, and written files
- [x] Same-directory temporary replacement for the active target
- [x] Format-specific stage validation hook
- [x] Format-specific read-back verification hook
- [x] Automatic rollback on apply or verification failure
- [x] Restore verification
- [x] Strict transactional shortcut service
- [x] Malformed active VDF aborts in the strict service
- [x] Unrelated shortcut records preserved in strict-service tests
- [x] User-managed shortcut fields preserved during updates
- [x] Generated new-file and existing-file rollback tests
- [x] Windows/Linux CI for all new transaction tests

### Remaining Before Sprint 01 Completion

- [ ] Route the production/legacy `upsert_games` interface through the strict service.
- [ ] Update the legacy malformed-file smoke expectation from replace-after-backup to abort-and-preserve.
- [ ] Ensure no UI handler can bypass the transaction service.
- [ ] Surface the blocked-malformed-file error clearly in the UI.
- [ ] Confirm transaction location and cleanup/retention settings.
- [ ] Record final integration CI evidence.

### Sprint 01 Acceptance Criteria

- [ ] No production UI event handler writes `shortcuts.vdf` directly.
- [ ] Every production shortcut write has a plan, backup manifest, verification result, and rollback path.
- [ ] Malformed input never silently replaces the active file.
- [x] Verification failure restores the original automatically in tests.
- [x] Existing smoke and foundation tests remain green with the service present.
- [ ] Existing smoke and foundation tests remain green after live integration.

## Modern UI Prototype

A read-only prototype is available at:

```text
prototypes/modern_shell.py
```

Run it with:

```text
python -m pip install -r requirements-ui-prototype.txt
python prototypes/modern_shell.py
```

Implemented prototype elements:

- [x] Dark blue three-column desktop shell
- [x] Accent palette selector
- [x] Left navigation
- [x] Compact action toolbar
- [x] Mock library list
- [x] Multi-game checkboxes
- [x] Contextual bulk action bar
- [x] `Find Art` for the selected set
- [x] Artwork slot inspector
- [x] Match confidence/provider panel
- [x] Backup, verification, and rollback cards
- [x] Apply disabled by design
- [x] Mock data only; no Steam detection or writes

Production UI integration remains in later sprints after controller extraction and stable library persistence.

## Merged Pull Requests

- **PR #1:** Safety, architecture, CI, selection/job/policy/transaction foundations
- **PR #8:** Verified file transaction engine and strict transactional shortcut service
- **PR #9:** Read-only modern UI shell prototype

## Open Execution Issues

- **#2:** Sprint 01 — Transactional `shortcuts.vdf` integration
- **#3:** Sprint 02-03 — Transaction history and atomic artwork writes
- **#4:** Sprint 04-05 — UI service extraction and stable persistence
- **#5:** Sprint 06-08 — Modern multi-select library and background queue
- **#6:** Sprint 09-11 — `Find Artwork for Selected` and review workspace
- **#7:** Modern UI prototype review and eventual production adaptation

## Latest Validation Evidence

Transaction service PR:

- Smoke Tests run 50: success
- CI run 31: success
- All Windows/Ubuntu and Python 3.11/3.13 jobs passed
- File transaction and shortcut rollback suites passed

Modern UI prototype PR:

- Smoke Tests run 57: success
- CI run 38: success
- Production test matrix passed
- Optional CustomTkinter import passed on Windows and Ubuntu

Commands covered:

```text
python -m compileall -q steam_shortcut_studio tests main.py
python tests/smoke_test.py
python tests/foundation_test.py
python tests/transaction_test.py
python tests/file_transaction_test.py
python tests/shortcut_transaction_test.py
python -m py_compile prototypes/modern_shell.py
```

## Current Blockers

No blocker for continuing Sprint 01.

The production switch must update the old malformed-file smoke test in the same change. Do not temporarily disable the smoke suite or retain a silent recovery fallback merely to keep the old expectation passing.

## Known Risks

- `ui.py` still carries too many responsibilities.
- The live shortcut path still uses legacy malformed-file recovery until Sprint 01 integration is complete.
- Artwork writes are not yet atomic as a set.
- Native Steam settings may be overwritten by Steam or vary by platform.
- The custom VDF parser needs broader fixtures before unknown future field types can be trusted.
- The prototype must not become a second implementation of domain logic.

## Exact Next Action

Use Codex on issue #2 to complete the production switch to `upsert_games_transactional` while preserving the legacy public return shape and normal successful behavior.

## Next Codex Prompt

```text
Read CODEX_START_HERE.md and all linked docs. Continue issue #2 / Sprint 01 only. The verified file engine and strict shortcut service are already merged and green. Route the production upsert_games path through upsert_games_transactional while preserving the legacy tuple result and successful behavior. Update the old malformed-file smoke test to expect a clear abort with the original bytes untouched and no fresh active file. Ensure UI errors are understandable. Do not add a fallback that silently replaces malformed data. Use temp/generated fixtures only. Run compileall, smoke_test.py, foundation_test.py, transaction_test.py, file_transaction_test.py, shortcut_transaction_test.py, and all new tests. Update SPRINT_STATUS with exact evidence. Do not begin native Steam field editing or production UI migration.
```
