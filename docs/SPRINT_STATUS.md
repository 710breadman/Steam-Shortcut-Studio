# Steam Shortcut Studio Sprint Status

## How to Use This File

This is the persistent handoff file for ChatGPT, Codex, and future development sessions.

At the start of every coding session:

1. Read `CODEX_START_HERE.md`.
2. Read the linked roadmap, UI, architecture, audit, policy, and setup documents.
3. Confirm the active sprint and prerequisites.
4. Inspect the repository before changing code.

At the end of every coding session:

1. Update completed checklist items.
2. Record files changed.
3. Record tests and commands run.
4. Record unresolved risks and blockers.
5. Set the exact next action.
6. Do not mark a sprint complete until acceptance criteria pass.

## Current Position

- **Completed:** Sprint 00 — Baseline and Repository Audit
- **Active sprint:** Sprint 01 — Transactional Steam Write Service
- **Status:** Ready for Codex implementation
- **Working branch/PR:** `agent/foundation-and-bulk-artwork` / draft PR #1
- **Next sprint:** Sprint 02 — Transaction History and Restore Foundation
- **Product direction:** Approved
- **UI direction:** Approved mockup #2 style; incremental CustomTkinter shell prototype after safety boundaries
- **Priority feature:** Multi-select `Find Artwork for Selected`
- **Safety priority:** Transaction, backup, verification, and rollback before broader native Steam editing

## Approved Product Decisions

- Personal library is the primary use case.
- Support native Steam games and non-Steam games.
- Prefer launcher manifests; use folder scanning as fallback.
- Windows launcher support comes before SteamOS/Bazzite expansion.
- Safe changes may automate; risky or uncertain changes require review.
- Strong artwork matches may auto-apply under policy.
- Weak, incomplete, conflicting, or manually locked artwork requires review.
- Native Steam controls should be broad where practical, but must never break the library.
- Game installation files must never be modified.
- Theme/accent color options must remain.
- The approved UI direction is modern, dark, sleek, and blue by default.

## Sprint 00 Completion Evidence

### Repository and Runtime

- [x] Record current branch and latest branch commits.
- [x] Record Python version requirements.
- [x] Record supported operating systems.
- [x] Verify development dependencies in CI.
- [x] Run the complete current smoke suite in CI.
- [x] Record baseline result: no failures.

### Architecture Inventory

- [x] Map package/module structure.
- [x] Identify responsibilities currently inside `ui.py`.
- [x] Identify scanner, metadata, artwork, Steam detection, VDF, and settings boundaries.
- [x] Identify current background-thread/job concerns.
- [x] Identify persistent settings and cache formats.

### Steam Write Audit

- [x] Find the paths that write `shortcuts.vdf`.
- [x] Find the paths that write Steam grid artwork.
- [x] Record settings/cache cleanup write behavior.
- [x] Record Steam close/reopen requirements.
- [x] Record existing backup behavior.
- [x] Record malformed-file behavior.
- [x] Record unknown-field preservation risk.

### Required Deliverables

- [x] `docs/CURRENT_ARCHITECTURE.md`
- [x] `docs/WRITE_PATH_AUDIT.md`
- [x] `docs/FIXTURE_PLAN.md`
- [x] `docs/TRANSACTION_SERVICE_SPEC.md`
- [x] `docs/NATIVE_STEAM_FIELD_MATRIX.md`
- [x] `docs/ARTWORK_MATCH_POLICY.md`
- [x] `docs/UI_FRAMEWORK_DECISION.md`
- [x] `docs/DEVELOPMENT_SETUP.md`
- [x] `CODEX_START_HERE.md`
- [x] Cross-platform CI
- [x] Selection, job, artwork-policy, and transaction-plan foundations
- [x] Foundation and transaction tests

### CI Results

GitHub Actions completed successfully on draft PR #1:

- **Smoke Tests**, run 38: success
- **CI**, run 19: success
- CI matrix: Windows and Ubuntu, Python 3.11 and 3.13

Commands covered:

```text
python -m compileall -q steam_shortcut_studio tests main.py
python tests/smoke_test.py
python tests/foundation_test.py
python tests/transaction_test.py
```

### Sprint 00 Acceptance Criteria

- [x] Baseline tests are recorded and passing.
- [x] All known Steam write categories are listed.
- [x] Current architecture dependencies are documented.
- [x] Risks and blockers are explicit.
- [x] Sprint 01 can start without guessing where writes occur.

## Active Sprint 01 Checklist

### Objective

Route `shortcuts.vdf` writes through a transactional service without changing successful user-visible behavior.

### Codex Work

- [ ] Add file-operation abstraction for staging, backup, hash, replace, and restore.
- [ ] Build prepared shortcut transactions from `TransactionPlan`.
- [ ] Preserve unrelated shortcuts and user-managed fields.
- [ ] Change malformed-file default to abort without replacing the active file.
- [ ] Create grouped transaction manifests/backups.
- [ ] Stage and parse proposed binary VDF before apply.
- [ ] Read back and verify owned fields and unrelated-record preservation.
- [ ] Roll back automatically on apply or verification failure.
- [ ] Keep current UI call sites working through the service.
- [ ] Add generated and malformed VDF fixtures.
- [ ] Update tests and this status file with evidence.

### Sprint 01 Acceptance Criteria

- [ ] No UI event handler writes `shortcuts.vdf` directly.
- [ ] Every shortcut write has a plan, backup manifest, verification result, and rollback path.
- [ ] Malformed input does not silently replace the active file.
- [ ] Verification failure restores the original automatically.
- [ ] Existing smoke and foundation tests remain green.

## Current Blockers

None for starting Sprint 01.

Do not test destructive behavior against the user's primary Steam profile. Use generated fixtures and temporary directories.

## Known Risks

- `ui.py` carries too many responsibilities.
- Steam-owned binary/config formats are safety-critical.
- Malformed `shortcuts.vdf` recovery currently writes a fresh active file after backup; Sprint 01 must change this default.
- Artwork writes are not yet atomic as a set.
- Native Steam settings may be overwritten by Steam or vary by platform.
- UI modernization must remain separate from write-path work.
- The custom VDF parser needs broader fixtures before unknown future fields can be trusted.

## Session Log

### 2026-07-11 — Foundation, audit, and execution setup

- Completed repository architecture and write-path audits.
- Added transaction, fixture, artwork policy, native field, UI framework, development, and Codex handoff documents.
- Added stable selection, job state, artwork decision, and transaction-plan contracts.
- Added cross-platform CI and tests.
- Opened draft PR #1.
- Created implementation issues #2 through #7 for transaction safety, history/artwork rollback, service extraction/persistence, multi-select queue, bulk artwork, and modern UI prototype.
- Both GitHub Actions workflows passed.
- Existing live Steam-write behavior remains unchanged on this branch.

## Exact Next Action

Use Codex on issue #2: **Sprint 01: Transactional shortcuts.vdf service**.

## Next Codex Prompt

```text
Read CODEX_START_HERE.md and all linked docs. Sprint 00 is complete and CI is green. Execute issue #2 / Sprint 01 only. Wrap shortcuts.vdf in a transaction service with staging, grouped backup manifest, SHA-256, readback verification, and automatic rollback. Malformed input must abort by default and leave the active file untouched. Preserve unrelated records and user-managed fields. Keep current UI behavior working through the new service. Use generated fixtures and temp directories only. Run compileall, smoke_test.py, foundation_test.py, transaction_test.py, and all new tests. Update SPRINT_STATUS with exact commands/results. Small commits. Do not start UI modernization or native Steam field edits.
```
