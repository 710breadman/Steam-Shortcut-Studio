from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

SelectionAction = Literal["select", "clear", "invert"]
SelectionScope = Literal["all", "visible", "current_filter"]


@dataclass(frozen=True, slots=True)
class SelectionActionResult:
    action: SelectionAction
    scope: SelectionScope
    row_count: int

    @property
    def label(self) -> str:
        return selection_action_label(self.action, self.scope, self.row_count)


def selection_action_label(action: SelectionAction, scope: SelectionScope, row_count: int) -> str:
    action_text = {
        "select": "Selected",
        "clear": "Cleared",
        "invert": "Inverted",
    }[action]
    if scope == "current_filter":
        return f"{action_text} {row_count} row(s) matching current filter."
    if scope == "visible":
        return f"{action_text} {row_count} visible game row(s)."
    if action == "invert":
        return f"{action_text} {row_count} game selection(s)."
    return f"{action_text} {row_count} all game row(s)."


def selection_action_result(
    action: SelectionAction,
    scope: SelectionScope,
    row_count: int,
) -> SelectionActionResult:
    return SelectionActionResult(action=action, scope=scope, row_count=row_count)
