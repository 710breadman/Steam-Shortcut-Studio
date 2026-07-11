# Artwork Match Policy

**Status:** Initial policy for implementation and fixture testing  
**Purpose:** Prevent incorrect or low-quality artwork from being applied silently during bulk operations.

## Core Rule

Automatic artwork application requires strong evidence of the correct game identity, valid image files, and a coherent set. Anything uncertain goes to review. Invalid or clearly unrelated content is rejected.

## Result States

Every selected game must finish in exactly one state:

- `Artwork Applied`
- `Needs Review`
- `No Good Match`
- `Skipped`
- `Failed`
- `Cancelled`

The internal policy decisions are:

- `auto_accept`
- `review`
- `reject`

## Evidence Model

Each decision should record:

- Library item ID
- Display title
- Source identity and external IDs
- Search terms used
- Provider
- Candidate ID and URL
- Artwork slot
- Image format, dimensions, aspect ratio, and file size
- Successful image decode result
- Identity score
- Set-coherence score
- Release year comparison
- Edition/DLC/remaster comparison
- Manual lock state
- Decision
- Human-readable reasons

## Identity Priority

Use evidence in this order:

1. Exact provider/store external ID
2. Launcher manifest identity
3. Exact normalized title plus compatible release year
4. Exact normalized title without year conflict
5. Executable product name or file metadata
6. Folder title
7. Fuzzy title match

A fuzzy title match alone must never auto-apply artwork.

## Initial Thresholds

The first implementation uses conservative defaults:

```text
Automatic identity threshold: 92 / 100
Automatic set-coherence threshold: 85 / 100
Reject identity below: 45 / 100
Complete set required for automatic acceptance: yes
```

These values must be tuned with sanitized fixtures rather than changed to make a small sample pass.

## Automatic Acceptance Requirements

All of the following must be true:

- Candidate decodes as a valid supported image.
- Candidate identity score meets the automatic threshold.
- Candidate set-coherence score meets the automatic threshold.
- No conflicting release year.
- No conflicting edition, sequel, DLC, remaster, or remake.
- Artwork is not manually locked.
- The required set is complete for the selected bulk mode.
- No provider or download error occurred.

## Review Conditions

Send to review when any of these are true:

- Identity is plausible but below the automatic threshold.
- Artwork set is incomplete.
- Multiple candidates are close in score.
- Release year is unknown.
- Edition name is ambiguous.
- One slot appears to belong to a different edition.
- Manual artwork is locked.
- Existing artwork would be replaced.
- Provider result lacks enough identity information.
- Aspect ratio requires a crop or composition decision.

## Rejection Conditions

Reject when any of these are true:

- Content is empty or cannot be decoded.
- Response is HTML, JSON error text, or another non-image payload.
- Identity score is below the rejection threshold.
- Candidate clearly belongs to another game.
- Dimensions are unusable for the target slot and no safe transformation exists.
- File is unreasonably large or exceeds configured safety limits.
- Candidate has a known provider/content-policy failure.

## Manual Artwork Protection

- Manual artwork selections must be persisted separately from disposable cache.
- Bulk search may discover alternatives for locked slots, but must not replace them automatically.
- `All unlocked slots` must be the default bulk replacement mode.
- Replacing a locked slot requires an explicit override action.
- Clearing a lock and replacing artwork should appear as two separate proposed changes.

## Bulk Modes

### Missing slots only

- Search only empty slots.
- Never replace existing artwork.
- Recommended default for first-time bulk use.

### All unlocked slots

- Search empty slots and replace unlocked existing assets when policy permits.
- Preserve every manual lock.

### Complete set only

- Apply nothing unless a coherent required set is available.
- Incomplete sets go to review.

## Set Coherence

A coherent set should share:

- Correct game identity
- Compatible edition
- Compatible branding/logo treatment
- Similar visual era/style where practical
- Slot-appropriate dimensions and composition

It is acceptable to use different providers for different slots only when identity is certain and the set still appears coherent.

## Slot Validation Targets

These are guidance ranges, not hard provider requirements:

- Portrait/grid: portrait orientation, commonly near 2:3
- Wide capsule: landscape orientation
- Hero: very wide landscape composition
- Logo: transparent background preferred
- Icon: square, small-size readable

The app should record actual dimensions rather than trusting provider labels.

## Cache Rules

Cache keys should include:

```text
provider / library-item-id / external-id / slot / candidate-id-or-url-hash
```

Do not key only by title. Title-only cache keys can mix editions and games with identical names.

## Policy Code

The initial UI-independent implementation is in:

```text
steam_shortcut_studio/artwork_policy.py
```

The code is intentionally not wired into the current UI yet. Integration belongs in the bulk artwork sprints after the job queue and stable library IDs exist.

## Fixture Plan

Build fixtures for at least:

- Same title, different release years
- Original versus remake/remaster
- Base game versus DLC
- Standard versus definitive/director's-cut edition
- Regional title differences
- Acronym folder names
- Games with punctuation differences
- Games sharing generic words
- Missing logos or icons
- Invalid HTML/image responses
- Manual locks
- Partial provider outages

## Stop Condition

If the system cannot explain why a candidate is the correct game and edition, it must not auto-apply it.
