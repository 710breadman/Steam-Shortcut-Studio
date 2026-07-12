# Modern UI Shell Prototype

This folder contains non-production interface experiments for the approved dark blue Steam Shortcut Studio design.

## Safety Boundary

The prototypes:

- Do not detect or control Steam
- Do not write Steam shortcuts or artwork
- Do not call artwork providers
- Keep Apply disabled
- Use either mock data or the app's own read-only persistent library database

They exist to validate layout, density, theme direction, multi-selection, artwork review, and safety/history presentation before production integration.

## Run the Design Mock

```bash
python -m pip install -r requirements-ui-prototype.txt
python prototypes/modern_shell.py
```

## Run With Persistent Library Data

First populate the library, for example with Epic manifests:

```powershell
python -m steam_shortcut_studio.cli scan-epic
```

Then open the approved modern shell with those stored games:

```powershell
python prototypes/modern_library.py
```

Options:

```powershell
python prototypes/modern_library.py --include-missing
python prototypes/modern_library.py --database "D:\Data\sss-library.sqlite3"
python prototypes/modern_library.py --empty
```

If no stored games exist, the runner shows the original mock data unless `--empty` is supplied.

CustomTkinter remains optional until Windows/Linux rendering, DPI behavior, startup time, and packaging impact are accepted.

## Review Checklist

- Does the overall layout match approved mockup #2?
- Is the library table readable at 1100x700 and larger?
- Is selection scope obvious?
- Are bulk actions visible only when relevant?
- Are artwork slots easy to scan?
- Are safety and rollback states clear?
- Do accent choices remain useful without reducing contrast?
- Does the interface still feel calm when many games need review?
- Do real stored titles, sources, status, and sizes fit naturally?

## Remaining Production Integration

1. Replace prototype-local selection with `SelectionState`.
2. Connect `BackgroundJobQueue` progress and summaries.
3. Connect `BulkArtworkCoordinator` through the Find Art action.
4. Connect transaction history to the Backups view.
5. Keep apply actions disabled until provider review and production UI integration are complete.
