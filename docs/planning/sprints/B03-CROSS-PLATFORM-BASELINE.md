# B03 — Cross-Platform Baseline Manifest

- **Size:** S
- **Prerequisites:** B01 and B02.
- **Objective:** prove the existing repository baseline before new architecture work.

## Work

1. Run every command from active CI workflows on Windows 3.11/3.13 and Ubuntu 3.11/3.13.
2. Run optional UI import/prototype checks.
3. Capture command, duration, exit code, pass/fail/skip count, warnings, OS, Python, dependency versions, and commit.
4. Write `artifacts/baseline/latest.json` and a concise Markdown summary.
5. CI verifies that the manifest commit equals the tested commit or clearly labels merge-commit testing.

## Forbidden

No feature, refactor, schema, or visual work.

## Acceptance

- Required matrix is green.
- Failures and skips are zero or explicitly approved.
- Report is reproducible and machine-readable.
- `CURRENT_STATE.md` points to the baseline evidence.
