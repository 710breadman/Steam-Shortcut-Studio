# B01 — Fix Windows Transaction-History Failure

- **Size:** XS/S
- **Prerequisite:** B00 traceback.
- **Objective:** make transaction-history controller behavior deterministic on Windows without weakening restore evidence.

## Likely files

- `steam_shortcut_studio/transaction_history.py`
- `steam_shortcut_studio/transaction_history_view.py`
- `steam_shortcut_studio/transaction_history_controller.py`
- `tests/transaction_history_controller_test.py`

Modify only files proven relevant by B00.

## Safety

- Never hide a missing backup.
- Preserve canonical target, backup, and manifest paths.
- Do not make tests pass by ignoring path or file errors.
- Normalize only at a defined boundary.

## Tests

- Existing controller test.
- History and view tests.
- New Windows-specific regression fixture if the defect is platform semantics.
- Run on Windows 3.11 and 3.13, then Ubuntu.

## Acceptance

- Original failure test passes on all matrix targets.
- Regression test fails on the old implementation and passes on the fix.
- Backup availability remains truthful.
- No unrelated transaction behavior changes.
