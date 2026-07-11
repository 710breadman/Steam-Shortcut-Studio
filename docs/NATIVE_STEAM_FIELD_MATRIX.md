# Native Steam Field Safety Matrix

**Status:** Conservative draft  
**Rule:** Unknown ownership or rollback behavior means read-only.

| Field | Current support | Likely storage/ownership | Risk | Default policy | Requirements before write support |
|---|---|---|---|---|---|
| Custom artwork | Yes | Per-user Steam grid folder | Low to medium | Allowed with preview, backup, and restore | Validate images; group slot backups; verify copied files |
| Native game launch options | No | Steam local user configuration | High | Read-only | Identify authoritative file/API; preserve unknown data; fixture tests; rollback proof |
| Compatibility tool | Partial for managed non-Steam shortcuts | Steam `config.vdf` compatibility mapping | High | Manual/advanced only | Discover installed tools; read-back verification; atomic rollback; native-game fixtures |
| Hidden state | No | Steam local user data | High | Read-only | Determine exact owner and overwrite behavior; test across Steam restarts |
| Favorite state | No | Steam local user data | High | Read-only | Determine exact owner and overwrite behavior; test across Steam restarts |
| Collections/tags | Partial for non-Steam shortcuts | Shortcut tags and/or Steam local user data | High for native games | Non-Steam only | Native collection format research; preserve unrelated collections; rollback fixtures |
| Personal notes | Managed non-Steam only | Generated note files/current Steam note behavior | High for native games | Native read-only | Identify supported native note storage/API and conflict behavior |
| Custom display title | Non-Steam shortcut only | `shortcuts.vdf` AppName for non-Steam | High for native games | Native read-only | Confirm whether Steam supports persistent native custom names without corrupting identity |
| Artwork lock | App-owned future field | App persistence database | Low | Allowed | Stable library IDs and schema migration |
| Manual metadata notes | App-owned for managed entries | App persistence and generated outputs | Low | Allowed outside native Steam storage | Stable library IDs; separate user data from disposable cache |
| Launch target/start directory | Non-Steam shortcut only | `shortcuts.vdf` | High | Review required | Transaction plan; backup; read-back; launch test option; rollback |
| Shortcut overlay/desktop flags | Preserved, not actively edited | `shortcuts.vdf` | High | Preserve only | Field-specific research and explicit advanced UI before editing |

## Confirmed Safe Boundary

Native Steam game installation files are never modified.

The currently acceptable native Steam customization boundary is custom artwork in the per-user grid folder, because it is separate from installed game content and can be restored from file backups. Even this must move into the unified transaction system before bulk automatic use.

## Non-Steam Boundary

Managed non-Steam shortcuts may use:

- `shortcuts.vdf` AppName
- Executable path
- Start directory
- Launch options
- Tags
- Artwork
- Compatibility mapping
- Generated notes

These fields are not automatically safe. They still require preview, backup, verification, and rollback.

## Research Checklist Per Field

Before changing any field from read-only to writable, document:

1. Exact file, key, or supported API.
2. Whether data is per-user, per-machine, or cloud-synchronized.
3. Whether Steam must be closed.
4. Whether Steam rewrites the value.
5. Valid value format.
6. Unknown-field preservation strategy.
7. Cross-platform differences.
8. Fixture source and sanitization.
9. Read-back verification.
10. Rollback procedure.
11. Behavior after Steam restart.
12. Behavior after launching the game.

## Stop Condition

No field enters implementation merely because another application appears to edit it. The project needs repeatable evidence, a test fixture, and a reliable restore path.
