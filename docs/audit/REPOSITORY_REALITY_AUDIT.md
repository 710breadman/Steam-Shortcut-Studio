# Repository Reality Audit

**Audit date:** 2026-07-22  
**Repository:** `710breadman/Steam-Shortcut-Studio`  
**Default branch:** `main`  
**Default-branch head observed:** `9915d34017c536f96b902eb36847380d387be7ea`  
**Open planning PR:** `#39`, head `d062c64a684b2bd40393f155ac9b6674d5c8e87a`  
**Audit-planning branch:** `agent/final-audit-roadmap`

## Audit method

Inspected through GitHub:

- Repository metadata and default branch.
- Current and historical planning documents.
- Main runtime entry points and dependencies.
- Source, persistence, controller, artwork, transaction, and UI modules.
- Tests and workflow definitions.
- Open issues and PRs.
- Workflow runs and job-step outcomes.
- Comparable repositories and licenses.

The environment could not resolve `github.com` for a local clone. No claim is made that this audit independently ran the complete test suite.

## Repository shape

- Language/runtime: Python desktop application.
- Production UI: CustomTkinter with Tk/ttk components.
- Optional prototype: CustomTkinter and approved isolated PySide6 research direction.
- Persistence: SQLite, schema version 1.
- Packaging: PyInstaller spec, Windows release workflow, Linux desktop entry.
- Dependencies: Pillow, CustomTkinter, certifi; standard-library-first core.
- Main risk concentration: `steam_shortcut_studio/ui.py` remains oversized and orchestration-heavy.

## Confirmed working foundations

### Steam safety

`shortcut_transactions.py` blocks malformed active VDF files, validates staged records, compares signed/unsigned AppID semantics, reads back written records, and routes through verified file transactions.

`artwork_transactions.py` validates every source image before writes, stages and hashes files, backs up all targets, writes atomically, verifies hashes, and rolls back the complete set after failure.

**Status:** production foundation complete; final end-to-end user acceptance still required.

### Persistent library

`LibraryStore` provides source records, manual overrides, notes, artwork locks, rejected matches, and scan history with WAL and short-lived connections.

**Status:** backend complete for schema v1; migration, identity clustering, launch recipes, and richer states missing.

### Sources

Implemented source boundaries exist for Steam, Epic, and local folders. Scans are persisted conservatively so unavailable sources do not erase presence state.

**Status:** current adapters substantially implemented; broader launcher ecosystem missing.

### Selection and jobs

Selection is stable-ID based and independent from widget row identity. Background jobs are bounded, cancellable, retryable, and communicate through immutable events.

**Status:** foundation complete; final UI consistency and stress acceptance pending.

### Artwork

Provider search, candidate adaptation, policy routing, review outcomes, locks, rejected matches, validation, and grouped transactions exist.

**Status:** backend mostly complete; production review and apply workflow partially integrated.

## Current CI reality

For PR `#39`:

- Smoke Tests: passed.
- UI prototype import jobs: passed on Windows and Ubuntu.
- Main CI: Ubuntu jobs passed; Windows Python 3.11 and 3.13 failed at `tests/transaction_history_controller_test.py`, causing later steps to skip.
- Source CLI workflow: Ubuntu passed; Windows Python 3.11 and 3.13 failed at `tests/source_cli_test.py`.

This is the active baseline. Documentation claiming the complete Windows suite passes is stale until new evidence replaces these runs.

## Open P0 work

- `#34` installable Windows alpha.
- `#35` isolated PySide6 library proof.
- `#36` reproducible 100/1,000/5,000-row benchmarks.
- `#37` cross-source identity cluster contracts.
- `#38` duplicate detection and reconciliation planning.

These are valid directions but were missing an explicit prerequisite: fix current Windows CI before expansion.

## Important gaps

1. Green Windows CI.
2. Reproducible baseline report tied to a commit.
3. SQLite migration framework.
4. Explicit Source, Steam, and Studio state model.
5. Cross-source identity clusters and evidence.
6. Remembered merge/keep-separate/ignore decisions.
7. Multiple launch recipes with explicit preference.
8. Full review-to-preview-to-apply workflow.
9. Explicit target Steam profile at every write boundary.
10. User-facing restore and failure recovery.
11. Clean-machine installer, upgrade, and uninstall proof.
12. Structured diagnostics and sanitized support export.
13. Root project license.
14. Accessibility and large-library acceptance.
15. Visual parity, intentionally deferred by the owner.

## Obsolete or non-authoritative material

- `docs/SPRINT_MAP.md` and `docs/SPRINT_STATUS.md` contain useful historical evidence but are not the active backlog.
- Prototypes are evidence, not production completion.
- A button or view is not considered complete without a connected service, tests, and runtime evidence.

## Audit conclusion

The project is not nearly empty and should not be rewritten. It has unusually strong write-safety, persistence, job, selection, and artwork foundations. It is also not release-complete. The fastest safe route is to stabilize CI, finish domain contracts and end-to-end workflows, prove packaging, add high-value sources, then handle final visual reconstruction.
