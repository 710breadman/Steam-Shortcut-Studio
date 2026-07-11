# Sanitized Fixture Plan

## Purpose

Create repeatable test data for Steam-owned formats and library matching without committing personal account data, API keys, or real game paths.

## Rules

- Generate fixtures where possible instead of copying live files.
- Use fake Steam user IDs such as `123456789`.
- Use temporary paths such as `C:\TestGames\Example` or `/tmp/TestGames/Example`.
- Replace real game names when the identity is irrelevant to the test.
- Preserve only the structural fields needed to reproduce a format behavior.
- Document the origin and sanitization process for any captured fixture.
- Never commit authentication tokens, cookies, API keys, or personal notes.

## Fixture Directory

```text
tests/fixtures/
  README.md
  shortcuts/
  text_vdf/
  artwork/
  manifests/
  metadata/
```

## Binary `shortcuts.vdf` Fixtures

Create generated fixtures for:

1. Empty shortcut list
2. One normal shortcut
3. Multiple unrelated shortcuts
4. Shortcut with all currently supported fields
5. Unknown-but-preservable fields once parser support exists
6. Duplicate title with different executable paths
7. Same executable with changed title
8. Unicode title and path
9. Linux script/AppImage path
10. Truncated file
11. Unknown type marker
12. Missing root terminator
13. Large shortcut list

Expected assertions:

- Round-trip preservation
- Unrelated record preservation
- Deterministic ordering where required
- Clear parse failure
- No write on malformed input by default
- Backup and rollback behavior

## Text `config.vdf` Fixtures

Create generated fixtures for:

1. No compatibility mapping
2. Existing unrelated mappings
3. Existing selected AppID mapping
4. Valve key capitalization variants
5. Extra unknown branches
6. Unicode values
7. Malformed text VDF

Expected assertions:

- Only selected mapping changes
- Unrelated mappings and branches remain unchanged
- Read-back matches plan
- Malformed input aborts
- Restore reproduces original bytes/hash where practical

## Artwork Fixtures

Create small generated images with Pillow for:

- Valid PNG, JPEG, WebP, and ICO
- Portrait, landscape, hero-wide, logo-transparent, and square icon ratios
- Same image encoded in multiple formats
- Near-duplicate images
- Very small/low-quality image
- Oversized dimensions
- Truncated image
- HTML payload saved with image extension
- JSON error payload saved with image extension
- Wrong extension with valid image content

Expected assertions:

- Decode validation
- Dimension/aspect metadata
- Duplicate detection
- Slot policy decision
- Cache namespacing
- Full-set rollback after partial copy failure

## Library Identity Fixtures

Include identity cases for:

- Original and remake sharing a title
- Base game and DLC
- Standard and definitive/director's-cut editions
- Same title in different release years
- Acronym folder name versus full title
- Punctuation differences
- Regional title differences
- Executable codename unrelated to public title
- Existing shortcut executable differing from scanner's preferred candidate

## Launcher Manifest Fixtures

When adapters are implemented, generate or sanitize minimal manifests for:

- Epic Games Launcher
- GOG Galaxy
- Playnite
- EA App
- Ubisoft Connect
- Battle.net
- Heroic
- Lutris

Each fixture should include expected:

- External ID
- Title
- Install path
- Launch target or URI
- Platform
- Version/edition information where available

## Failure Injection

The transaction tests need controllable failure points:

- Backup failure
- Stage write failure
- Target replace failure
- Read-back parse failure
- Hash mismatch
- Artwork decode failure after copy
- Rollback restore failure
- Steam shutdown timeout

Use dependency injection or replaceable file-operation interfaces. Do not rely on changing real filesystem permissions in every test.

## Fixture README Format

Every non-generated fixture must document:

```text
Purpose:
Original source type:
Sanitization performed:
Fields intentionally retained:
Expected parser/result:
Safe to publish: yes/no
```

## Initial Implementation Order

1. Generate binary shortcut fixtures using the current serializer.
2. Add malformed byte fixtures.
3. Generate text VDF compatibility fixtures.
4. Generate artwork validation fixtures with Pillow.
5. Add launcher manifests as each adapter sprint begins.
