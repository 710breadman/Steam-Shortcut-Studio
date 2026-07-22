# Independent Board Reports

These reports were written as separate viewpoints. The synthesis appears in `BOARD_DECISIONS.md` and `MASTER_ROADMAP.md`.

## 1. Product Director

The product is a safe Steam-library workshop, not a launcher replacement. Completion depends on a coherent repeatable workflow and recoverability, not the number of supported launchers. Identity, launch choice, explicit profile targeting, packaging, and restore are necessary. Experimental native-Steam editing is not.

## 2. SSS Vision Director

Owner direction defers all source-picture inspection and parity work. No visual measurements or recommendations are made. The later phase must start fresh after non-visual acceptance.

## 3. Desktop UI/UX Architect

The immediate UI problem is state coherence, not color or spacing. One record can be present in a source, absent from Steam, customized in Studio, and missing artwork. The interface needs explicit state dimensions, stable selection, review queues, a change plan, and recovery. Broad toolkit migration is premature.

## 4. User Workflow Advocate

The weak point is the middle of the journey: after scan and before safe apply. Users need to understand duplicates, missing targets, launch choices, uncertain artwork, target profile, expected changes, and recovery. First-run setup and repeat use are also release gates.

## 5. Software Architecture Director

Keep the domain core. `ui.py` is oversized, but extraction should follow completed workflows. Build migration and identity contracts before new adapters. Use controllers/view models; never duplicate business logic in a PySide proof.

## 6. Steam Safety Director

Shortcut and artwork transactions are strong foundations. Remaining risk is orchestration: wrong target profile, mixed partial plans, misleading success, and incomplete restore. All future writes must consume one previewed plan and produce verified history.

## 7. Artwork and Metadata Director

Provider and transaction foundations are substantial. Finish the review queue, complete-set coherence, locks, rejected candidates, provider failure behavior, and explicit plan integration before adding more sources or art features.

## 8. Launcher Ecosystem Director

Use capability-driven adapters. Playnite provides broad installed-library value, GOG is a high-value direct source, and Battle.net needs launcher-first recipes. EA and Ubisoft should wait for format stability evidence. Every adapter needs sanitized fixtures and non-authoritative failure handling.

## 9. Reliability and Test Director

Current Windows CI failures invalidate a “ready” claim. Fix them first, publish a baseline manifest, add migration/failure-injection tests, and benchmark large libraries. Local pass claims without reproducible logs are provisional.

## 10. Accessibility and Input Director

Keyboard behavior exists in pieces but needs a complete acceptance matrix: focus visibility, range selection, filter changes, dialogs, scaling, contrast, and non-color status. Perform this after workflows stabilize and before final visual work.

## 11. Packaging and Release Director

PyInstaller files are a start, not an alpha. Required proof includes clean install or portable launch, first run, state paths, diagnostics, upgrade preservation, uninstall choices, and recovery on a machine without development tools.

## 12. Community Research Director

Repeated external needs include robust backup/restore, artwork-type filtering, platform/language/style controls, custom Steam paths, Linux icon handling, programmatic configuration, duplicate control, and compatibility-tool support. These support the roadmap, but none should bypass product scope or safety.

## 13. Gemma Execution Director

Gemma should receive one narrow sprint, normally 1–4 production files plus tests, with explicit forbidden files and a stop condition. The first packet is failure reproduction only; it must not guess a fix without a traceback.

## 14. Red-Team Director

Primary threats to the plan are: treating documentation as runtime proof, adding schema fields before migration, title-only merging, broad UI migration, adapter expansion before release, missing project licensing, and allowing deferred visual work to creep back into active sprints. The revised order addresses these threats if gates are enforced.
