from __future__ import annotations

from collections.abc import Sequence


def selected_or_current_indices(
    selected_flags: Sequence[bool],
    current_index: int | None,
) -> tuple[int, ...]:
    selected = tuple(index for index, is_selected in enumerate(selected_flags) if is_selected)
    if selected:
        return selected
    if current_index is not None and 0 <= current_index < len(selected_flags):
        return (current_index,)
    return ()


def metadata_refresh_indices(
    selected_flags: Sequence[bool],
    native_steam_flags: Sequence[bool],
    current_index: int | None,
) -> tuple[int, ...]:
    candidates = selected_or_current_indices(selected_flags, current_index)
    return tuple(
        index
        for index in candidates
        if index < len(native_steam_flags) and not native_steam_flags[index]
    )
