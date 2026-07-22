# Codex Start Here

Read this before changing Steam Shortcut Studio.

## Product

Steam Shortcut Studio is a safe personal-library workshop for Steam and non-Steam PC games. It scans sources, reconciles identity and launch choices, manages complete artwork sets, previews approved Steam changes, applies them through verified transactions, and preserves rollback evidence. It is not a replacement launcher.

## Current authority

1. `docs/CURRENT_STATE.md` — verified current capability and known gaps.
2. `docs/audit/REPOSITORY_REALITY_AUDIT.md` — audit evidence and limitations.
3. `docs/design/sss-vision.png` — canonical visual target.
4. `docs/planning/MASTER_ROADMAP.md` — dependency-ordered future work.
5. `docs/planning/SPRINT_INDEX.md` — active implementation sequence.
6. The active sprint and its Gemma prompt.
7. Code and tests — final authority when documentation differs.

Older sprint maps and `docs/SPRINT_STATUS.md` are historical.

## Immediate order

1. Fix the Windows CI failures recorded in the audit.
2. Establish a green cross-platform baseline.
3. Install the canonical SSS Vision asset and visual regression harness.
4. Complete the isolated PySide6 proof and measured toolkit decision.
5. Execute SSS Vision parity sprints in the chosen toolkit.
6. Complete identity, reconciliation, profile-targeted apply, recovery, sources, and release work.

## Do not rebuild

Reuse `LibraryStore`, `LibraryController`, `SelectionState`, `BackgroundJobQueue`, source adapters/coordinator, artwork policy/search/coordinator, image validation, shortcut/artwork transaction services, transaction history, and immutable job events.

## Hard safety rules

- Never modify game installation files.
- Never write Steam data directly from UI code or source adapters.
- Never replace malformed active VDF data.
- Never allow worker threads to manipulate widgets.
- Never let partial or unavailable scans mark stored games missing.
- Never discard manual overrides, artwork locks, rejected matches, notes, collections, or launch choices.
- Never merge identities from title alone.
- Never silently change a preferred launch recipe.
- Never default writes to all Steam profiles.
- Never show backup, verification, or rollback success without real evidence.
- Never call a feature complete because a screen, button, class, or stub exists.

## Worker limits

Gemma receives one XS, S, or M sprint. Target 8K–20K input tokens; stop near 28K. Supply only directly relevant files, tests, crop references, and decisions. Gemma stops when acceptance criteria are met and does not start the next sprint.

## Required finish

Run focused tests, capture required screenshots, record commands/results, update `docs/planning/PERSISTENT_HANDOFF.md`, and state the exact next command. Failed or unavailable validation must be labeled, not hidden.
