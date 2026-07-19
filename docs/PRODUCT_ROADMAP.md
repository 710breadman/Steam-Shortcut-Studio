# Steam Shortcut Studio — Product Roadmap

**Updated:** 2026-07-19  
**Scope:** future work only. See `CURRENT_STATE.md` for completed capabilities.

## North Star

A user can scan a personal PC-game library, reconcile the same game across sources, choose the preferred launch method, review only uncertain results, and safely apply approved shortcuts, artwork, notes, and organization changes to the intended Steam profile.

Steam Shortcut Studio remains a library workshop, not a replacement launcher.

## Permanent Safety Rules

1. Never modify installed game files.
2. Never infer duplicate identity from title alone.
3. Never silently change the preferred launch recipe.
4. Never write to every Steam profile by default.
5. Never overwrite manual artwork, notes, collections, tags, or launch choices.
6. Automatic monitoring may detect changes; Steam writes require preview and approval by default.
7. Every Steam-owned write uses backup, staged validation, read-back verification, and rollback.
8. Unsupported or poorly understood Steam fields remain read-only.
9. Launcher adapters remain read-only.
10. Preserve unknown source and Steam data whenever possible.

# P0 — Release Baseline and Architecture Decisions

## P0.1 Planning and Handoff Reset

- Keep `CURRENT_STATE.md` factual and concise.
- Keep this roadmap future-only.
- Use small GitHub issues for implementation.
- Treat `SPRINT_STATUS.md` and older sprint documents as historical evidence, not the active backlog.
- Keep `CODEX_START_HERE.md` short and action-oriented.

### Exit criteria

- A new development session can identify the current state, active issue, safety boundaries, and required tests without reading a long historical diary.

## P0.2 Installable Windows Alpha

Create a dependable Windows build for personal testing.

Deliverables:

- Installer and portable ZIP evaluation.
- App icon, version metadata, and uninstaller behavior.
- Per-user settings and cache preservation across upgrades.
- Clear first-run setup.
- Diagnostics export.
- Signed-build plan, even if initial alpha builds remain unsigned.
- Release checklist and rollback instructions.

### Exit criteria

- A clean Windows machine can install or run the alpha, scan a test library, preview changes, apply a safe shortcut transaction, and uninstall without reading source code.

## P0.3 PySide6 Proof of Concept

Keep the current production UI operational while building one isolated PySide6 library workspace using real controller data.

Required proof:

- 100, 1,000, and 5,000 generated rows.
- Thumbnail, title, source, platform, source state, Steam state, Studio state, artwork state, confidence, and row actions.
- Search, sorting, grouping, saved filters, and stable multi-selection.
- Right-side inspector with artwork slot cards.
- Context menus, keyboard navigation, drag-and-drop, and queue progress.
- Windows scaling at 100%, 125%, and 150%.
- Basic Linux/Bazzite launch test.
- Packaged startup time and distribution-size comparison.
- Clear code-complexity comparison against the current production table.

### Decision gate

Migrate only if the proof is materially better in responsiveness, interaction quality, scaling, maintainability, and packaging. Keep the Python core in either outcome.

## P0.4 Library Performance Baseline

Measure the current and proof interfaces under representative loads.

Record:

- Initial load time.
- Search/filter latency.
- Sort latency.
- Selection latency.
- Thumbnail memory use.
- Background event throughput.
- Startup time.
- Packaged size.

### Exit criteria

- Results are reproducible and stored in a short benchmark report.
- The UI decision uses measured evidence instead of appearance alone.

## P0.5 Identity and Reconciliation Foundation

Create a first-class cross-source identity system before adding many more launchers.

Deliverables:

- `GameIdentityCluster` or equivalent domain model.
- Exact external/store identifier links.
- Native Steam AppID relationships.
- Existing shortcut target relationships.
- Install-path and executable evidence.
- Conservative title/year/developer fallback scoring.
- Edition and platform conflict detection.
- Preferred installed copy.
- Preferred launch recipe.
- Decisions: merge, keep separate, ignore, and remember.
- Detection of duplicate shortcuts and missing targets.
- Previewable reconciliation changes.

### Exit criteria

- Scanning the same title from Steam, Epic, Playnite, folders, or existing shortcuts cannot silently create duplicate shortcut proposals.
- Title-only matches always require review.

# P1 — Core Daily Workflow

## P1.1 Explicit Library States

Represent three independent state groups:

```text
Source state: installed / missing / unavailable / unknown
Steam state: native / existing shortcut / not added / duplicate
Studio state: managed / unmanaged / review / pending / failed
```

Build smart views:

- All Games
- Native Steam
- Existing Non-Steam
- Managed by Studio
- Detected — Not Added
- Ready to Add
- Missing or Uninstalled
- Duplicate or Conflicting
- Needs Launch Review
- Missing Artwork
- Needs Artwork Review
- Manually Customized
- Failed Jobs

Support user-created saved filters.

## P1.2 Contextual Quick Actions

Add consistent row and selection actions:

- Test launch.
- Open install folder.
- Open source record when safe.
- Copy launch command.
- Add selected to Steam.
- Remove a Studio-managed shortcut.
- Restore previous state.
- Rescan parent source.
- Ignore executable permanently.
- Explain launch-candidate selection.
- Choose preferred launch recipe.

## P1.3 Windows Explorer Quick Add

### Stage 1

Register a per-user `.exe` context-menu command:

```text
Add to Steam with Shortcut Studio
```

It invokes a compact review wizard rather than writing immediately.

Wizard fields:

- Detected title.
- Alternative executables.
- Duplicate/identity warning.
- Direct and launcher launch recipes.
- Working directory and arguments.
- Artwork match summary.
- Target Steam profile.
- Preview and Apply.

