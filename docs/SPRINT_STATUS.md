# Steam Shortcut Studio Sprint Status

## How to Use This File

This is the persistent handoff file for ChatGPT, Codex, and future development sessions.

At the start of every coding session:

1. Read `docs/PRODUCT_ROADMAP.md`.
2. Read `docs/UI_UX_TARGET.md`.
3. Read `docs/SPRINT_MAP.md`.
4. Read this file.
5. Confirm the active sprint and its prerequisites.
6. Inspect the repository before changing code.

At the end of every coding session:

1. Update completed checklist items.
2. Record files changed.
3. Record tests and commands run.
4. Record unresolved risks and blockers.
5. Set the exact next action.
6. Do not mark a sprint complete until its acceptance criteria pass.

## Current Position

- **Active sprint:** Sprint 00 — Baseline and Repository Audit
- **Status:** Not started
- **Next sprint:** Sprint 01 — Transactional Steam Write Service
- **Product direction:** Approved
- **UI direction:** Approved mockup #2 style; see `UI_UX_TARGET.md`
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

- [ ] Record current branch and latest commit.
- [ ] Record Python version requirements.
- [ ] Record supported operating systems.
- [ ] Install or verify development dependencies.
- [ ] Run the current test suite.
- [ ] Record all baseline failures without hiding them.

#### Architecture Inventory

- [ ] Map package/module structure.
- [ ] Identify responsibilities currently inside `ui.py`.
- [ ] Identify scanner, metadata, artwork, Steam detection, VDF, and settings boundaries.
- [ ] Identify background-thread or async behavior.
- [ ] Identify persistent settings and cache formats.

#### Steam Write Audit

- [ ] Find every path that writes `shortcuts.vdf`.
- [ ] Find every path that writes Steam grid artwork.
- [ ] Find every path that changes or deletes cached artwork.
- [ ] Find every path that closes or reopens Steam.
- [ ] Record existing backup behavior.
- [ ] Record malformed-file behavior.
- [ ] Record how unknown VDF fields are handled.

#### Workflow Baseline

- [ ] Record startup flow.
- [ ] Record Steam detection flow.
- [ ] Record folder scan flow.
- [ ] Record existing shortcut scan flow.
- [ ] Record native Steam artwork flow.
- [ ] Record non-Steam shortcut write flow.
- [ ] Record preview flow.
- [ ] Record error and logging behavior.

#### Required Deliverables

- [ ] Create `docs/CURRENT_ARCHITECTURE.md`.
- [ ] Create `docs/WRITE_PATH_AUDIT.md`.
- [ ] Add sanitized fixture plan.
- [ ] Update this status file with evidence.

#### Sprint 00 Acceptance Criteria

- [ ] Baseline tests are recorded.
- [ ] All known Steam write paths are listed.
- [ ] Current architecture dependencies are documented.
- [ ] Risks and blockers are explicit.
- [ ] Sprint 01 can start without guessing where writes occur.

## Current Blockers

None recorded. Codex must verify that the project runs and the current tests are usable before implementation begins.

## Known Risks

- The main UI module currently carries too many responsibilities.
- Steam-owned binary/config formats are safety-critical.
- Artwork identity can be wrong even when title matching appears strong.
- Native Steam settings may be overwritten by Steam or vary by platform.
- UI modernization can become a large rewrite if not kept separate from safety work.
- Bulk jobs can freeze or destabilize the UI without a proper queue and event boundary.

## Session Log

### 2026-07-11 — Planning retained in repository

- Added product roadmap.
- Added approved UI/UX target.
- Added full sprint map.
- Added this persistent status tracker.
- Recorded multi-selected-game artwork search as a primary requirement.
- No application code changed.
- No runtime validation performed in this planning update.

## Last Implementation Evidence

No implementation sprint has run yet.

## Exact Next Action

Use Codex on **Sprint 00 — Baseline and Repository Audit**.

Codex should not begin the UI rewrite immediately. It should first produce the architecture and write-path audits, run the baseline tests, and update this file with the results.

## Codex Start Prompt

```text
Read these files first:
- docs/PRODUCT_ROADMAP.md
- docs/UI_UX_TARGET.md
- docs/SPRINT_MAP.md
- docs/SPRINT_STATUS.md

Execute only Sprint 00 — Baseline and Repository Audit.

Rules:
- Do not begin the UI rewrite.
- Do not change Steam write behavior.
- Do not add native Steam setting edits.
- Run and record the existing tests.
- Map all modules and responsibilities.
- Find every Steam-owned file write path.
- Create docs/CURRENT_ARCHITECTURE.md.
- Create docs/WRITE_PATH_AUDIT.md.
- Add a sanitized fixture plan.
- Update docs/SPRINT_STATUS.md with commands, results, blockers, and the exact next action.
- Keep changes documentation-only unless a minimal change is required to run the audit; document any such change explicitly.
```
