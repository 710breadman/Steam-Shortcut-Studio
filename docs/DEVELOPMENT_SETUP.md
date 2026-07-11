# Development Setup

## Supported Development Targets

- Windows 10/11
- SteamOS/Bazzite or another modern Linux desktop
- Python 3.11 or newer

Windows is the first implementation target for launcher adapters and modern UI work. Linux remains a required regression target.

## Initial Setup

### Windows PowerShell

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If script execution is blocked for the current terminal only:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

### Linux

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Tkinter may be distributed separately by some Linux distributions. Install the matching system package if `python -c "import tkinter"` fails.

## Baseline Validation

Run these before changing code:

```bash
python -m compileall -q steam_shortcut_studio tests main.py
python tests/smoke_test.py
python tests/foundation_test.py
```

Record the exact commands and results in `docs/SPRINT_STATUS.md`.

## Running the App

```bash
python main.py
```

Use a test Steam profile or sanitized temporary paths when developing write behavior. Do not use a primary Steam profile for destructive or malformed-file tests.

## Safe Test Data Rules

- Never commit a real `shortcuts.vdf` without sanitizing names and paths.
- Never commit Steam account IDs, API keys, home paths, or personally identifying logs.
- Prefer generated fixture files.
- Keep malformed and edge-case fixtures in a dedicated `tests/fixtures/` directory.
- Document how each fixture was generated.
- Tests must write only into temporary directories.

## Branch and Sprint Workflow

1. Read:
   - `docs/PRODUCT_ROADMAP.md`
   - `docs/UI_UX_TARGET.md`
   - `docs/SPRINT_MAP.md`
   - `docs/SPRINT_STATUS.md`
2. Confirm the active sprint.
3. Create or use a focused branch.
4. Keep Steam-write changes separate from UI framework changes.
5. Add or update tests.
6. Run baseline validation.
7. Update `SPRINT_STATUS.md` with evidence.
8. Open a draft pull request.

## CI

`.github/workflows/ci.yml` runs the current smoke suite and foundation tests on:

- Ubuntu latest / Python 3.11
- Ubuntu latest / Python 3.13
- Windows latest / Python 3.11
- Windows latest / Python 3.13

A sprint that changes runtime behavior is not complete while CI is failing.

## UI Prototype Dependency

CustomTkinter is the selected prototype direction, but it is not yet a required runtime dependency. Do not add it to `requirements.txt` until:

- A small shell prototype exists.
- Windows and Linux packaging has been tested.
- The mixed CustomTkinter/ttk table layout works.
- Distribution size and startup impact are recorded.

Prototype dependencies may be placed in a separate development requirements file or branch until accepted.

## Useful Diagnostics

```bash
python --version
python -c "import tkinter; print(tkinter.TkVersion)"
python -c "from PIL import Image; print(Image.__version__)"
python -c "import certifi; print(certifi.where())"
```

## Codex Completion Report

Every Codex implementation session should end with:

```text
Sprint:
Scope completed:
Files changed:
Tests added/updated:
Commands run:
Results:
Known limitations:
Blockers:
Exact next action:
```