### Stage 2

Evaluate a Windows 11 native context-menu integration. Keep scanning and network work outside Explorer's process.

## P1.4 Structured Notes

Replace the single conceptual notes surface with structured app-owned sections:

- Personal notes.
- Launch instructions.
- Compatibility notes.
- Controller notes.
- Mods and patches.
- Troubleshooting.
- Source/import evidence.
- Links.
- Automatic metadata summary.

Allow an optional short, previewed Steam summary. Detailed notes remain app-owned.

## P1.5 Multiple Launch Recipes

A library identity may retain multiple launch methods:

- Direct executable.
- Source launcher protocol or command.
- Playnite action.
- Mod manager.
- Compatibility wrapper.
- Custom script.
- Remote-play target.

Each recipe stores target, arguments, working directory, environment, source, platform, evidence, and last test result. One recipe is explicitly preferred per installation/profile context.

## P1.6 Steam Profile Targeting

- Detect available Steam profiles.
- Require an explicit default or per-operation target.
- Support selected multiple profiles only when intentionally chosen.
- Show the target profile in Preview and Apply.
- Never default to all profiles.

## P1.7 Collections Backup and Restore

Before collection editing:

- Identify ownership and storage format.
- Back up collection state.
- Preview changes.
- Verify writes.
- Restore previous state.

Later optional management may create or update collections from sources, tags, and saved rules. Existing manual collections remain protected by default.

# P2 — Windows Launcher Sources

Every source implements the shared read-only adapter model, stable identity, capability declaration, and structured diagnostics.

## Adapter capabilities

```text
supports_installed_games
supports_owned_uninstalled_games
supports_direct_launch
supports_launcher_launch
supports_launch_arguments
supports_artwork_identity
supports_version
supports_install_monitoring
supports_uninstall_detection
supports_multiple_installations
supports_platform_variants
```

Unsupported actions are disabled through capabilities rather than launcher-specific UI conditionals.

## Priority order

1. Playnite
2. GOG Galaxy
3. Battle.net
4. EA App
5. Ubisoft Connect
6. Amazon Games
7. itch.io
8. Rockstar Games Launcher
9. Microsoft Store / Xbox where safe and feasible

## Playnite requirements

Treat Playnite as an optional, user-curated source.

Preserve:

- Playnite game ID.
- Custom title.
- Installation state.
- Launch actions.
- Emulator associations.
- Source plugin identity.
- Existing metadata and artwork references where useful.

Offer both `Launch through Playnite` and imported direct/source-launch recipes when available.

## Battle.net requirements

Research and fixture-test:

- Stable product identity.
- Installed-state records.
- Product/launcher URI.
- Direct executable reliability.
- Update and repair behavior.
- PTR, beta, and region variants.
- Multiple installations.
- Launcher movement and repair effects.

Prefer launcher-based launch until direct execution is proven reliable for the title.

# P3 — Artwork and Portability

## Artwork Workspace Completion

- Per-game and bulk artwork search.
- Missing-any-slot and per-slot filters.
- Steam AppID and external-ID lookup.
- Official Steam assets as fallback.
- Local file, clipboard, drag-and-drop, and URL import.
- Provider, creator, dimension, aspect-ratio, and animation preferences.
- Complete-set coherence scoring.
- Before/after comparison for all five slots.
- Export/import artwork packs.
- Restore original/native art.
- Copy art between Steam profiles.
- Permanent candidate rejection.

## Portable Managed-Library Bundle

Export and preview-import:

- Library records.
- Identity decisions.
- Manual overrides.
- Structured notes and tags.
- Launch recipes.
- Artwork and locks.
- Rejected candidates.
- Collections backups.
- Transaction references.

Support path remapping between computers and PC/Steam Deck environments. Import reconciles rather than blindly duplicating.

# P4 — Monitoring and Automation

After reconciliation is dependable:

- Watch configured folders and launcher records.
- Detect new, removed, moved, and changed games.
- Show a review summary instead of writing automatically.
- Add CLI scan, preview, apply, export, import, and restore commands.
- Support scheduled quiet scans.
- Retry transient provider failures.
- Notify only when action is useful.

Default policy:

- Detection may run automatically.
- Steam-owned changes require explicit preview and approval.

# P5 — Later Expansion

## Owned but Uninstalled

Add a separate read-only view after installed-library workflows stabilize. Do not mix uninstalled ownership with installed launch readiness.

## SteamOS and Bazzite

After the Windows alpha and core workflow are stable:

1. Heroic
2. Lutris
3. Legendary
4. Bottles
5. Faugus Launcher
6. `.desktop` and Flatpak-aware sources

Include compatibility recipes, removable-storage state, native Linux versus Proton distinctions, and automatic icon conversion where required.

## Optional Deck Companion

Evaluate a small Decky companion for:

- Opening pending review work.
- Applying already reviewed changes.
- Refreshing sources.
- Managing artwork in Game Mode.

## Plugin API

Do not publish a public plugin API until source capabilities, data migrations, and reconciliation contracts are stable. Later extension points may include:

- Source adapters.
- Metadata providers.
- Artwork providers.
- Exporters.
- Launch-recipe enrichers.

# Success Metrics

- Correct cross-source identity rate.
- Silent duplicate proposal rate: target zero.
- Manual launch choices later overwritten: target zero.
- Manual artwork choices later overwritten: target zero.
- Wrong-profile writes: target zero.
- Percentage of selected games processed without manual intervention.
- False-positive automatic artwork rate.
- Median time to review a batch of 20 games.
- Write-verification success rate.
- Rollback success rate.
- Search/filter latency at 5,000 rows.
- Number of Steam-write paths outside transaction services: target zero.
