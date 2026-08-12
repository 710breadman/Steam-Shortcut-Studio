from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from steam_shortcut_studio.shell_shortcuts import (  # noqa: E402
    SHELL_SHORTCUTS,
    accelerator,
    format_sequence,
    shortcut_for,
    shortcut_groups,
    shortcut_reference_text,
)


def test_the_primary_workflow_is_all_reachable_from_the_keyboard() -> None:
    """docs/UI_UX_TARGET.md: "Keyboard navigation covers the primary workflow"."""
    actions = {shortcut.action for shortcut in SHELL_SHORTCUTS}

    assert {
        "focus_search", "select_all", "clear_selection", "toggle_active",
        "move_up", "move_down", "refresh", "scan",
        "auto_art", "review_queue", "preview", "apply",
    } <= actions


def test_no_two_actions_claim_the_same_key() -> None:
    seen: dict[str, str] = {}
    for shortcut in SHELL_SHORTCUTS:
        for sequence in shortcut.sequences:
            assert sequence not in seen, f"{sequence} bound by {seen.get(sequence)} and {shortcut.action}"
            seen[sequence] = shortcut.action


def test_every_shortcut_declares_at_least_one_sequence_and_readable_text() -> None:
    for shortcut in SHELL_SHORTCUTS:
        assert shortcut.sequences, shortcut.action
        assert shortcut.label.strip()
        assert shortcut.description.strip()
        assert shortcut.group.strip()
        assert all(sequence.startswith("<") and sequence.endswith(">") for sequence in shortcut.sequences)


def test_sequences_render_as_the_accelerators_a_user_expects() -> None:
    assert format_sequence("<Control-f>") == "Ctrl+F"
    assert format_sequence("<Control-Shift-A>") == "Ctrl+Shift+A"
    assert format_sequence("<Control-Return>") == "Ctrl+Enter"
    assert format_sequence("<Escape>") == "Esc"
    assert format_sequence("<space>") == "Space"
    assert format_sequence("<F5>") == "F5"
    assert format_sequence("<Up>") == "Up"


def test_accelerator_uses_the_first_sequence_so_case_variants_do_not_leak() -> None:
    """Control-f and Control-F are both bound; only one is worth showing."""
    assert accelerator("focus_search") == "Ctrl+F"
    assert shortcut_for("select_all").display == "Ctrl+A"


def test_unknown_actions_raise_rather_than_render_a_blank_accelerator() -> None:
    try:
        accelerator("not_a_real_action")
    except KeyError:
        return
    raise AssertionError("An unknown action must raise, not render an empty label.")


def test_groups_preserve_declaration_order_and_cover_every_shortcut() -> None:
    groups = shortcut_groups()
    covered = [shortcut for _, shortcuts in groups for shortcut in shortcuts]

    assert len(covered) == len(SHELL_SHORTCUTS)
    assert [group for group, _ in groups] == list(dict.fromkeys(s.group for s in SHELL_SHORTCUTS))


def test_the_reference_text_lists_every_shortcut_with_its_key() -> None:
    text = shortcut_reference_text()

    for shortcut in SHELL_SHORTCUTS:
        assert shortcut.display in text, shortcut.action
        assert shortcut.description in text, shortcut.action


if __name__ == "__main__":
    for name, value in sorted(dict(globals()).items()):
        if name.startswith("test_") and callable(value):
            value()
    print("Shell shortcut tests passed.")
