# B00 — Windows Failure Reproduction

- **Parent phase:** Phase 0
- **Size:** XS
- **Objective:** obtain complete, reproducible evidence for the two current Windows CI failures.
- **User-visible result:** none; restores trustworthy engineering baseline.
- **Reason:** fixing by guess risks masking platform defects.

## Inspect

- `.github/workflows/ci.yml`
- `.github/workflows/source-cli.yml`
- `tests/transaction_history_controller_test.py`
- `tests/source_cli_test.py`

## Modify

Prefer no production changes. A tiny diagnostic-only test adjustment is allowed only when required to expose the failing assertion or cleanup error.

## Forbidden

- `steam_shortcut_studio/ui.py`
- transaction semantics
- source behavior
- schema changes
- source-picture/design files

## Steps

1. Use Windows Python 3.11 matching CI.
2. Install `requirements.txt`.
3. Run each failing test alone with unbuffered output.
4. Repeat under Python 3.13 if available.
5. Record Windows version, Python version, temp root, exit code, full traceback, and whether the failure occurs during assertion, file cleanup, SQLite cleanup, encoding, or path comparison.
6. Run the equivalent tests on Ubuntu only to confirm platform difference.
7. Do not implement a fix.

## Commands

```powershell
python -u tests/transaction_history_controller_test.py
python -u tests/source_cli_test.py
```

## Acceptance

- Both Windows failures are reproduced, or CI logs/artifacts provide complete tracebacks.
- Evidence names the exact failing line and exception.
- `PERSISTENT_HANDOFF.md` is updated.
- No behavior change is committed.

## Stop

Stop after evidence capture. Do not begin B01 or B02.
