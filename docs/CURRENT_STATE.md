# Steam Shortcut Studio — Current State

**Verified audit date:** 2026-07-22  
**Purpose:** factual description of what exists now. Future work belongs in `docs/planning/MASTER_ROADMAP.md`.

## Product position

Steam Shortcut Studio is a safe personal-library workshop for importing, identifying, repairing, organizing, and customizing Steam and non-Steam PC games. It is not intended to replace Steam.

The intended production workflow is:

1. Detect Steam and configured sources.
2. Scan native Steam games, existing shortcuts, supported launchers, and loose folders.
3. Normalize records into an app-owned persistent library.
4. Select one or many games.
5. Find metadata and complete artwork sets.
6. Review uncertain identity, launch, or artwork decisions.
7. Preview all Steam-owned changes for one explicit profile.
8. Back up, apply, verify, and retain rollback evidence.

## Production-safe foundations

Code and tests support these foundations:

- Strict transactional `shortcuts.vdf` writes.
- Malformed active VDF blocking.
- Staged parsing and structural validation.
- Read-back verification and automatic rollback.
- Preservation of unrelated shortcuts and user-managed fields.
- Atomic per-game artwork-set transactions.
- Image decode and hash validation before and after writes.
- Complete artwork-set rollback and stale-extension cleanup.
- Transaction manifests and history.
- Steam close/reopen ownership tracking.

No feature may bypass these boundaries.

## Persistent library

The SQLite library currently supports:

- Stable source-specific IDs.
- Native Steam games.
- Existing non-Steam shortcuts.
- Epic Games Launcher installs.
- Loose/local folders.
- Present, missing, and reappearing state.
- Manual title and launch overrides.
- Personal notes.
- Artwork slot locks.
- Rejected artwork candidates.
- Scan history.

Partial or unavailable source scans are designed to be non-authoritative. The current schema is version 1 and does not yet have a real migration path.

## Selection, jobs, and artwork foundations

Implemented foundations include:

- Stable selection by persistent library ID.
- Active inspector focus separate from bulk selection.
- Range, additive, visible-scope, and filter-scope selection.
- Bounded background workers and immutable UI events.
- Per-item and aggregate progress, cancellation, retry, and review states.
- Artwork modes for missing slots, all unlocked slots, and complete sets.
- Real provider search behind UI-independent services.
- Policy routing to automatic accept, review, skip, or rejection.
- Production grouped artwork transactions.

The production artwork review experience is only partially integrated and has not passed the final SSS Vision or end-to-end acceptance gates.

## Current sources

| Source | Current status |
| --- | --- |
| Native Steam | Implemented read-only scan |
| Existing non-Steam shortcuts | Implemented read and preserved transactional update |
| Epic Games Launcher | Implemented read-only `.item` adapter |
| Loose/local folders | Implemented ranked scan with manual override support |
| Playnite | Planned next; research and fixture gate first |
| GOG Galaxy | Planned after Playnite |
| Battle.net | Planned after GOG; launcher-first launch policy |
| EA App / Ubisoft Connect | Deferred to a later evidence gate |
| SteamOS/Bazzite sources | Intentionally later than the Windows alpha |

## Current UI

The production entry point uses a CustomTkinter shell with ttk/Tk components and a controller-backed persistent library. It includes a modern dark shell, navigation, command area, table, selection, inspector, artwork controls, source progress, and transaction-history access.

This is not proof of SSS Vision parity. Before this audit there was no canonical repository copy of the exact reference, deterministic screenshot fixture, crop manifest, mixed visual metric, or accepted component-by-component parity report.

A PySide6 proof is approved only as an isolated read-only experiment. Migration is not approved until measured evidence shows a clear win in responsiveness, interaction quality, scaling, maintainability, and packaging.

## Known release blockers

- Windows CI failures on the open vNext planning PR:
  - `tests/transaction_history_controller_test.py`
  - `tests/source_cli_test.py`
- No verified green cross-platform baseline tied to the final planning commit.
- No canonical SSS Vision regression harness or accepted parity evidence.
- No first-class cross-source identity/reconciliation subsystem.
- No versioned database migration mechanism.
- Explicit Source/Steam/Studio states are incomplete.
- Multiple launch recipes and structured notes are not production-complete.
- Explicit profile-targeted preview/apply needs a final integrated acceptance gate.
- Restore is not yet a complete end-user workflow.
- Installer/upgrade/uninstall behavior is not proven on a clean Windows machine.
- The repository has no root license at audit time.

## Evidence limits

The audit inspected repository files, pull requests, issues, commits, workflows, and workflow results through GitHub. The complete suite could not be run in the audit container because external Git cloning was unavailable. CI results are therefore treated as runtime evidence, while local-machine pass claims remain provisional unless linked to reproducible output.
