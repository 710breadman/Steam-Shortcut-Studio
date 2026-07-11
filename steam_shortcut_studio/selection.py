from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Sequence


@dataclass(slots=True)
class SelectionState:
    """UI-independent selection state for library and bulk actions.

    The active item drives the inspector. Selected items drive bulk actions.
    Those concepts are intentionally separate so opening one game never
    silently changes the scope of a batch operation.
    """

    selected_ids: set[str] = field(default_factory=set)
    active_id: str | None = None
    anchor_id: str | None = None

    def set_active(self, item_id: str | None) -> None:
        self.active_id = item_id

    def clear(self) -> None:
        self.selected_ids.clear()
        self.anchor_id = None

    def replace(self, item_ids: Iterable[str]) -> None:
        ordered = [item_id for item_id in item_ids if item_id]
        self.selected_ids = set(ordered)
        self.anchor_id = ordered[-1] if ordered else None

    def add(self, item_id: str) -> None:
        if not item_id:
            return
        self.selected_ids.add(item_id)
        self.anchor_id = item_id

    def remove(self, item_id: str) -> None:
        self.selected_ids.discard(item_id)
        if self.anchor_id == item_id:
            self.anchor_id = None

    def toggle(self, item_id: str) -> bool:
        """Toggle an item and return its new selected state."""

        if item_id in self.selected_ids:
            self.remove(item_id)
            return False
        self.add(item_id)
        return True

    def select_range(
        self,
        ordered_ids: Sequence[str],
        target_id: str,
        *,
        additive: bool = False,
    ) -> list[str]:
        """Select an inclusive range from the anchor to ``target_id``.

        If the anchor is unavailable, the target becomes the only selected
        item unless ``additive`` is true. The returned list preserves display
        order and can be used for status text or command dispatch.
        """

        if target_id not in ordered_ids:
            raise ValueError(f"Unknown selection target: {target_id}")

        anchor = self.anchor_id if self.anchor_id in ordered_ids else target_id
        start = ordered_ids.index(anchor)
        end = ordered_ids.index(target_id)
        if start > end:
            start, end = end, start
        selected_range = list(ordered_ids[start : end + 1])

        if not additive:
            self.selected_ids.clear()
        self.selected_ids.update(selected_range)
        self.anchor_id = anchor
        return selected_range

    def select_all(self, ordered_ids: Iterable[str]) -> None:
        self.selected_ids.update(item_id for item_id in ordered_ids if item_id)

    def retain_available(self, available_ids: Iterable[str]) -> set[str]:
        """Drop deleted entries without changing selection because of filters."""

        available = set(available_ids)
        removed = self.selected_ids - available
        self.selected_ids.intersection_update(available)
        if self.active_id not in available:
            self.active_id = None
        if self.anchor_id not in available:
            self.anchor_id = None
        return removed

    def selected_in_order(self, ordered_ids: Iterable[str]) -> list[str]:
        return [item_id for item_id in ordered_ids if item_id in self.selected_ids]

    @property
    def count(self) -> int:
        return len(self.selected_ids)
