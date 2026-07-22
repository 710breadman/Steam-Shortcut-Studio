# B02 — Fix Windows Source CLI Failure

- **Size:** XS/S
- **Prerequisite:** B00 traceback.
- **Objective:** make source CLI tests deterministic on Windows while preserving conservative scan persistence.

## Likely files

- `steam_shortcut_studio/source_cli.py`
- `steam_shortcut_studio/sources/local.py`
- `steam_shortcut_studio/scanner.py`
- `steam_shortcut_studio/library_store.py`
- `tests/source_cli_test.py`

Modify only the proven failure boundary.

## Safety

- Missing roots remain blocked and non-authoritative.
- Existing stored records remain present after blocked scans.
- Fake executable validation remains representative.
- Do not bypass Windows executable checks just for tests.
- Close all database/file handles deterministically.

## Tests

- Existing source CLI test.
- Source scan, folder source, library store, and scanner tests relevant to the defect.
- Windows 3.11/3.13 and Ubuntu matrix.

## Acceptance

- Original failing workflow passes.
- Regression coverage explains the Windows defect.
- JSON and human output remain stable or intentionally versioned.
- Conservative presence behavior is unchanged.
