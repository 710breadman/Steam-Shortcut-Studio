from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, UnidentifiedImageError

DEFAULT_ALLOWED_FORMATS = frozenset({"PNG", "JPEG", "WEBP", "ICO"})
DEFAULT_MAX_BYTES = 50 * 1024 * 1024
DEFAULT_MAX_PIXELS = 100_000_000


class ArtworkValidationError(ValueError):
    """Raised when an artwork file is unsafe or unusable."""


@dataclass(frozen=True, slots=True)
class ArtworkFileInfo:
    path: Path
    format: str
    width: int
    height: int
    mode: str
    file_size: int
    sha256: str
    average_hash: str
    orientation: str
    aspect_ratio: float
    has_alpha: bool

    @property
    def dimensions(self) -> tuple[int, int]:
        return self.width, self.height


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _looks_like_text_error(prefix: bytes) -> bool:
    cleaned = prefix.lstrip().lower()
    return cleaned.startswith(
        (
            b"<!doctype html",
            b"<html",
            b"<?xml",
            b"{" ,
            b"[",
        )
    )


def _orientation(width: int, height: int) -> str:
    if width == height:
        return "square"
    return "landscape" if width > height else "portrait"


def average_hash(image: Image.Image, hash_size: int = 8) -> str:
    """Return a deterministic average hash suitable for duplicate screening."""

    if hash_size < 2:
        raise ValueError("hash_size must be at least 2")
    grayscale = image.convert("L").resize((hash_size, hash_size), Image.Resampling.LANCZOS)
    pixels = list(grayscale.getdata())
    mean = sum(pixels) / len(pixels)
    bits = "".join("1" if value >= mean else "0" for value in pixels)
    width = (len(bits) + 3) // 4
    return f"{int(bits, 2):0{width}x}"


def hash_distance(first: str, second: str) -> int:
    """Return Hamming distance between two equal-width hexadecimal hashes."""

    if len(first) != len(second):
        raise ValueError("Hashes must have equal width")
    try:
        return (int(first, 16) ^ int(second, 16)).bit_count()
    except ValueError as exc:
        raise ValueError("Hashes must be hexadecimal") from exc


def validate_artwork_file(
    path: str | Path,
    *,
    allowed_formats: frozenset[str] = DEFAULT_ALLOWED_FORMATS,
    max_bytes: int = DEFAULT_MAX_BYTES,
    max_pixels: int = DEFAULT_MAX_PIXELS,
    min_width: int = 32,
    min_height: int = 32,
) -> ArtworkFileInfo:
    """Decode and inspect an artwork file before it can enter an apply plan."""

    candidate = Path(path).expanduser()
    if not candidate.is_file():
        raise ArtworkValidationError(f"Artwork file does not exist: {candidate}")

    file_size = candidate.stat().st_size
    if file_size <= 0:
        raise ArtworkValidationError("Artwork file is empty")
    if max_bytes <= 0:
        raise ValueError("max_bytes must be positive")
    if file_size > max_bytes:
        raise ArtworkValidationError(
            f"Artwork file is too large: {file_size} bytes exceeds {max_bytes}"
        )

    with candidate.open("rb") as handle:
        prefix = handle.read(256)
    if _looks_like_text_error(prefix):
        raise ArtworkValidationError("Artwork payload appears to be HTML, XML, or JSON")

    try:
        with Image.open(candidate) as probe:
            image_format = str(probe.format or "").upper()
            width, height = probe.size
            mode = probe.mode
            if image_format not in allowed_formats:
                raise ArtworkValidationError(
                    f"Unsupported artwork format: {image_format or 'unknown'}"
                )
            if width < min_width or height < min_height:
                raise ArtworkValidationError(
                    f"Artwork dimensions are too small: {width}x{height}"
                )
            if width * height > max_pixels:
                raise ArtworkValidationError(
                    f"Artwork has too many pixels: {width * height} exceeds {max_pixels}"
                )
            probe.verify()

        with Image.open(candidate) as decoded:
            decoded.load()
            image_hash = average_hash(decoded)
            has_alpha = "A" in decoded.getbands() or "transparency" in decoded.info
            mode = decoded.mode
    except ArtworkValidationError:
        raise
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as exc:
        raise ArtworkValidationError(f"Artwork could not be decoded: {exc}") from exc

    return ArtworkFileInfo(
        path=candidate.resolve(strict=False),
        format=image_format,
        width=width,
        height=height,
        mode=mode,
        file_size=file_size,
        sha256=sha256_file(candidate),
        average_hash=image_hash,
        orientation=_orientation(width, height),
        aspect_ratio=round(width / height, 6),
        has_alpha=has_alpha,
    )
