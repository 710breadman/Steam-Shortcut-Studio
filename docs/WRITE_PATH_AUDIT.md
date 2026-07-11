# Write Path Audit

**Audit date:** 2026-07-11  
**Rule:** Game installation files must never be modified.

## Summary

The application currently writes four categories of data:

1. Non-Steam shortcut records
2. Steam grid artwork files
3. Steam Play compatibility mappings
4. Application settings, cache, logs, and generated notes

The first three affect Steam-owned locations and must eventually be coordinated through one transaction service.

## 1. Non-Steam Shortcuts

### Target

```text
<Steam>/userdata/<user-id>/config/shortcuts.vdf
```

### Code

- `steam_shortcut_studio/steam_shortcuts.py`
  - `create_backup`
  - `load_shortcuts_for_write`
  - `write_shortcuts_file`
  - `upsert_games`

### Current safeguards

- Native Steam games are excluded from shortcut creation.
- Existing records are matched by executable or title.
- User-managed fields are preserved when updating.
- Existing files are timestamp-backed up.
- Writes use a temporary file followed by replacement.
- The file is read back after writing.
- Expected games must be found after read-back.

### Current critical risk

If the existing file cannot be parsed, the application backs it up and replaces it with a fresh file containing only newly selected entries. This avoids blocking the user, but it can leave unrelated existing shortcuts absent from the active file.

### Required transaction behavior

- Malformed input must produce an explicit recovery plan.
- Default action should be abort and preserve the active file.
- A recovery action must clearly state that a fresh file will omit unparsed records.
- Failed read-back verification must restore the backup automatically.
- The transaction record must include original hash, backup path, written hash, and verification result.

## 2. Steam Grid Artwork

### Target

```text
<Steam>/userdata/<user-id>/config/grid/
```

### Code

- `steam_shortcut_studio/artwork.py`
  - `_backup_existing`
  - `_replace_artwork_file`
  - `copy_game_artwork_to_steam`
  - `copy_all_artwork_to_steam`

### Files used

- Portrait/grid: `<appid>p.<ext>`
- Wide capsule: `<appid>.<ext>`
- Hero: `<appid>_hero.<ext>`
- Logo: `<appid>_logo.<ext>`
- Icon: `<appid>_icon.<ext>`

### Current safeguards

- Existing variants are backed up before replacement.
- Native Steam artwork is allowed without creating a shortcut.
- Source and target equality is checked.
- Only known artwork extensions are considered.

### Current risks

- Artwork files are copied individually, not as a single atomic set.
- A partial failure can leave a mixed old/new set.
- Existing backups are not yet grouped into one restore point.
- Download validation does not yet require successful image decoding.
- Slot fallbacks may reuse one image across incompatible aspect ratios.

### Required transaction behavior

- Stage the complete proposed set outside the Steam grid directory.
- Validate every staged image.
- Record every existing target and backup.
- Apply the set only after all required assets are ready.
- Verify hashes and image readability after copy.
- Restore the full previous set if a required copy fails.

## 3. Steam Play Compatibility Mapping

### Target

```text
<Steam>/config/config.vdf
```

### Code

- `steam_shortcut_studio/steam_compat.py`
  - `_load_config`
  - `_write_config`
  - `write_compat_tool_mappings`

### Current safeguards

- Existing file is parsed before editing.
- Existing file is backed up if a change is needed.
- Writes use a temporary text file followed by replacement.
- Only the `CompatToolMapping` subtree is intended to change.

### Current risks

- No read-back verification is performed after writing.
- No automatic restore occurs if the written file is malformed.
- Compatibility writes are separate from shortcut creation, even though they may depend on the new shortcut AppID.
- The current tool list is hardcoded and may not match locally installed compatibility tools.

### Required transaction behavior

- Discover available tools from local Steam data where possible.
- Include shortcut creation and compatibility mapping in the same plan.
- Read back the mapping after write.
- Restore the backup automatically on parse or verification failure.
- Treat native Steam compatibility changes as advanced/manual until field ownership is fully documented.

## 4. Generated Notes

### Targets

Application-generated note files associated with managed non-Steam entries.

### Code

- `steam_shortcut_studio/steam_notes.py`

### Current safeguards

- Native Steam games are explicitly excluded.
- User-edited note text is preserved.
- Generated note sections are marked.

### Required behavior

- Include note writes in preview and history.
- Avoid deleting unrelated note content.
- Restore prior generated content on transaction rollback.

## 5. Settings and Cache

### Targets

```text
Windows:
%APPDATA%/SteamShortcutStudio/
%LOCALAPPDATA%/SteamShortcutStudio/cache/

Linux:
~/.config/SteamShortcutStudio/
~/.cache/SteamShortcutStudio/cache/
```

### Code

- `settings_store.py`
- `ui.py` logging configuration
- artwork and metadata cache helpers

### Current safeguards

- API keys and generated state are kept out of source control.
- Artwork cleanup is scoped to artwork cache paths.
- Settings reset rewrites defaults.

### Required improvements

- Version every persistent schema.
- Store manual locks and rejected matches separately from disposable cache.
- Never delete user-imported artwork during cache cleanup.
- Add exportable diagnostics that redact API keys and personal paths where requested.

## Steam Process Control

### Code

- `steam_detection.py`
  - Steam running detection
  - shutdown for write
  - reopen after write

### Required transaction behavior

- Record whether Steam was running before the operation.
- Close Steam only after the user approves a plan requiring closure.
- Reopen Steam only if the app closed it.
- Restore files before reopening Steam if verification fails.
- Do not claim that Steam is closed solely because a shutdown command was sent.

## Transaction Service Requirements

Every Steam-affecting operation must eventually use one service with these stages:

```text
DISCOVER -> PLAN -> VALIDATE -> BACKUP -> APPLY -> READ BACK -> VERIFY -> COMMIT
                                                        \-> ROLLBACK
```

Each transaction record should contain:

- Unique transaction ID
- Timestamp
- Steam profile/user ID
- Requested game IDs
- Planned files and fields
- Risk classification
- Backup paths
- Original and written hashes
- Apply result
- Verification result
- Rollback result
- Error details

## Stop Conditions

Stop implementation and leave a field read-only when:

- Ownership of the field is uncertain.
- Unknown data cannot be preserved.
- A valid value cannot be verified.
- A reliable rollback cannot be demonstrated.
- Steam may rewrite the field and the behavior is not understood.
