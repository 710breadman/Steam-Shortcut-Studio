from __future__ import annotations

from pathlib import Path


path = Path("tests/smoke_test.py")
text = path.read_text(encoding="utf-8")

if "from PIL import Image" not in text:
    marker = "from pathlib import Path\n"
    if marker not in text:
        raise RuntimeError("Could not locate pathlib import in smoke_test.py")
    text = text.replace(marker, marker + "\nfrom PIL import Image\n", 1)

helper = '''\n\ndef write_test_image(\n    path: Path,\n    *,\n    size: tuple[int, int] = (96, 64),\n    color: tuple[int, int, int] = (32, 96, 160),\n) -> None:\n    path.parent.mkdir(parents=True, exist_ok=True)\n    Image.new("RGB", size, color).save(path)\n'''
if "def write_test_image(" not in text:
    marker = "\n\ndef same_path(left: Path | None, right: Path) -> bool:\n"
    if marker not in text:
        raise RuntimeError("Could not locate same_path insertion point")
    text = text.replace(marker, helper + marker, 1)

replacements = {
    'image.write_bytes(b"fake image")': 'write_test_image(image, size=(1920, 620))',
    'image.write_bytes(b"new grid")': 'write_test_image(image, size=(600, 900))',
    '(profile.grid_dir / "424242p.png").read_bytes() == b"new grid"': '(profile.grid_dir / "424242p.png").read_bytes() == image.read_bytes()',
    '(profile.grid_dir / "424242.png").read_bytes() == b"new grid"': '(profile.grid_dir / "424242.png").read_bytes() == image.read_bytes()',
}
expected_counts = {
    'image.write_bytes(b"fake image")': 1,
    'image.write_bytes(b"new grid")': 2,
    '(profile.grid_dir / "424242p.png").read_bytes() == b"new grid"': 1,
    '(profile.grid_dir / "424242.png").read_bytes() == b"new grid"': 1,
}
for old, new in replacements.items():
    count = text.count(old)
    if count != expected_counts[old]:
        raise RuntimeError(f"Expected {expected_counts[old]} occurrences of {old!r}, found {count}")
    text = text.replace(old, new)

path.write_text(text, encoding="utf-8")

for temporary in (
    Path(".github/workflows/apply-smoke-image-fixture-patch.yml"),
    Path(".github/smoke-image-fixture.trigger"),
    Path("scripts/apply_smoke_image_fixture_patch.py"),
):
    temporary.unlink(missing_ok=True)
