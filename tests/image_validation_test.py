from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from steam_shortcut_studio.image_validation import (
    ArtworkValidationError,
    average_hash,
    hash_distance,
    validate_artwork_file,
)


class ArtworkValidationTests(unittest.TestCase):
    def test_valid_png_reports_dimensions_orientation_alpha_and_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "portrait.png"
            Image.new("RGBA", (600, 900), (20, 80, 160, 180)).save(path)

            info = validate_artwork_file(path)

            self.assertEqual(info.format, "PNG")
            self.assertEqual(info.dimensions, (600, 900))
            self.assertEqual(info.orientation, "portrait")
            self.assertAlmostEqual(info.aspect_ratio, 2 / 3, places=5)
            self.assertTrue(info.has_alpha)
            self.assertEqual(len(info.sha256), 64)
            self.assertEqual(len(info.average_hash), 16)

    def test_valid_jpeg_is_landscape_without_alpha(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "hero.jpg"
            Image.new("RGB", (1920, 620), (30, 40, 50)).save(path, quality=90)

            info = validate_artwork_file(path)

            self.assertEqual(info.format, "JPEG")
            self.assertEqual(info.orientation, "landscape")
            self.assertFalse(info.has_alpha)

    def test_html_payload_with_image_extension_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.png"
            path.write_text("<!doctype html><html><body>rate limited</body></html>", encoding="utf-8")

            with self.assertRaisesRegex(ArtworkValidationError, "HTML"):
                validate_artwork_file(path)

    def test_truncated_image_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "truncated.png"
            Image.new("RGB", (128, 128), "navy").save(path)
            path.write_bytes(path.read_bytes()[:32])

            with self.assertRaises(ArtworkValidationError):
                validate_artwork_file(path)

    def test_tiny_image_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tiny.png"
            Image.new("RGB", (16, 16), "white").save(path)

            with self.assertRaisesRegex(ArtworkValidationError, "too small"):
                validate_artwork_file(path)

    def test_byte_and_pixel_limits_are_enforced(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "image.png"
            Image.new("RGB", (100, 100), "white").save(path)

            with self.assertRaisesRegex(ArtworkValidationError, "too large"):
                validate_artwork_file(path, max_bytes=8)
            with self.assertRaisesRegex(ArtworkValidationError, "too many pixels"):
                validate_artwork_file(path, max_pixels=5_000)

    def test_average_hash_distance_detects_identical_content(self) -> None:
        first = Image.new("RGB", (64, 64), "black")
        second = Image.new("RGB", (128, 128), "black")
        different = Image.new("RGB", (64, 64), "white")
        for x in range(32):
            for y in range(64):
                different.putpixel((x, y), (0, 0, 0))

        first_hash = average_hash(first)
        second_hash = average_hash(second)
        different_hash = average_hash(different)

        self.assertEqual(hash_distance(first_hash, second_hash), 0)
        self.assertGreater(hash_distance(first_hash, different_hash), 0)

    def test_hash_distance_rejects_mismatched_widths(self) -> None:
        with self.assertRaises(ValueError):
            hash_distance("ffff", "ff")


if __name__ == "__main__":
    unittest.main()
