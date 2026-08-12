from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from steam_shortcut_studio.library_edits import (  # noqa: E402
    OVERRIDE_FIELDS,
    build_manual_overrides,
    describe_override_changes,
    field_label,
    override_change_message,
    override_value,
)
from steam_shortcut_studio.library_store import LibraryStore  # noqa: E402
from steam_shortcut_studio.sources.base import (  # noqa: E402
    SourceLibraryItem,
    stable_source_item_id,
)


def _source(**overrides: str) -> dict[str, str]:
    values = {
        "display_title": "Source Title",
        "launch_target": r"C:\Games\Example\game.exe",
        "launch_arguments": "",
        "working_directory": r"C:\Games\Example",
        "notes": "",
    }
    values.update(overrides)
    return values


def test_editing_a_field_to_its_source_value_stores_no_override() -> None:
    """Otherwise the value is pinned and a later launcher rename never appears."""
    assert override_value("display_title", "Source Title", "Source Title") is None
    assert override_value("display_title", "  Source Title  ", "Source Title") is None
    assert override_value("display_title", "My Title", "Source Title") == "My Title"


def test_clearing_a_field_stores_no_override() -> None:
    assert override_value("launch_target", "", r"C:\Games\Example\game.exe") is None
    assert override_value("launch_target", "   ", r"C:\Games\Example\game.exe") is None


def test_notes_have_no_source_counterpart_so_any_value_is_an_override() -> None:
    assert override_value("notes", "Runs badly on the dGPU", "") == "Runs badly on the dGPU"
    assert override_value("notes", "", "") is None


def test_every_field_is_always_written_so_a_partial_save_cannot_erase_others() -> None:
    overrides = build_manual_overrides(
        "item-1", {"display_title": "My Title"}, _source()
    )

    assert overrides.item_id == "item-1"
    assert overrides.display_title == "My Title"
    # Fields absent from `edits` resolve to None rather than being skipped.
    for field in OVERRIDE_FIELDS:
        assert hasattr(overrides, field)
    assert overrides.launch_target is None
    assert overrides.notes is None


def test_a_missing_item_id_is_rejected() -> None:
    try:
        build_manual_overrides("  ", {}, _source())
    except ValueError:
        return
    raise AssertionError("Overrides without a stable ID must be rejected.")


def test_change_descriptions_distinguish_setting_from_reverting() -> None:
    overrides = build_manual_overrides(
        "item-1",
        {"display_title": "My Title", "notes": ""},
        _source(),
    )
    changes = describe_override_changes({"display_title": "", "notes": "Old note"}, overrides)
    actions = {change.field: change.action for change in changes}

    assert actions["display_title"] == "set"
    assert actions["notes"] == "cleared"
    assert actions["launch_target"] == "unchanged"
    assert override_change_message(changes) == "1 override(s) saved. 1 reverted to the source value."


def test_no_changes_reports_nothing_to_save() -> None:
    overrides = build_manual_overrides("item-1", {}, _source())
    changes = describe_override_changes({field: "" for field in OVERRIDE_FIELDS}, overrides)

    assert override_change_message(changes) == "No changes to save."


def test_field_labels_are_human_readable() -> None:
    assert field_label("display_title") == "Title"
    assert field_label("working_directory") == "Working directory"


def test_round_trip_through_the_real_store_resolves_and_reverts() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        store = LibraryStore(Path(tmp) / "library.sqlite3")
        stable_id = stable_source_item_id("epic", external_id="one")
        store.replace_source_snapshot(
            "epic",
            [
                SourceLibraryItem(
                    stable_id=stable_id,
                    source="epic",
                    external_id="one",
                    title="Source Title",
                    install_path=r"C:\Games\Example",
                    launch_target=r"C:\Games\Example\game.exe",
                    platform="windows",
                    size_bytes=1024,
                    launch_target_exists=True,
                )
            ],
        )
        source = _source()

        store.save_overrides(
            build_manual_overrides(stable_id, {"display_title": "My Title", "notes": "Note"}, source)
        )
        resolved = store.resolve_item(stable_id)
        assert resolved is not None
        assert resolved.display_title == "My Title"
        assert resolved.notes == "Note"
        assert "display_title" in resolved.overridden_fields

        # Editing the title back to the source value removes the override
        # rather than pinning it.
        store.save_overrides(
            build_manual_overrides(stable_id, {"display_title": "Source Title", "notes": "Note"}, source)
        )
        reverted = store.resolve_item(stable_id)
        assert reverted is not None
        assert reverted.display_title == "Source Title"
        assert "display_title" not in reverted.overridden_fields
        # The unrelated note survived a save that only mentioned the title.
        assert reverted.notes == "Note"


if __name__ == "__main__":
    for name, value in sorted(dict(globals()).items()):
        if name.startswith("test_") and callable(value):
            value()
    print("Library edits tests passed.")
