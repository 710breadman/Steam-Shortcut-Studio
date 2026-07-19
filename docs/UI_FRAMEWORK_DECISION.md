# UI Framework Decision

**Status:** PySide6 proof approved; migration not yet approved  
**Updated:** 2026-07-19

## Decision

Keep the current production CustomTkinter/ttk interface operational while building one isolated PySide6 proof of the central library workflow.

Do not rewrite the domain core. The following remain Python and UI-independent regardless of the result:

- Library persistence.
- Source adapters and scan coordination.
- Stable selection.
- Background jobs.
- Metadata and artwork services.
- Identity and reconciliation logic.
- Steam transaction, verification, history, and rollback services.

A full UI migration occurs only when measured evidence shows that PySide6 provides a worthwhile improvement.

## Why the Decision Changed

The earlier decision deferred PySide6 until transaction, selection, queue, persistence, and controller boundaries were stable. Those foundations now exist. The project can test a second UI without coupling the experiment to Steam writes or rebuilding application logic.

The current interface remains the production baseline and fallback.

## Proof Scope

Build one library workspace using real `LibraryController` data and immutable events.

Required features:

- 100, 1,000, and 5,000 generated library rows.
- Thumbnail, title, source, platform, explicit state columns, artwork state, confidence, and row actions.
- Search, filtering, sorting, grouping, saved views, and stable multi-selection.
- Active inspector focus separated from batch selection.
- Right-side inspector with artwork slot cards.
- Context menus and keyboard actions.
- Drag-and-drop entry points.
- Background queue progress and terminal states.
- Read-only operation; no new Steam-write path.

## Evaluation Matrix

Compare the proof against the current production UI:

| Area | Measurement |
| --- | --- |
| Initial load | Time to first usable library at 100/1,000/5,000 rows |
| Search/filter | Median and worst observed response time |
| Sort | Response time and selection preservation |
| Selection | Range, additive, visible, and filter-scope correctness |
| Background work | Event throughput without UI stalls |
| Memory | Baseline and thumbnail-heavy use |
| Scaling | Windows 100%, 125%, and 150% |
| Linux | Basic Bazzite/SteamOS-compatible launch and rendering |
| Packaging | Build size, startup time, dependency complexity |
| Maintainability | Code size, state boundaries, custom widget burden |
| UX | Table clarity, inspector flow, keyboard use, review speed |

## Migration Gate

Approve migration only when all are true:

- The proof is materially more responsive or scalable.
- The model/view table clearly simplifies selection, sorting, filtering, and custom cell states.
- Windows scaling is reliable.
- Linux support remains viable.
- Packaging cost is acceptable.
- Controller and transaction boundaries remain unchanged.
- A staged screen-by-screen migration can keep the current UI usable.

If the proof does not clearly win, retain CustomTkinter/ttk and apply the useful interaction findings there.

## Options Rejected for This Stage

### C# / Avalonia

Potentially strong cross-platform UI, but it would introduce a second language boundary or require a broader rewrite without first proving that Python/Qt is insufficient.

### WinUI 3 or WPF

Windows-focused and inconsistent with the planned SteamOS/Bazzite phase.

### JavaFX

Requires a rewrite with little direct advantage for the existing Python services.

### Electron, Tauri, or Flutter

Adds a frontend/backend bridge and packaging architecture before the desktop workflow has proven that need.

## Proof Safety Rules

- Read real app-owned library data only.
- Do not write Steam files.
- Do not duplicate controllers or services inside widgets.
- Do not replace the current production entry point.
- Do not begin broad migration before the benchmark report and explicit decision.
