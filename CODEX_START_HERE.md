# Codex Start Here

Read this before changing Steam Shortcut Studio.

## Product

Steam Shortcut Studio is a safe personal-library workshop for Steam and non-Steam PC games. It scans sources, reconciles identity and launch choices, manages artwork, previews approved Steam changes, applies them through verified transactions, and preserves recovery evidence. It is not a replacement launcher.

## Current authority

1. `docs/CURRENT_STATE.md` — verified capability and known gaps.
2. `docs/audit/REPOSITORY_REALITY_AUDIT.md` — audit evidence and limitations.
3. `docs/planning/MASTER_ROADMAP.md` — dependency-ordered future work.
4. `docs/planning/SPRINT_INDEX.md` — implementation sequence.
5. The active sprint and Gemma prompt.
6. Code and tests — final authority when documentation differs.

Older sprint maps and `docs/SPRINT_STATUS.md` are historical.

## Owner priority override

Do not analyze or reproduce the SSS Vision source picture yet. Core correctness, architecture, data, workflow, tests, packaging, and source integrations must be sorted first. The image remains a later visual target, not a current work input.

## Immediate order

1. Reproduce and fix the Windows CI failures.
2. Establish a green cross-platform baseline.
3. Finish repository and architecture truth documents.
4. Add versioned persistence, explicit state contracts, identity clusters, reconciliation, and launch recipes.
5. Complete the end-to-end source → review → preview → apply → verify → restore workflow.
6. Prove Windows packaging, first-run setup, diagnostics, upgrade, and uninstall behavior.
7. Add approved source integrations and quality-of-life work.
8. Run performance, accessibility, reliability, and toolkit decision gates.
9. Only then begin SSS Vision asset analysis and visual-parity work.

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

Gemma receives one XS, S, or M sprint. Target 8K–20K input tokens; stop near 28K. Supply only directly relevant files, tests, and decisions. Gemma stops when acceptance criteria are met and does not start the next sprint.

## Required finish

Run focused tests, record commands/results, update `docs/planning/PERSISTENT_HANDOFF.md`, and state the exact next command. Failed or unavailable validation must be labeled, not hidden.
