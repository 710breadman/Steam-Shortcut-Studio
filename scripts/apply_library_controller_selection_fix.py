from __future__ import annotations

from pathlib import Path

path = Path("steam_shortcut_studio/library_controller.py")
text = path.read_text(encoding="utf-8")

old_refresh = """            self._rows = tuple(rows)
            self.selection.selected_ids.intersection_update(valid_ids)
            if self.selection.active_id not in valid_ids:
                self.selection.active_id = None
            return self.snapshot()
"""
new_refresh = """            self._rows = tuple(rows)
            self.selection.retain_available(valid_ids)
            return self.snapshot()
"""
if old_refresh not in text:
    raise RuntimeError("Could not locate controller selection refresh block")
text = text.replace(old_refresh, new_refresh, 1)

old_selected = """        with self._lock:
            self.selection.set_selected(item_id, selected)
            return self.snapshot()
"""
new_selected = """        with self._lock:
            if selected:
                self.selection.add(item_id)
            else:
                self.selection.remove(item_id)
            return self.snapshot()
"""
if old_selected not in text:
    raise RuntimeError("Could not locate controller set_selected block")
text = text.replace(old_selected, new_selected, 1)

path.write_text(text, encoding="utf-8")

for temporary in (
    Path(".github/workflows/library-controller-diagnostic.yml"),
    Path(".github/workflows/apply-library-controller-selection-fix.yml"),
    Path(".github/library-controller-selection-fix.trigger"),
    Path("scripts/apply_library_controller_selection_fix.py"),
):
    temporary.unlink(missing_ok=True)
