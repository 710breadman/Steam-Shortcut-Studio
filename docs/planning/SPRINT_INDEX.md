# Sprint Index

Each implementation sprint is XS, S, or M. No sprint combines a major refactor, feature, and visual redesign. Tests ship with the change. Gemma stops after the sprint acceptance gate.

## Phase 0 — Stabilize truth

| ID | Size | Title | Depends on |
| --- | --- | --- | --- |
| B00 | XS | Reproduce Windows failures and capture evidence | none |
| B01 | XS/S | Fix transaction-history controller Windows failure | B00 |
| B02 | XS/S | Fix source CLI Windows failure | B00 |
| B03 | S | Run full cross-platform baseline and publish manifest | B01, B02 |
| B04 | XS | Consolidate authoritative docs and retire contradictions | B03 |
| B05 | XS | Choose and add root project license | owner decision |

## Phase 1 — Persistence and state

| ID | Size | Title | Depends on |
| --- | --- | --- | --- |
| P00 | S | Database backup and migration runner | B03 |
| P01 | S | Schema-v1 migration fixtures and failure rollback | P00 |
| P02 | S | Explicit Source/Steam/Studio state contracts | B03 |
| P03 | S | Persist explicit state evidence without derived duplication | P00, P02 |
| P04 | M | Launch-recipe schema and models | P00, P02 |
| P05 | S | Preferred launch-recipe policy | P04 |
| P06 | S | Structured app notes and optional Steam-summary contract | P00 |
| P07 | S | Explicit target-profile preference and validation | P00 |

## Phase 2 — Identity and reconciliation

| ID | Size | Title | Depends on |
| --- | --- | --- | --- |
| I00 | S | Identity-cluster immutable models | P02, P04 |
| I01 | S | Exact-ID and managed-shortcut evidence | I00 |
| I02 | S | Path/executable and launcher evidence | I00 |
| I03 | S | Conservative fallback evidence and conflict rules | I01, I02 |
| I04 | S | Remembered merge/keep-separate/ignore persistence | P00, I00 |
| I05 | M | Identity proposal service | I01–I04 |
| I06 | S | Missing/moved target detector | P04, I02 |
| I07 | M | Dry-run reconciliation plan | I05, I06 |
| I08 | S | Controller-ready reconciliation review model | I07 |

## Phase 3 — Complete core workflow

| ID | Size | Title | Depends on |
| --- | --- | --- | --- |
| W00 | S | Source issue/review workspace controller | P02, B03 |
| W01 | S | Launch-recipe review controller | P05, I08 |
| W02 | M | Artwork review queue completion | B03, P02 |
| W03 | S | Unified change-plan contracts | W00–W02, I08, P07 |
| W04 | S | Shortcut plan builder for explicit profile | W03 |
| W05 | S | Artwork plan builder for explicit profile | W03 |
| W06 | S | Preview summary and blocked-state explanations | W04, W05 |
| W07 | M | Transactional apply orchestrator | W06 |
| W08 | S | Verification result and recovery guidance | W07 |
| W09 | M | User-directed restore workflow | W08 |
| W10 | S | Repeat-scan preservation acceptance | W09 |

## Phase 4 — Windows alpha

| ID | Size | Title | Depends on |
| --- | --- | --- | --- |
| R00 | S | Installer vs portable decision experiment | B03 |
| R01 | S | Reproducible Windows build script | R00 |
| R02 | M | First-run setup controller and UI | P07, R01 |
| R03 | S | Sanitized diagnostics export | R01 |
| R04 | S | Upgrade data-preservation test | P01, R01 |
| R05 | S | Uninstall retention/removal behavior | R01 |
| R06 | M | Clean-machine alpha acceptance | W10, R02–R05 |

## Phase 5 — Sources

| ID | Size | Title | Depends on |
| --- | --- | --- | --- |
| S00 | S | Playnite format research and sanitized fixtures | P04, I00 |
| S01 | M | Read-only Playnite adapter | S00 |
| S02 | S | GOG format research and fixtures | S01 |
| S03 | M | Read-only GOG adapter | S02 |
| S04 | S | Battle.net format/launch research and fixtures | S03 |
| S05 | M | Read-only Battle.net adapter | S04 |
| S06 | XS | Reassess EA/Ubisoft priority from evidence | S05 |
| S07 | S | SteamOS/Bazzite source and packaging research gate | R06 |

## Phase 6 — Quality of life

| ID | Size | Title | Depends on |
| --- | --- | --- | --- |
| Q00 | S | Smart views: detected-not-added, duplicate, broken, missing | I08 |
| Q01 | S | Safe Explorer “Review in Steam Shortcut Studio” action | R06, W03 |
| Q02 | S | Structured notes workspace | P06 |
| Q03 | M | Collection backup/restore foundation | W09 |
| Q04 | S | Artwork export/import by identity and slot | W02 |
| Q05 | S | Provider language/platform/author filters | W02 |
| Q06 | S | Portable-game recipe workflow | P05, W01 |

## Phase 7 — Hardening and toolkit decision

| ID | Size | Title | Depends on |
| --- | --- | --- | --- |
| H00 | S | Deterministic 100/1k/5k dataset generator | B03, P02 |
| H01 | S | Production UI benchmark harness | H00 |
| H02 | M | Isolated read-only PySide6 proof | H00 |
| H03 | S | Comparative toolkit decision record | H01, H02 |
| H04 | S | Accessibility and scaling acceptance | H03 |
| H05 | S | Shutdown, cancellation, and failure injection | W10 |
| H06 | S | Logging, crash recovery, and support workflow | R03, H05 |

## Phase 8 — Deferred visual work

| ID | Size | Title | Depends on |
| --- | --- | --- | --- |
| V00 | XS | Install and verify canonical source-picture asset | owner reopens phase, H04–H06 |
| V01 | S | Forensic visual specification | V00 |
| V02 | S | Deterministic screenshot harness | V00, H03 |
| V03+ | S/M | Component-by-component parity sprints | V01, V02 |

No V sprint is active. Current workers must not inspect the source picture.
