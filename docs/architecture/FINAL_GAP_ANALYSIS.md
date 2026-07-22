# Final Gap Analysis

## Current architecture

```text
source adapters
  -> SourceScanCoordinator
  -> LibraryStore (source records, overrides, locks, rejects, scan history)
  -> LibraryController + SelectionState
  -> UI views / background immutable events

metadata/artwork providers
  -> ArtworkSearchService
  -> policy + BulkArtworkCoordinator
  -> review decisions
  -> ArtworkSetTransaction

selected library records
  -> shortcut plan/merge
  -> verified file transaction
  -> transaction history
```

This direction is sound. The problem is incomplete contracts and integration, not a missing architecture.

## Critical gaps

### 1. CI baseline

Windows-specific failures are unresolved. No new feature phase should begin while the baseline is red.

### 2. Persistence evolution

`SCHEMA_VERSION = 1` has no migration implementation. New identity, launch-recipe, structured-note, profile-choice, and decision data require a tested migration framework before schema growth.

### 3. Product state

The system needs distinct dimensions rather than one vague status:

- Source state: present, missing, unavailable, incomplete, moved, review.
- Steam state: native, existing shortcut, absent, duplicate, broken target.
- Studio state: clean, customized, pending, review, blocked, applied, recoverable.
- Artwork state per slot and complete-set state.
- Identity confidence and conflict state.

### 4. Identity and reconciliation

Stable source IDs are not the same as a unified game identity. A cluster must preserve all source records, installations, exact IDs, evidence, conflicts, and remembered owner decisions.

### 5. Launch modeling

A game may have direct executable, source launcher, URI, compatibility wrapper, or portable launch recipes. One explicit preferred recipe is needed without deleting alternatives.

### 6. End-to-end plan

The UI currently exposes pieces of scanning, selection, artwork, writes, and history. It needs one controller-owned change plan that states:

- target profile;
- selected records;
- identity/launch decisions;
- shortcut changes;
- artwork changes;
- notes/collection changes;
- backup targets;
- verification checks;
- rollback plan.

### 7. Recovery

Automatic rollback exists internally, but users also need understandable restore points, explicit restore actions, verification, and failure guidance.

### 8. UI coupling

`ui.py` remains too large. Extract one tested controller/view-model responsibility at a time. Do not perform a broad UI rewrite.

### 9. Packaging

A build artifact is not an accepted release. Installation, portable launch, upgrades, state preservation, uninstall behavior, diagnostics, and clean-machine testing are required.

### 10. License

The repository needs an explicit root license before public distribution or code reuse decisions.

## Recommended dependency order

1. Green CI.
2. Baseline manifest and documentation authority.
3. Migration framework.
4. Explicit state contracts.
5. Identity and reconciliation.
6. Launch recipes and structured notes.
7. Controller-owned change plan.
8. Profile-targeted preview/apply/verify/restore.
9. Packaging and diagnostics.
10. New sources and quality-of-life work.
11. Performance/accessibility/toolkit decision.
12. Source-picture and visual-parity phase.

## Rewrite decision

A rewrite is rejected. It would discard tested transaction, persistence, selection, job, source, and artwork foundations and increase Steam-data risk. Incremental extraction is cheaper, safer, and independently reviewable.
