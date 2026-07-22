# P00 — Database Migration Runner

- **Size:** S
- **Prerequisite:** B03.
- **Objective:** safely evolve `LibraryStore` beyond schema version 1.

## Inspect

- `steam_shortcut_studio/library_store.py`
- library store tests
- settings/data-directory behavior

## Expected changes

- Extract schema creation and migrations into a focused module or tightly bounded functions.
- Back up the database before a version upgrade.
- Apply ordered migrations in one transaction where SQLite permits.
- Verify `PRAGMA user_version` and required objects.
- Restore the backup or leave the original untouched after injected failure.
- Refuse newer unsupported schemas.

## Tests

- Fresh database creation.
- Schema-v1 fixture upgrade.
- Injected migration failure.
- Backup existence and hash.
- Original remains usable after failure.
- Reopening an already-current database is idempotent.
- Concurrent initialization behavior remains safe.

## Non-goals

No new identity, recipe, note, or profile tables in this sprint.

## Acceptance

Migration mechanics are proven before schema v2 is introduced.
