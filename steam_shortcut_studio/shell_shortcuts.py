"""Keyboard bindings for the modern shell's primary workflow.

`docs/UI_UX_TARGET.md` requires that "keyboard navigation covers the primary
workflow" and that common scanning, selection, review, and artwork actions not
need excessive mouse travel.

The table lives here, apart from the widgets, for two reasons: the set of
bindings is worth testing without constructing a window, and the same table
drives both the `bind_all` calls and the reference shown to the user. A
shortcut that exists but is undiscoverable helps nobody, and one documented but
never bound is worse.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ShellShortcut:
    action: str
    sequences: tuple[str, ...]
    label: str
    description: str
    group: str

    @property
    def display(self) -> str:
        """The accelerator to show a user, from the first bound sequence."""
        return format_sequence(self.sequences[0])


def format_sequence(sequence: str) -> str:
    text = sequence.strip("<>")
    parts = [part for part in text.split("-") if part]
    names = {
        "Control": "Ctrl",
        "Shift": "Shift",
        "Alt": "Alt",
        "Return": "Enter",
        "Escape": "Esc",
        "space": "Space",
        "Prior": "Page Up",
        "Next": "Page Down",
        "slash": "/",
    }
    return "+".join(names.get(part, part.title() if len(part) > 1 else part.upper()) for part in parts)


SHELL_SHORTCUTS: tuple[ShellShortcut, ...] = (
    ShellShortcut(
        action="focus_search",
        sequences=("<Control-f>", "<Control-F>"),
        label="Search",
        description="Jump to the library search box",
        group="Navigate",
    ),
    ShellShortcut(
        action="select_all",
        sequences=("<Control-a>", "<Control-A>"),
        label="Select all",
        description="Select every game in the current view",
        group="Select",
    ),
    ShellShortcut(
        action="clear_selection",
        sequences=("<Escape>",),
        label="Clear selection",
        description="Clear the selection, or the search when nothing is selected",
        group="Select",
    ),
    ShellShortcut(
        action="toggle_active",
        sequences=("<space>",),
        label="Toggle game",
        description="Select or deselect the game in the inspector",
        group="Select",
    ),
    ShellShortcut(
        action="move_up",
        sequences=("<Up>",),
        label="Previous game",
        description="Inspect the game above",
        group="Navigate",
    ),
    ShellShortcut(
        action="move_down",
        sequences=("<Down>",),
        label="Next game",
        description="Inspect the game below",
        group="Navigate",
    ),
    ShellShortcut(
        action="refresh",
        sequences=("<F5>",),
        label="Refresh",
        description="Reload the library from disk",
        group="Library",
    ),
    ShellShortcut(
        action="scan",
        sequences=("<Control-n>", "<Control-N>"),
        label="Import / Scan",
        description="Open the scan screen",
        group="Library",
    ),
    ShellShortcut(
        action="auto_art",
        sequences=("<Control-Shift-A>",),
        label="Auto-Art",
        description="Find artwork for the selected games",
        group="Artwork",
    ),
    ShellShortcut(
        action="review_queue",
        sequences=("<Control-r>", "<Control-R>"),
        label="Review queue",
        description="Open the artwork review queue",
        group="Artwork",
    ),
    ShellShortcut(
        action="preview",
        sequences=("<Control-p>", "<Control-P>"),
        label="Preview",
        description="Preview what Apply Changes would write",
        group="Apply",
    ),
    ShellShortcut(
        action="apply",
        sequences=("<Control-Return>",),
        label="Apply Changes",
        description="Write shortcuts and artwork to Steam",
        group="Apply",
    ),
)


def shortcut_for(action: str) -> ShellShortcut:
    for shortcut in SHELL_SHORTCUTS:
        if shortcut.action == action:
            return shortcut
    raise KeyError(action)


def accelerator(action: str) -> str:
    return shortcut_for(action).display


def shortcut_groups() -> tuple[tuple[str, tuple[ShellShortcut, ...]], ...]:
    """Shortcuts grouped for display, preserving declaration order."""
    order: list[str] = []
    grouped: dict[str, list[ShellShortcut]] = {}
    for shortcut in SHELL_SHORTCUTS:
        if shortcut.group not in grouped:
            grouped[shortcut.group] = []
            order.append(shortcut.group)
        grouped[shortcut.group].append(shortcut)
    return tuple((group, tuple(grouped[group])) for group in order)


def shortcut_reference_text() -> str:
    lines: list[str] = []
    for group, shortcuts in shortcut_groups():
        lines.append(group.upper())
        width = max(len(shortcut.display) for shortcut in shortcuts)
        for shortcut in shortcuts:
            lines.append(f"  {shortcut.display.ljust(width)}   {shortcut.description}")
        lines.append("")
    return "\n".join(lines).strip()
