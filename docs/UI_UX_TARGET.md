# Steam Shortcut Studio UI/UX Target

## Approved Direction

The approved visual direction is based on the second mockup: a modern dark desktop application with cool blue accents, a compact command bar, a left navigation sidebar, a central game library table, and a right-side game inspector.

This document is the implementation reference. The goal is not to copy every pixel from a concept image. The goal is to preserve its information hierarchy, visual tone, safety cues, and efficient multi-game workflow.

## Design Principles

1. **Library first** — the game list is the main workspace.
2. **Safe by design** — backup, verification, and rollback status remain visible.
3. **Bulk actions are obvious** — selecting multiple games should reveal the actions that apply to them.
4. **Review exceptions, not everything** — strong matches move forward; uncertain matches become a focused queue.
5. **Dense but calm** — show useful information without making the screen noisy.
6. **Consistent themes** — retain accent-color options through shared design tokens.
7. **Keyboard friendly** — common scanning, selection, review, and artwork actions should not require excessive mouse travel.
8. **No fake safety** — never label an operation safe unless the underlying service has actually validated it.

## Main Window Structure

```text
┌──────────────────────────────────────────────────────────────────────┐
│ App identity | Scan | Refresh | Auto-Art | Preview | Apply Changes │
├───────────────┬──────────────────────────────┬───────────────────────┤
│               │ Search / Filters / Selection │ Selected Game Header  │
│ Left Sidebar  ├──────────────────────────────┼───────────────────────┤
│               │                              │ Tabs                  │
│               │ Library Table                │ Artwork / Details     │
│               │                              │ Metadata / Safety     │
│               │                              │ History               │
├───────────────┴──────────────────────────────┴───────────────────────┤
│ Status / Job Queue / Steam connection / pending changes             │
└──────────────────────────────────────────────────────────────────────┘
```

## Top Command Bar

### Required Actions

- `Scan`
- `Refresh Metadata`
- `Auto-Art`
- `Preview`
- `Apply Changes`

### Behavior

- Actions operate on selected games when selection exists.
- When nothing is selected, actions that support it may operate on the current filtered view only after explicit confirmation.
- `Apply Changes` must never bypass preview, backup, validation, or required review.
- Use a split-button or menu when an action has important modes.

### Example Auto-Art Menu

```text
Find Artwork for Selected
Find Missing Artwork for Selected
Reconsider Unlocked Artwork for Selected
Open Artwork Review Queue
```

## Left Sidebar

### Primary Navigation

- Library
- Shortcuts
- Artwork
- Metadata
- Tools
- Import / Scan
- Backups
- Settings

### Secondary or Later Navigation

- Extensions
- About

### Lower Sidebar Modules

- Theme/accent selector
- Steam library location and storage summary
- Steam connection state
- Active profile if profiles are implemented

### Rules

- The selected item needs a strong but not oversized highlight.
- Icons and text should align consistently.
- Counts should appear only when actionable, such as `Needs Review 12`.
- Do not use the sidebar as a status dump.

## Library Workspace

## Search and Filter Header

Required controls:

- Search field
- Source filter
- Steam/non-Steam filter
- Artwork-status filter
- Review-status filter
- Sort menu or sortable columns
- View options
- Selection menu

Useful saved filters:

- All Games
- Native Steam
- Non-Steam
- Missing Artwork
- Needs Review
- Existing Shortcuts
- Failed Jobs
- Manually Customized

## Library Table

Recommended columns:

- Selection checkbox
- Thumbnail
- Title
- Source
- Platform
- Steam state
- Artwork state
- Confidence
- Optional last played
- Optional size
- Row actions

### Row States

- Default
- Hovered
- Selected
- Active/current item
- Safe automatic result
- Needs review
- Failed
- Protected/manual lock
- Pending change
- Applied

### Selection Rules

- Checkbox selection must not conflict with opening a row.
- Click row: make it the active inspector item.
- Click checkbox: add/remove it from bulk selection.
- Shift-click: range selection.
- Ctrl-click on Windows: additive selection.
- Header checkbox: select all visible rows.
- Provide `Select all matching current filter` when results exceed the visible page.
- Show a persistent selection count.

## Contextual Bulk Action Bar

The bulk action bar appears when one or more games are selected.

Required actions:

- Scan Selected
- Refresh Metadata
- Find Artwork
- Preview Changes
- Apply Safe Changes
- More
- Clear Selection

The bar should show:

- Number selected
- Number eligible for the chosen action
- Number blocked or requiring review

### Find Artwork Bulk Dialog

Required options:

```text
Scope
- Missing slots only
- All unlocked slots
- Complete set only

Automation
- Auto-accept high-confidence matches
- Send uncertain matches to review
- Never replace manually locked artwork

Sources
- Official Steam assets
- SteamGridDB
- Enabled fallback providers

After search
- Open summary
- Open review queue when needed
```

## Right-Side Inspector

The right panel displays the active game. It does not represent the entire selected batch unless the UI clearly switches into a batch summary mode.

### Header

- Thumbnail
- Title
- Source
- Native Steam AppID or shortcut identity when relevant
- Installed state
- Confidence or review state
- Overflow menu

### Tabs

- Artwork
- Details
- Metadata
- Launch
- Compatibility
- Safety
- History

Tabs may be combined at narrow widths, but the information must remain accessible.

## Artwork Tab

Required slots:

- Portrait/Grid
- Wide Capsule
- Hero
- Logo
- Icon

Each slot card should show:

- Slot name
- Expected dimensions or ratio
- Current preview
- Proposed preview when different
- Source
- Confidence
- Lock status
- Validation state

Per-slot actions:

- Auto Match
- Review Matches
- Replace Art
- Import Local File
- Paste from Clipboard
- Lock/Unlock
- Clear Custom Slot
- Restore Previous

