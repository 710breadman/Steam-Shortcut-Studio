# Steam Shortcut Studio Sprint Status

## Start Here

This is the persistent handoff for ChatGPT, Codex, and future development sessions.

Before changing code:

1. Read `CODEX_START_HERE.md` and its linked documents.
2. Confirm the active sprint and prerequisites below.
3. Inspect the repository and current tests.
4. Work only on the active sprint unless a prerequisite defect blocks it.

After changing code, record files, commands, results, risks, and the exact next action here.

## Current Position

- **Completed:** Sprint 00 — Baseline and Repository Audit
- **Active:** Sprint 01 — Transactional Steam Write Service
- **Sprint 01 status:** Transaction engine and strict shortcut service are merged; production legacy/UI-path integration remains
- **Next:** Sprint 02 — Transaction History and Restore Foundation
- **Priority product feature:** Multi-select `Find Artwork for Selected`
- **UI direction:** Approved mockup #2; read-only modern prototype is merged
- **Safety rule:** No broader native Steam editing before backup, verification, history, and rollback are proven

## Approved Product Decisions

- Personal library first
- Native Steam and non-Steam games in one library
- Launcher manifests preferred; folder scanning fallback
- Windows launcher support before SteamOS/Bazzite adapters
- Safe automation only; risky or uncertain changes require review
- Strong complete artwork matches may auto-apply
- Weak, incomplete, conflicting, or manually locked artwork requires review
- Game installation files are never modified
- Accent/theme options remain
- Modern dark blue UI by default

## Completed Foundation

### Planning and Architecture

- [x] Product roadmap and Sprint 00-18 map
- [x] `CHAT`, `CODEX`, and `MIXED` work separation
- [x] Current architecture audit
- [x] Steam/cache write-path audit
- [x] Transaction service specification
- [x] Sanitized fixture plan
- [x] Native Steam field safety matrix
- [x] Artwork match policy
- [x] UI framework decision
- [x] Development setup and Codex entrypoint

### Reusable Domain Contracts

- [x] Stable multi-selection state
- [x] Active inspector item separated from bulk selection
- [x] Job lifecycle, cancellation, retry, and batch summaries
- [x] Artwork auto-accept/review/reject policy
- [x] Transaction plans and risk approvals
- [x] Verification and result contracts

### CI

- [x] Existing smoke suite retained
- [x] Windows and Ubuntu
- [x] Python 3.11 and 3.13
- [x] Foundation and transaction tests
- [x] Optional UI prototype import on Windows and Ubuntu

## Sprint 01 — Transactional `shortcuts.vdf`

### Implemented and Merged

- [x] Generic staged file transaction engine
- [x] App-owned transaction directory
- [x] Grouped backup and JSON manifest
- [x] SHA-256 original/staged/written hashes
- [x] Same-directory atomic replacement
- [x] Stage-validation and read-back hooks
- [x] Automatic rollback and restore verification
- [x] Strict transactional shortcut service
- [x] Malformed active VDF aborts in strict service
- [x] Unrelated shortcut preservation tests
- [x] User-managed shortcut field preservation tests
- [x] Existing-file and new-file rollback tests
- [x] Cross-platform CI

### Remaining Before Sprint 01 Completion

- [ ] Route production `upsert_games` through the strict service
- [ ] Preserve the legacy tuple return shape
- [ ] Update the old malformed-file smoke test to expect abort-and-preserve
- [ ] Ensure UI handlers cannot bypass the transaction service
- [ ] Surface blocked-malformed-file errors clearly
- [ ] Confirm transaction cleanup/retention settings
- [ ] Record final integration CI evidence

### Acceptance Criteria

- [ ] No production UI handler writes `shortcuts.vdf` directly
- [ ] Every production shortcut write has a manifest, backup, verification, and rollback path
- [ ] Malformed input never silently replaces the active file
- [x] Verification failure automatically restores in tests
- [x] Existing suites remain green with the new service present
- [ ] Existing suites remain green after production integration

