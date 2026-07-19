# Launcher Import Research

**Updated:** 2026-07-19

## Goal

Prefer launcher-owned installation metadata over recursive executable guessing. Folder scanning remains the fallback for portable games and unsupported launchers.

All adapters are read-only. They normalize source data into shared records and never modify launcher files or databases.

## Current and Planned Order

1. Epic Games Launcher — implemented
2. Native Steam — implemented
3. Loose/local folders — implemented
4. Playnite — next
5. GOG Galaxy
6. Battle.net
7. EA App
8. Ubisoft Connect
9. Amazon Games
10. itch.io
11. Rockstar Games Launcher
12. Microsoft Store / Xbox where safe and feasible
13. Heroic, Lutris, Legendary, Bottles, Faugus, `.desktop`, and Flatpak-aware sources after the Windows workflow is stable

## Shared Adapter Contract

Every source provides:

- Stable source-specific ID.
- Display title.
- Source name.
- External/store identity.
- Installation path.
- Launch target and arguments.
- Working directory.
- Platform.
- Version and size when available.
- Source-record path or equivalent evidence.
- Structured warnings and errors.

Adapters return normalized records, not raw launcher-specific objects.

## Capability Declaration

Each adapter should expose explicit capabilities so the controller and UI can disable unsupported actions without launcher-specific conditionals.

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

Capability absence is not an error. It means the related action is unavailable or requires review.

## Identity and Reconciliation Requirement

Adding a source must not create direct shortcut proposals before cross-source reconciliation runs.

Identity evidence priority:

1. Exact stable store or launcher ID.
2. Exact native Steam AppID relationship.
3. Exact existing managed-shortcut relationship.
4. Exact source launch identity.
5. Strong install-path/executable evidence.
6. Title, release year, developer, and edition evidence requiring conservative scoring.

Title alone never permits automatic merging.

## Epic Games Launcher

### Current implementation

The read-only adapter scans:

```text
%PROGRAMDATA%\Epic\EpicGamesLauncher\Data\Manifests\*.item
```

It uses catalog namespace and item ID as strong identity, maps install and launch data, skips incomplete or non-executable components, isolates malformed manifests, and flags suspicious launch targets for review.

Epic is the reference implementation for conservative source scans.

## Playnite — Next Adapter

Treat Playnite as a first-class optional curated source, not a dependency or replacement launcher.

### Preserve

- Playnite game ID.
- Source plugin and source game ID.
- Custom display name.
- Installation state.
- Installation directory.
- All launch actions.
- Emulator associations.
- Platform associations.
- User-selected executable and arguments.
- Existing metadata, tags, and artwork references where useful.

### Launch behavior

Store multiple launch recipes where available:

- Launch through Playnite.
- Launch through the original source launcher.
- Direct executable or script.
- Emulator action.

Never silently replace one recipe with another. Require an explicit preferred recipe.

### Research tasks

- Confirm installed and portable database locations.
- Determine the safest supported read path for current Playnite versions.
- Avoid locking or writing the live database.
- Create generated and anonymized fixtures.
- Define handling for uninstalled, hidden, emulated, and duplicate entries.
- Preserve user-curated names without treating them as exact cross-source identity.

## GOG Galaxy

Research the safest read-only source of installed-game identity and launch data.

Requirements:

- Open databases in read-only mode.
- Avoid taking persistent locks on the live database.
- Tolerate schema changes and unavailable Galaxy services.
- Preserve GOG product IDs.
- Distinguish Galaxy-managed and standalone installations.
- Store direct and Galaxy launch recipes when both are valid.

## Battle.net

Research before implementation:

- Stable product identity.
- Installed-version records.
- Launcher URI or product code.
- Direct executable reliability.
- Update, repair, and relocation behavior.
- PTR, beta, classic, and region variants.
- Multiple installations.
- Launch arguments.
- Behavior when Battle.net is moved or reinstalled.

Default to launcher-based launch unless direct execution is proven reliable for that title. Preserve both recipes when appropriate.

## EA App and Ubisoft Connect

For each launcher, document:

- Manifest/database ownership.
- Locking behavior.
- Stable external identity.
- Installation state.
- Launch protocol.
- Direct executable reliability.
- Update and repair behavior.
- Multiple editions and subscriptions.

No adapter should depend on credentials, scrape private account data, or modify launcher storage.

## Monitoring

Source monitoring is a later layer above adapters.

- Watch only documented directories or records.
- Debounce repeated launcher writes.
- Convert changes into a review summary.
- Never write Steam automatically merely because a launcher manifest changed.
- A partial or unavailable scan never marks prior games missing.

## Testing Requirements

Every adapter needs fixtures for:

- Normal installed game.
- Missing install path.
- Missing or suspicious launch target.
- Multiple launch actions.
- Duplicate external IDs.
- Malformed record isolation.
- Partial/unavailable source behavior.
- Missing/reappearing persistence.
- Platform or edition variants.
- Stable IDs across rescans.
- No source-file modifications.
