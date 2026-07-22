# Reference Project Catalog

Research date: 2026-07-22. Activity means a recent repository commit was observed during this audit; it is not a maintenance guarantee.

| Project | Purpose | Activity observed | License | Useful lessons | Recommendation |
| --- | --- | --- | --- | --- | --- |
| Steam ROM Manager | Bulk parser-driven shortcut and artwork import | Active | GPL-3.0 | parser presets, preview, artwork filters, configuration import/export, broad platforms | Study; do not copy code into a differently licensed project without review |
| Steam Art Manager | Steam artwork browser/editor | Release 3.16.1 observed June 2026 | GPL-3.0; selected parsers LGPL-2.1 | staged in-memory choices, import/export, unused-grid cleanup, cross-platform packaging | Study workflow; parser reuse only after boundary/license review |
| BoilR | Import games from launchers into Steam | Commit observed February 2026 | zlib | launcher breadth, backups, lightweight Rust/egui approach | Study adapter behavior and backup UX |
| Playnite | Full game-library manager | Version 10.56 bump observed May 2026 | MIT | source plugins, normalized game model, filters, metadata, large-library UX | Study and add read-only Playnite import; do not turn SSS into a launcher replacement |
| SGDBoop | Apply SteamGridDB assets through a URL protocol | Active commit observed | zlib | external artwork handoff and small integration surface | Adapt protocol integration only if it improves review flow |

## Project-specific conclusions

### Steam ROM Manager

Useful evidence from open issues:

- Users want robust backup/restore.
- Large scraping jobs can lose provider connection.
- Artwork filters by type, platform, language, and author/style reduce manual work.
- Custom Steam executable paths matter.
- Linux `.ico` handling needs automatic PNG extraction.
- Programmatic configuration and safe partial import are valuable.

Its GPL license makes direct code adoption a deliberate legal/product decision. Algorithms and user problems can be studied independently.

### Steam Art Manager

The strongest reusable idea is a clear staged-artwork workflow: browse or upload, hold choices in memory, then apply. Import/export and dead-grid cleanup are valuable later. Its Tauri stack is not a reason to rewrite SSS.

### BoilR

BoilR proves demand for launcher import and backup. SSS should study supported sources and launch recipes while retaining its stronger app-owned persistence and verified transaction model.

### Playnite

Playnite is both a reference and a source. A read-only adapter can import installed-game and launch metadata while keeping SSS focused on Steam preparation rather than becoming another launcher.

## Adoption rule

No external dependency or copied code is approved by this catalog. Each candidate needs maintenance, security, packaging, data-flow, and license review in its own sprint.
