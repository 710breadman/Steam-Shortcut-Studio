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


def build_mixed_selection_summary(
    selected_flags: Sequence[bool],
    item_ids: Sequence[str],
    visible_indices: Sequence[int],
    selected_item_ids: set[str] | frozenset[str],
) -> SelectionSummary:
    total = len(selected_flags)

    def is_selected(index: int) -> bool:
        if not 0 <= index < total:
            return False
        item_id = item_ids[index] if index < len(item_ids) else ""
        return item_id in selected_item_ids if item_id else selected_flags[index]

    selected = sum(1 for index in range(total) if is_selected(index))
    visible_selected = sum(1 for index in visible_indices if is_selected(index))
    return SelectionSummary(
        total=total,
        selected=selected,
        visible_total=len(visible_indices),
        visible_selected=visible_selected,
    )
