# Codex Start Here

Read this file before changing Steam Shortcut Studio.

## Source of Truth

1. `docs/CURRENT_STATE.md` — what exists now.
2. `docs/PRODUCT_ROADMAP.md` — future priorities and approved decisions.
3. The active GitHub issue — exact implementation scope.
4. Code and tests — final authority when documentation differs.

Older sprint maps and `docs/SPRINT_STATUS.md` are historical evidence, not the active backlog.

## Current Product Direction

Steam Shortcut Studio is a safe personal-library workshop for Steam and non-Steam games. It is not a replacement launcher.

Approved decisions:

- Keep the Python core.
- Keep the production CustomTkinter UI operational.
- Build a measured PySide6 proof before deciding on migration.
- Finish Windows before SteamOS/Bazzite expansion.
- Make Playnite the first new optional source, followed by GOG and Battle.net.
- Store direct and launcher-based launch recipes per game.
- Use detailed app-owned notes with an optional short Steam summary.
- Require an explicit target Steam profile.
- Detect source changes automatically, but require approval before Steam writes.
- Back up and restore collections before optional collection management.

## Immediate P0 Order

Work only from a focused GitHub issue. Current P0 sequence:

1. Installable Windows alpha.
2. PySide6 library proof.
3. 100/1,000/5,000-row UI benchmarks.
4. Cross-source identity and reconciliation foundation.

Do not combine UI migration, reconciliation, launcher adapters, packaging, and Steam-write changes in one pull request.

## Existing Systems — Do Not Rebuild

```text
steam_shortcut_studio/selection.py
steam_shortcut_studio/jobs.py
steam_shortcut_studio/job_queue.py
steam_shortcut_studio/library_controller.py
steam_shortcut_studio/library_store.py
steam_shortcut_studio/source_scans.py
steam_shortcut_studio/sources/base.py
steam_shortcut_studio/sources/epic.py
steam_shortcut_studio/sources/steam.py
steam_shortcut_studio/sources/local.py
steam_shortcut_studio/artwork_policy.py
steam_shortcut_studio/bulk_artwork.py
steam_shortcut_studio/artwork_search_service.py
steam_shortcut_studio/image_validation.py
steam_shortcut_studio/transactions.py
steam_shortcut_studio/file_transactions.py
steam_shortcut_studio/shortcut_transactions.py
steam_shortcut_studio/artwork_transactions.py
steam_shortcut_studio/transaction_history.py
```

Reuse controllers, services, persistent IDs, transactions, and immutable job events.

## Required Safety Rules

- Never modify game installation files.
- Never add direct Steam writes outside transaction services.
- Never replace malformed active VDF data.
- Never let worker threads touch UI widgets.
- Never let partial source scans mark stored games missing.
- Never discard manual overrides, artwork locks, rejected matches, notes, collections, or launch choices during rescans.
- Never merge identities from title alone.
- Never silently change the preferred launch recipe.
- Never default writes to every Steam profile.
- Never enable risky native Steam changes without ownership research, preview, verification, and rollback.

## Implementation Discipline

For each issue:

1. Read the issue and only the directly relevant design documents.
2. Inspect current code before proposing new abstractions.
3. Add or update tests with the implementation.
4. Keep commits small and reversible.
5. Record validation in the PR description.
6. Update `docs/CURRENT_STATE.md` only when actual capability changes.
7. Update `docs/PRODUCT_ROADMAP.md` only when priorities or approved decisions change.

## Validation

Run focused tests for every touched subsystem. For a major integration PR, also run the relevant CI-equivalent commands from `.github/workflows/`.

Minimum baseline:

```text
python -m compileall -q steam_shortcut_studio tests main.py
python tests/foundation_test.py
python tests/smoke_test.py
```

Add the transaction, persistence, source, artwork, UI, or packaging suites required by the change. Never mark work complete because code was written; provide passing evidence or name the blocker.
