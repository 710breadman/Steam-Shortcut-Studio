from __future__ import annotations

from pathlib import Path

path = Path("steam_shortcut_studio/source_scans.py")
text = path.read_text(encoding="utf-8")
old = '''NON_AUTHORITATIVE_ISSUE_CODES = frozenset(
    {
        "programdata_unavailable",
        "manifest_directory_missing",
    }
)
'''
new = '''NON_AUTHORITATIVE_ISSUE_CODES = frozenset(
    {
        "programdata_unavailable",
        "manifest_directory_missing",
        "collection_root_missing",
        "steam_root_missing",
    }
)
'''
if old not in text:
    raise RuntimeError("Could not locate unavailable-source policy block")
path.write_text(text.replace(old, new, 1), encoding="utf-8")

for temporary in (
    Path(".github/workflows/apply-source-scan-unavailable-policy.yml"),
    Path(".github/source-scan-unavailable.trigger"),
    Path("scripts/apply_source_scan_unavailable_policy.py"),
):
    temporary.unlink(missing_ok=True)