## Artwork Safety Foundation

Merged helper: `steam_shortcut_studio/image_validation.py`

- [x] Real Pillow decode validation
- [x] Format, dimensions, orientation, aspect ratio, mode, and alpha metadata
- [x] File-size and pixel-count limits
- [x] Reject empty, tiny, oversized, excessive-pixel, truncated, and unsupported images
- [x] Reject HTML, XML, and JSON error payloads with image extensions
- [x] SHA-256 content hash
- [x] Average perceptual hash and Hamming distance
- [x] Generated PNG/JPEG/error fixtures
- [x] Windows/Linux CI

This helper is not yet wired into provider downloads or Steam artwork copies. Later artwork work must validate immediately after download and after copy.

## Modern UI Prototype

Run:

```text
python -m pip install -r requirements-ui-prototype.txt
python prototypes/modern_shell.py
```

Implemented:

- [x] Dark blue three-column shell
- [x] Accent palettes
- [x] Left navigation and compact command bar
- [x] Mock library list
- [x] Multi-game checkboxes
- [x] Contextual bulk actions including `Find Art`
- [x] Artwork slot inspector and confidence panel
- [x] Backup, verification, and rollback cards
- [x] Apply disabled
- [x] Mock data only; no Steam reads or writes

Production UI integration waits for controller extraction and stable library persistence.

## Merged Pull Requests

- **#1:** Architecture, roadmap, CI, selection/job/policy/transaction contracts
- **#8:** Verified file transaction engine and strict shortcut service
- **#9:** Read-only modern UI shell prototype
- **#10:** Artwork image validation and duplicate-hash foundation

## Open Execution Issues

- **#2:** Complete production transactional `shortcuts.vdf` integration
- **#3:** Transaction history and atomic artwork writes
- **#4:** Service extraction and stable persistence
- **#5:** Modern multi-select library and background queue
- **#6:** `Find Artwork for Selected` and review workspace
- **#7:** Review and later adapt the UI prototype

## Latest Validation

All listed PRs were merged only after green GitHub Actions.

Latest artwork-validation run:

- Smoke Tests run 64: success
- CI run 45: success
- Four production matrix jobs passed
- Windows and Ubuntu UI-prototype imports passed

Current commands:

```text
python -m compileall -q steam_shortcut_studio tests main.py
python tests/smoke_test.py
python tests/foundation_test.py
python tests/transaction_test.py
python tests/file_transaction_test.py
python tests/shortcut_transaction_test.py
python tests/image_validation_test.py
python -m py_compile prototypes/modern_shell.py
```

## Known Risks

- `ui.py` still contains too many responsibilities
- The live shortcut path still uses legacy malformed-file recovery
- Artwork writes are not atomic as a complete set
- Image validation is not yet integrated into download/apply paths
- Native Steam settings may vary by platform or be overwritten by Steam
- The custom VDF parser needs broader fixtures for future field types
- The prototype must not duplicate domain logic

## Exact Next Action

Complete issue #2: switch the production shortcut path to the merged strict service and update the legacy malformed-file smoke expectation in the same change.

## Next Codex Prompt

```text
Read CODEX_START_HERE.md and all linked docs. Continue issue #2 / Sprint 01 only. The verified file engine and strict shortcut service are merged and green. Route production upsert_games through upsert_games_transactional while preserving the legacy tuple result and normal successful behavior. Update the old malformed-file smoke test to expect a clear abort with original bytes untouched. Ensure UI errors are understandable. Never add a fallback that silently replaces malformed data. Use temp/generated fixtures only. Run compileall, smoke_test.py, foundation_test.py, transaction_test.py, file_transaction_test.py, shortcut_transaction_test.py, and image_validation_test.py. Update this status file with exact evidence. Do not start native Steam field editing or production UI migration.
```