### Artwork Quality Rules Visible in UI

Show concise reasons such as:

- Exact Steam AppID match
- Exact external store ID match
- Title and release year match
- Edition conflict
- Low resolution
- Wrong aspect ratio
- Duplicate image
- Manual artwork locked
- Provider unavailable

## Details, Metadata, and Launch Tabs

### Details

- Original value
- Proposed value
- Edit control
- Source/evidence

### Metadata

- Title
- Release year/date
- Developer
- Publisher
- Genres
- Tags
- Notes
- External IDs

### Launch

- Launch target
- Arguments
- Working directory
- Source launcher
- Test launch where safe

### Compatibility

- Platform
- Compatibility tool
- Current value
- Proposed value
- Risk explanation

Launch and compatibility changes always require review.

## Safety and Backup Panel

A visible safety section should communicate real system state using three compact cards:

1. **Backup Created**
   - timestamp
   - files included
   - backup identifier

2. **Write Verification**
   - verification pending or passed
   - read-back result
   - hash or structural validation where appropriate

3. **Rollback Available**
   - restore-point identifier
   - restore action
   - last verified status

Do not use green success styling before the operation has actually succeeded.

## Job Queue and Progress

Long-running actions must not freeze the UI.

### Aggregate Status

Example:

```text
20 selected
12 completed
4 need review
1 skipped
2 failed
1 running
```

### Per-Game Status

- Queued
- Scanning
- Searching providers
- Validating images
- Selecting set
- Ready
- Needs review
- Failed
- Cancelled

### Required Controls

- Pause new work if supported
- Cancel remaining
- Retry failed
- Open review queue
- View details/log

## Review Queue

The review queue should be optimized for quick decisions.

### Layout

- Left: list of exceptions
- Center/right: selected item detail
- Before/after comparison
- Match evidence
- Accept
- Skip
- Search again
- Choose another candidate
- Lock manual choice

### Review Reasons

- Multiple game identities
- Conflicting edition
- Multiple launch targets
- Artwork set is incomplete
- Artwork slots resolve to different games
- Low-confidence result
- Existing manual art
- Native Steam setting change

## Theme System

Retain the existing color-choice concept, but implement it through semantic tokens.

### Suggested Accent Presets

- Deep Ocean Blue
- Orion Purple
- Forest Green
- Solar Amber
- Rose
- Nordic Ice
- Classic Gray

### Required Semantic Tokens

```text
background.app
background.sidebar
background.panel
background.panelRaised
background.input
border.default
border.focus
text.primary
text.secondary
text.muted
accent.primary
accent.hover
accent.pressed
status.success
status.warning
status.danger
status.info
status.protected
selection.background
selection.border
shadow.panel
```

### Rules

- Status colors must not change meaning between themes.
- Accent colors may change; warning/error/success semantics should remain recognizable.
- Text contrast must remain readable.
- Avoid excessive glow effects.

## Spacing and Shape Guidance

Suggested scale:

```text
4, 8, 12, 16, 20, 24, 32
```

Suggested corner radii:

```text
small controls: 6
buttons/inputs: 8
cards/panels: 10-12
large dialogs: 12-16
```

Use restrained borders and shadows. The design should feel layered, not outlined everywhere.

## Typography Guidance

- Use one primary UI family.
- Use size and weight to establish hierarchy before adding color.
- Avoid tiny text for important statuses.
- Keep table rows readable at normal Windows scaling.
- Test 100%, 125%, and 150% display scaling.

Suggested hierarchy:

```text
Window title: 18-20 semibold
Section title: 15-17 semibold
Body: 12-14 regular
Table: 12-13 regular
Caption: 10-12 regular
Status badge: 10-12 medium
```

## Animation and Motion

Use subtle motion only when supported cleanly by the toolkit.

Good uses:

- Progress transitions
- Panel open/close
- Selection feedback
- Job completion

Avoid:

- Constant pulsing
- Decorative motion that hides state
- Slow transitions that interfere with bulk work

## Accessibility and Input

- Full keyboard navigation for primary actions
- Visible focus states
- Tooltips for unfamiliar icons
- Text labels for important controls
- Do not rely only on color to show status
- Respect system scaling
- Avoid hover-only functionality

## Responsive Behavior

### Wide Window

- Sidebar visible
- Library table and inspector side by side
- Artwork slots arranged in a grid

### Medium Window

- Narrower sidebar
- Inspector remains visible
- Less-important table columns collapse or hide

### Small Window

- Sidebar may collapse to icons
- Inspector becomes a drawer or tabbed page
- Primary actions remain accessible

## Implementation Guidance

The current toolkit may limit exact visual fidelity. Codex should first evaluate whether the desired design can be achieved sustainably with the existing UI framework.

Acceptable paths:

1. Improve the current Tkinter/ttk implementation with a clear component and theme layer.
2. Adopt a maintained themed Tkinter-compatible library if it reduces custom widget code without harming packaging.
3. Plan a controlled UI-framework migration only if the existing toolkit blocks core requirements such as scalable tables, background job presentation, responsive layout, or reliable theming.

A framework migration must not be mixed casually into safety-critical Steam-write work. It requires its own decision record and migration sprint.

## Definition of Done for the UI Refresh

- The main screen follows the approved sidebar/table/inspector layout.
- Theme accent choices remain available.
- Multi-selection is easy to understand.
- `Find Artwork for Selected` is visible and functional.
- Long-running work is represented by a job queue.
- Safety, backup, verification, and rollback are visible.
- The interface remains usable at 100%, 125%, and 150% scaling.
- Keyboard navigation covers the primary workflow.
- Existing capabilities are not silently removed.
