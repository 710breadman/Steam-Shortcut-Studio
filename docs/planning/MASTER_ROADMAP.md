# Master Roadmap

## Completion definition

Steam Shortcut Studio is ready for a Windows alpha when a clean machine can install or run it, complete first-run setup, scan supported sources, reconcile review items, choose launch recipes, manage artwork, preview one explicit Steam profile, apply through verified transactions, inspect history, restore a known-good state, export diagnostics, upgrade without losing app data, and uninstall with documented retention behavior.

Visual parity is not part of the current completion gate. It begins afterward by owner direction.

## Phase 0 — Stabilize truth

**Goal:** stop planning on a red or contradictory baseline.

- Reproduce Windows failures.
- Fix transaction-history controller test behavior.
- Fix source CLI test behavior.
- Run all workflow commands on Windows and Ubuntu.
- Produce a machine-readable baseline manifest.
- Consolidate current-state and planning authority.
- Record or choose the project license.

**Exit:** all required CI jobs green; baseline report tied to a commit.

## Phase 1 — Persistence and state contracts

**Goal:** safely evolve the app-owned model.

- Add migration runner, backup, rollback, and fixture tests.
- Define explicit Source, Steam, Studio, artwork, and identity states.
- Add schema v2 without losing schema v1 data.
- Add multiple launch recipes and one explicit preferred recipe.
- Add structured notes with optional short Steam summary.
- Add explicit target-profile preference without defaulting all profiles.

**Exit:** upgrade/downgrade-failure tests prove app data preservation.

## Phase 2 — Identity and reconciliation

**Goal:** represent one game across many sources without unsafe merging.

- Immutable identity-cluster contracts.
- Exact-ID and executable/path evidence.
- Conservative scored proposals.
- Edition/platform conflict handling.
- Remembered merge, keep-separate, and ignore decisions.
- Missing/moved target detection.
- Dry-run reconciliation plans.
- Controller-ready review models.

**Exit:** exact relationships resolve; ambiguous sets require review; title-only never auto-merges.

## Phase 3 — Complete the core user workflow

**Goal:** one coherent path from scan to recovery.

- Source issue/review workspace.
- Launch-recipe review.
- Artwork review queue with locks and rejected candidates.
- Unified change-plan model.
- Explicit-profile preview.
- Transactional apply orchestration.
- Verification summary.
- History and restore workspace.
- Failure recovery and retry guidance.
- Repeat-scan behavior that preserves decisions.

**Exit:** a fixture library completes the entire workflow without hidden writes or manual file editing.

## Phase 4 — Windows alpha delivery

**Goal:** non-developer use on clean Windows systems.

- Installer versus portable decision.
- Reproducible release script.
- First-run setup.
- Sanitized diagnostics export.
- Upgrade preservation.
- Uninstall retention/removal choices.
- Crash/log locations.
- Release checklist and clean-machine acceptance.

**Exit:** signed-off clean-machine test for install, use, upgrade, recovery, and uninstall.

## Phase 5 — Source ecosystem

**Goal:** add sources only through proven adapter capabilities.

Order:

1. Playnite.
2. GOG Galaxy.
3. Battle.net.
4. Reassess EA App and Ubisoft Connect.
5. SteamOS/Bazzite after Windows acceptance.

Every adapter begins with format research, sanitized fixtures, read-only parsing, stable identity evidence, issue codes, and non-authoritative failure behavior.

**Exit:** each source passes fixture, missing-source, partial-source, rescan, and persistence tests.

## Phase 6 — Quality-of-life features

Candidate work, ordered by value and safety:

- Add-to-Steam Explorer context action that opens a review, never writes silently.
- Structured notes and optional Steam summary.
- Games detected but not added smart view.
- Duplicate/broken/missing smart views.
- Collection backup/restore before management.
- Artwork export/import by stable identity and slot.
- Provider language/platform/author filters.
- Portable-game launch recipes.

**Exit:** each feature has demand evidence, bounded maintenance, and reversible behavior.

## Phase 7 — Hardening and toolkit decision

- Deterministic 100/1,000/5,000-row benchmarks.
- Memory, startup, search, sort, selection, and background-event measurements.
- Accessibility and scaling review.
- Shutdown/cancellation/failure-injection tests.
- Isolated read-only PySide6 proof using real controller snapshots.
- Evidence-based keep/migrate decision.

No broad migration begins without an approved decision record.

## Phase 8 — Visual target phase, deferred

Only after Phases 0–7 are accepted:

- Install and verify the canonical source picture.
- Perform forensic layout analysis.
- Create deterministic screenshot fixtures.
- Build component and full-window comparison gates.
- Execute visual-parity sprints in the chosen production toolkit.

No current sprint may use the source picture as an implementation requirement.
