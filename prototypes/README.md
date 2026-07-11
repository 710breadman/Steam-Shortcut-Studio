# Modern UI Shell Prototype

This folder contains non-production interface experiments for the approved dark blue Steam Shortcut Studio design.

## Safety Boundary

The prototype:

- Uses mock library data only
- Does not detect Steam
- Does not scan folders
- Does not call artwork providers
- Does not write Steam files
- Does not import production write services

It exists to validate layout, density, theme direction, multi-selection, and the artwork/safety inspector before production integration.

## Run

```bash
python -m pip install -r requirements-ui-prototype.txt
python prototypes/modern_shell.py
```

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

## Next Steps After Acceptance

1. Replace mock rows with controller-provided view models.
2. Connect stable IDs through `SelectionState`.
3. Connect progress through `JobRecord` and `BatchSummary`.
4. Connect previews through `TransactionPlan`.
5. Keep apply actions disabled until the production transaction service is fully integrated.
