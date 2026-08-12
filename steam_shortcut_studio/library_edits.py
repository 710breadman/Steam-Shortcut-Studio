"""Turn edited field values into a safe `ManualOverrides` record.

Two things make this worth its own module rather than inline UI code.

`LibraryStore.save_overrides` replaces every column, so a caller that supplies
only the field it edited silently erases the others. Every save therefore has
to carry the complete set.

And an override should only exist where the user actually disagrees with the
source. Storing "override the title to exactly what the launcher already says"
would pin that title forever, so a later rename in the launcher would never
appear -- and the row would show as `customized` for no reason. Editing a value
back to its source value removes the override instead.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from .library_store import ManualOverrides


OVERRIDE_FIELDS = (
    "display_title",
    "launch_target",
    "launch_arguments",
    "working_directory",
    "notes",
)

# `notes` is the one field with no source-provided counterpart: a launcher has
# no opinion about a user's personal note, so any non-empty value is an override.
SOURCE_BACKED_FIELDS = frozenset(OVERRIDE_FIELDS) - {"notes"}


@dataclass(frozen=True, slots=True)
class OverrideChange:
    field: str
    action: str  # "set" | "cleared" | "unchanged"


def _clean(value: object) -> str:
    return str(value or "").strip()


def override_value(field: str, edited: str, source: str) -> str | None:
    """The value to store for one field, or None to store no override."""
    edited_text = _clean(edited)
    if not edited_text:
        return None
    if field in SOURCE_BACKED_FIELDS and edited_text == _clean(source):
        return None
    return edited_text


def build_manual_overrides(
    item_id: str,
    edits: Mapping[str, str],
    source: Mapping[str, str],
) -> ManualOverrides:
    """Build a complete override record from edited and source values."""
    if not str(item_id or "").strip():
        raise ValueError("Manual overrides require a stable library item ID.")
    values = {
        field: override_value(field, edits.get(field, ""), source.get(field, ""))
        for field in OVERRIDE_FIELDS
    }
    return ManualOverrides(item_id=item_id, **values)


def describe_override_changes(
    previous: Mapping[str, str],
    overrides: ManualOverrides,
) -> tuple[OverrideChange, ...]:
    """Compare a saved record against the overrides that were in effect before."""
    changes: list[OverrideChange] = []
    for field in OVERRIDE_FIELDS:
        before = _clean(previous.get(field, ""))
        after = _clean(getattr(overrides, field))
        if before == after:
            changes.append(OverrideChange(field, "unchanged"))
        elif after:
            changes.append(OverrideChange(field, "set"))
        else:
            changes.append(OverrideChange(field, "cleared"))
    return tuple(changes)


def override_change_message(changes: tuple[OverrideChange, ...]) -> str:
    applied = [change for change in changes if change.action != "unchanged"]
    if not applied:
        return "No changes to save."
    set_count = sum(1 for change in applied if change.action == "set")
    cleared_count = len(applied) - set_count
    parts = []
    if set_count:
        parts.append(f"{set_count} override(s) saved")
    if cleared_count:
        parts.append(f"{cleared_count} reverted to the source value")
    return ". ".join(parts) + "."


def field_label(field: str) -> str:
    return {
        "display_title": "Title",
        "launch_target": "Launch target",
        "launch_arguments": "Launch arguments",
        "working_directory": "Working directory",
        "notes": "Notes",
    }.get(field, field.replace("_", " ").title())
