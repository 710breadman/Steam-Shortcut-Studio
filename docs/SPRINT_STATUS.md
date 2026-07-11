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

- **Active sprint:** Sprint 00 — Baseline and Repository Audit
- **Status:** In progress — architecture/write audits and foundation scaffolding complete; CI validation pending
- **Working branch:** `agent/foundation-and-bulk-artwork`
- **Next sprint:** Sprint 01 — Transactional Steam Write Service
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

## Active Sprint Checklist

### Sprint 00 — Baseline and Repository Audit

#### Repository and Runtime

- [x] Record current branch and latest branch commits.
- [x] Record Python version requirements.
- [x] Record supported operating systems.
- [ ] Verify development dependencies in CI/local runtime.
- [ ] Run the complete current smoke suite in CI/local runtime.
- [ ] Record all baseline failures without hiding them.

#### Architecture Inventory

- [x] Map package/module structure.
- [x] Identify responsibilities currently inside `ui.py`.
- [x] Identify scanner, metadata, artwork, Steam detection, VDF, and settings boundaries.
- [x] Identify current background-thread/job concerns.
- [x] Identify persistent settings and cache formats.

#### Steam Write Audit

- [x] Find the paths that write `shortcuts.vdf`.
- [x] Find the paths that write Steam grid artwork.
- [x] Record settings/cache cleanup write behavior.
- [x] Record Steam close/reopen requirements.
- [x] Record existing backup behavior.
- [x] Record malformed-file behavior.
- [x] Record unknown-field preservation risk.

#### Workflow Baseline

- [x] Record startup and UI coordination architecture.
- [x] Record Steam detection flow.
- [x] Record folder and existing-shortcut scan flow.
- [x] Record native Steam artwork boundary.
- [x] Record non-Steam shortcut write flow.
- [x] Record preview and transaction requirements.
- [x] Record error/logging responsibilities and current concentration in `ui.py`.

#### Required Deliverables

- [x] Create `docs/CURRENT_ARCHITECTURE.md`.
- [x] Create `docs/WRITE_PATH_AUDIT.md`.
- [x] Create `docs/FIXTURE_PLAN.md`.
- [x] Create `docs/TRANSACTION_SERVICE_SPEC.md`.
- [x] Create `docs/NATIVE_STEAM_FIELD_MATRIX.md`.
- [x] Create `docs/ARTWORK_MATCH_POLICY.md`.
- [x] Create `docs/UI_FRAMEWORK_DECISION.md`.
- [x] Add cross-platform CI workflow.
- [x] Add UI-independent selection, job, artwork-policy, and transaction-plan foundations.
- [x] Add foundation tests.
- [x] Update this status file with evidence.

#### Sprint 00 Acceptance Criteria

- [ ] Baseline tests are recorded and passing or failures are explicitly accepted.
- [x] All known Steam write categories are listed.
- [x] Current architecture dependencies are documented.
- [x] Risks and blockers are explicit.
- [x] Sprint 01 can start without guessing where writes occur.

## Current Blockers

- GitHub CI results are not yet recorded. Sprint 00 remains open until the new workflow runs on the pull request and results are reviewed.
- No destructive Steam-write behavior has been exercised against a real Steam profile, by design.

## Known Risks

- `ui.py` carries too many responsibilities.
- Steam-owned binary/config formats are safety-critical.
- Malformed `shortcuts.vdf` recovery currently writes a fresh active file after backup; future default must abort instead.
- Artwork identity can be wrong even when title matching appears strong.
- Artwork writes are not yet atomic as a set.
- Native Steam settings may be overwritten by Steam or vary by platform.
- UI modernization can become a large rewrite if not kept separate from safety work.
- Bulk jobs can freeze or destabilize the UI without a worker/event boundary.
- The custom VDF parser needs broader fixtures before unknown future fields can be trusted.

## Session Log

### 2026-07-11 — Foundation and audit branch

Planning and documentation:

- Completed current architecture map.
- Completed Steam/cache write-path audit.
- Added transaction service specification.
- Added native Steam field safety matrix.
- Added sanitized fixture plan.
- Added conservative bulk artwork policy.
- Researched UI options and selected incremental CustomTkinter shell prototyping rather than an immediate PySide6 rewrite.
- Added development setup and Codex entrypoint.

Non-breaking code foundations:

- Added `selection.py` for stable multi-selection and separate inspector focus.
- Added `jobs.py` for queued/running/review/failure/cancel/retry states and batch summaries.
- Added `artwork_policy.py` for explicit auto-accept/review/reject decisions.
- Added `transactions.py` for change plans, risk approval, verification contracts, and result state.
- Added standard-library tests for these foundations.
- Added Windows/Linux CI across Python 3.11 and 3.13.

Runtime behavior:

- Existing Steam write call sites were not changed.
- New foundation modules are not wired into the live UI yet.
- No claim of runtime success is made until CI results are captured.

## Last Implementation Evidence

Pending pull-request CI.

Expected commands:

```text
python -m compileall -q steam_shortcut_studio tests main.py
python tests/smoke_test.py
python tests/foundation_test.py
python tests/transaction_test.py
```

## Exact Next Action

1. Open the foundation branch as a draft pull request.
2. Review all CI jobs on Windows/Linux and Python 3.11/3.13.
3. Fix any failures without changing Steam behavior.
4. Record CI evidence here.
5. Mark Sprint 00 complete only after baseline validation.
6. Begin Sprint 01 by wrapping `shortcuts.vdf` in the transaction service while preserving current behavior behind tests.

## Next Codex Prompt

```text
Read CODEX_START_HERE.md and all linked docs. Work only on Sprint 00 until CI is green and evidence is recorded. Do not rewrite UI or change Steam writes. Run compileall, smoke_test.py, foundation_test.py, and transaction_test.py. Fix only baseline/foundation failures. Update SPRINT_STATUS with exact commands/results. When Sprint 00 passes, start Sprint 01 by wrapping shortcuts.vdf in a transaction service with abort-on-malformed, backup manifest, readback verification, and automatic rollback. Keep legacy UI call sites working through the new service. Small commits. Tests required.
```
