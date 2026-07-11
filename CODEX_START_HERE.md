# Codex Start Here

This is the execution entrypoint for repository-capable coding sessions.

## Read First

Read these files in order:

1. `docs/PRODUCT_ROADMAP.md`
2. `docs/UI_UX_TARGET.md`
3. `docs/SPRINT_MAP.md`
4. `docs/SPRINT_STATUS.md`
5. `docs/CURRENT_ARCHITECTURE.md`
6. `docs/WRITE_PATH_AUDIT.md`
7. `docs/ARTWORK_MATCH_POLICY.md`
8. `docs/UI_FRAMEWORK_DECISION.md`
9. `docs/DEVELOPMENT_SETUP.md`

## Current Mission

Complete the active sprint in `docs/SPRINT_STATUS.md` without skipping prerequisites.

Do not start the full modern UI rewrite until the transaction and test foundations are complete.

## Non-Negotiable Safety Rules

- Never modify game installation files.
- Never test destructive behavior against the user's primary Steam profile.
- Do not silently replace a malformed `shortcuts.vdf`.
- Do not auto-apply weak, incomplete, conflicting, or manually locked artwork.
- Preserve unknown Steam fields.
- Back up before every Steam-owned write.
- Read back and verify every Steam-owned write.
- Roll back automatically when verification fails.
- Keep UI-framework changes separate from Steam-write changes.
- Do not mark work complete without test evidence.

## Existing Foundation

The repository already contains UI-independent groundwork:

- `steam_shortcut_studio/selection.py`
- `steam_shortcut_studio/jobs.py`
- `steam_shortcut_studio/artwork_policy.py`
- `tests/foundation_test.py`
- `.github/workflows/ci.yml`

These are foundations, not final integrations. Extend them carefully rather than duplicating their concepts inside `ui.py`.

## First Codex Session

Use this sequence:

```text
1. Inspect repository and current branch.
2. Run baseline validation from docs/DEVELOPMENT_SETUP.md.
3. Record all failures in docs/SPRINT_STATUS.md.
4. Confirm every Steam write call site against docs/WRITE_PATH_AUDIT.md.
5. Finish missing Sprint 00 evidence and fixture plan.
6. Do not change write behavior unless Sprint 00 acceptance criteria pass.
7. Commit the audit separately from implementation work.
```

## Next Engineering Sequence

After Sprint 00 passes:

```text
Sprint 01: transactional shortcut write service
Sprint 02: transaction history and restore foundation
Sprint 03: artwork staging, validation, and rollback
Sprint 04: extract UI services/controllers
Sprint 05: stable library identity and persistence
Sprint 06: modern library table and multi-selection
Sprint 07: background job queue
Sprint 08: bulk scan and metadata
Sprint 09: artwork validation and policy integration
Sprint 10: Find Artwork for Selected
```

Do not skip directly to Sprint 10. The selection and policy models exist, but safe execution requires stable IDs, a real queue, validated images, and transaction boundaries.

## Required Session Report

At the end of every session, update `docs/SPRINT_STATUS.md` with:

- Sprint and task IDs
- Files changed
- Commands run
- Test results
- CI state
- Risks and blockers
- Exact next action

## Compact Codex Instruction

```text
Read CODEX_START_HERE.md + all linked docs. Use SPRINT_STATUS active sprint only. Run baseline. Small changes. Tests with behavior. Never touch game files. Steam writes need backup + readback + rollback. Weak art goes review. Update status with evidence. Stop on unknown Steam fields.
```
