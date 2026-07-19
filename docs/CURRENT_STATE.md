# Steam Shortcut Studio — Current State

**Updated:** 2026-07-19  
**Purpose:** factual source of truth for what exists today. Future work belongs in `PRODUCT_ROADMAP.md`.

## Product Position

Steam Shortcut Studio is a safe personal-library workshop for importing, identifying, repairing, organizing, and customizing Steam and non-Steam games. It is not intended to replace Steam or become a general-purpose launcher.

The core workflow is:

1. Scan Steam, supported launchers, and configured folders.
2. Normalize entries into a persistent library.
3. Select one or many games.
4. Find metadata and complete artwork sets.
5. Review uncertain identity, launch, or artwork decisions.
6. Preview every Steam-owned change.
7. Back up, apply, verify, and retain a rollback point.

## Production-Safe Foundations

Implemented and in production code:

- Transactional `shortcuts.vdf` writes.
- Malformed active VDF blocking.
- Staged parsing and structural validation.
- Read-back verification.
- Automatic rollback on verification failure.
- Preservation of unrelated shortcuts and user-managed fields.
- Atomic per-game artwork-set transactions.
- Source-image decoding and validation before writes.
- Artwork hash verification and complete-set rollback.
- Transaction manifests and restore-point history.
- Graceful Steam close/reopen ownership tracking.

No new feature may bypass these transaction boundaries.

## Persistent Library

The app-owned SQLite library supports:

- Stable source-specific IDs.
- Native Steam games.
- Existing non-Steam shortcuts.
- Epic Games Launcher installs.
- Loose/local game folders.
- Present, missing, and reappearing state.
- Manual display-title overrides.
- Manual launch target, arguments, and working-directory overrides.
- Personal notes.
- Artwork slot locks.
- Rejected artwork candidates.
- Scan history.

Partial or unavailable source scans do not mark stored games missing.

## Bulk and Background Work

Implemented:

- Stable selection by persistent library ID.
- Active inspector focus separated from bulk selection.
- Range, additive, visible-scope, and filter-scope selection.
- Bounded background workers.
- UI-safe immutable events.
- Per-item and aggregate progress.
- Cancellation and selective retry.
- Isolated per-game failures.
- Review-required job states.
- Bulk artwork modes for missing slots, all unlocked slots, and complete sets.
- Match policy routing to automatic accept, review, skip, or rejection.
- Real provider search behind UI-independent services.

## Current Sources

| Source | Status | Notes |
| --- | --- | --- |
| Native Steam | Implemented | Read-only scan; Steam writes remain separate and transactional. |
| Existing non-Steam shortcuts | Implemented | Preserves unrelated and user-managed fields. |
| Loose/local folders | Implemented | Ranked launch candidates with manual override support. |
| Epic Games Launcher | Implemented | Read-only `.item` manifest adapter with strong catalog identity. |
| Playnite | Planned first | Optional curated source; preserve game IDs and launch actions. |
| GOG Galaxy | Planned | Read-only database/manifest research required. |
| Battle.net | Planned | Preserve launcher and direct launch recipes when valid. |
| EA App | Later | Research storage ownership and stable identity first. |
| Ubisoft Connect | Later | Research storage ownership and stable identity first. |
| Amazon Games / itch.io / Rockstar / Xbox | Later | Windows-first expansion after core sources stabilize. |
| Heroic / Lutris / Legendary / Bottles / Faugus | Later | SteamOS/Bazzite phase. |

## Current UI

The production interface uses a CustomTkinter shell with existing ttk/Tk components where practical. It includes:

- Modern dark-blue production shell.
- Left navigation.
- Top command area.
- Persistent library table.
- Search, filtering, sorting, and stable multi-selection.
- Right-side details and artwork areas.
- Artwork review controls.
- Source scan progress and retry controls.
- Transaction-history access.

### Approved UI Direction

- Keep the current production UI operational.
- Build an isolated PySide6 proof using real controller data.
- Do not migrate unless the proof demonstrates a clear improvement in table performance, interaction quality, scaling, maintainability, and packaging.
- Keep the Python domain, service, persistence, transaction, and source-adapter layers regardless of UI outcome.

## Approved Product Decisions

- Build a PySide6 proof, then decide whether to migrate.
- Windows Explorer `Add to Steam` opens a compact review wizard.
- Store direct and launcher-based launch recipes; choose per game.
- Treat Playnite as a first-class optional source.
- Keep detailed app notes with an optional short Steam summary.
- Require an explicit target Steam profile.
- Detect source changes automatically, but require approval before Steam writes.
- Back up and restore collections before optional collection management.
- Show owned-but-uninstalled games later in a separate read-only view.
- Finish the Windows experience before SteamOS/Bazzite expansion.

## Known Gaps

- Cross-source duplicate and identity reconciliation is not yet a first-class subsystem.
- Library status needs explicit source, Steam, and Studio state separation.
- Structured notes and multiple launch recipes are not yet modeled.
- Windows Explorer quick-add is not implemented.
- Explicit multi-profile targeting is not complete.
- Collections backup/restore and management are not complete.
- Installable Windows alpha packaging needs a defined release pipeline.
- PySide6 has not yet been benchmarked against the current UI.

## Validation

GitHub Actions and local suites cover Windows and Ubuntu with supported Python versions. Relevant changes must run focused tests plus the appropriate CI-equivalent commands.

Do not treat documentation as stronger evidence than code and tests. When they disagree, update this document after verifying runtime behavior.
