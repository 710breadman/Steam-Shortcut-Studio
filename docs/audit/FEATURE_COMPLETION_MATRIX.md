# Feature Completion Matrix

Percentages estimate accepted production readiness, not lines of code. A subsystem loses credit for missing integration, runtime proof, recovery, packaging, or user workflow even when its backend exists.

| Subsystem | Estimate | Status | Evidence | Main remaining work |
| --- | ---: | --- | --- | --- |
| Shortcut write safety | 88% | Production foundation complete | strict parse, stage, verify, rollback | real-profile failure injection and user acceptance |
| Artwork write safety | 86% | Production foundation complete | decode/hash validation, grouped rollback | full UI apply/restore acceptance |
| Persistent library v1 | 72% | Backend complete | SQLite records, overrides, notes, locks, rejects, scans | migrations, identity, recipes, richer state |
| Steam detection/profiles | 68% | Partially integrated | root/profile detection and restart handling | explicit profile targeting everywhere |
| Steam source scan | 75% | Backend complete | native app scan and persistence | fixtures, state model, final workflow |
| Existing shortcut import | 76% | Backend complete | parse, merge, preserve fields | identity clustering and review |
| Epic adapter | 72% | Backend complete | `.item` parsing, issues, persistence | real-machine fixture matrix |
| Local-folder scan | 68% | Backend complete | ranking and persistence | moved installs, portable recipes, review UX |
| Other launcher sources | 10% | Planned | priority decisions only | Playnite, GOG, Battle.net gates |
| Selection model | 83% | Foundation complete | stable IDs, ranges, scopes | stress and accessibility acceptance |
| Background jobs | 80% | Foundation complete | bounded workers, events, retry, cancel | shutdown and heavy-load acceptance |
| Metadata search | 66% | Partially integrated | service factory/provider boundary | cache/error policy and final review UX |
| Artwork search/policy | 76% | Backend mostly complete | provider service, policy, coordinator | production review/apply flow |
| Artwork review UI | 55% | Partially integrated | workspace mapping and actions | coherent queue, previews, bulk exceptions |
| Identity/reconciliation | 15% | Planned/foundation only | issues #37/#38 | complete domain and persistence implementation |
| Launch recipes | 20% | Planned | current single target/args fields | multiple recipes and preference policy |
| Notes | 45% | Partial | app-owned text notes | structured fields and optional Steam summary |
| Preview/apply UX | 62% | Partial | safe transaction services and existing UI actions | one coherent plan, explicit profile, review gate |
| Transaction history | 68% | Partial | manifests, view/controller | Windows CI fix, restore action, filtering |
| Restore/recovery UX | 48% | Partial | backups and rollback internals | user-directed restore and failure guidance |
| Production UI architecture | 60% | Partial | controller-backed library and modern shell | reduce `ui.py`, state-driven workspaces |
| Performance/scaling | 30% | Present but unverified | no accepted benchmark report | deterministic 100/1k/5k harness |
| Accessibility/input | 32% | Partial | some keyboard/multi-select behavior | focus, scaling, contrast, screen-reader review |
| Windows packaging | 35% | Partial | PyInstaller spec and workflow | clean install, update, uninstall, diagnostics |
| Linux packaging | 25% | Planned/partial | desktop entry and CI imports | real package and launch acceptance |
| CI/test reliability | 68% | Broken on Windows | broad suites; current Windows failures | fix failures and publish baseline manifest |
| Documentation/handoff | 70% | Being consolidated | architecture and roadmap history | remove contradictions and maintain handoff |
| Visual parity | Deferred | Intentionally deferred | owner direction | begin only after non-visual acceptance |

## Overall interpretation

Do not average this table into one project percentage. The safety core is mature, while release delivery, identity, reconciliation, workflow integration, and verified packaging remain substantial.
