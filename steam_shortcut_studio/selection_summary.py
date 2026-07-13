from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SelectionSummary:
    total: int
    selected: int
    visible_total: int
    visible_selected: int

    @property
    def label(self) -> str:
        if not self.total:
            return "0 selected"
        return f"{self.selected}/{self.total} selected; {self.visible_selected}/{self.visible_total} visible"


def build_selection_summary(
    selected_flags: Sequence[bool],
    visible_indices: Sequence[int],
) -> SelectionSummary:
    total = len(selected_flags)
    selected = sum(1 for flag in selected_flags if flag)
    visible_selected = sum(
        1
        for index in visible_indices
        if 0 <= index < total and selected_flags[index]
    )
    return SelectionSummary(
        total=total,
        selected=selected,
        visible_total=len(visible_indices),
        visible_selected=visible_selected,
    )
