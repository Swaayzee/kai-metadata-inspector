"""Preview decoding, kept GUI-free so it can be tested without a display."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageOps

try:
    from pillow_heif import register_heif_opener

    register_heif_opener()
    HEIC_PREVIEW_AVAILABLE = True
except Exception:
    HEIC_PREVIEW_AVAILABLE = False

PREVIEW_MAX_SIDE = 1600


def load_preview_image(path: Path, max_side: int = PREVIEW_MAX_SIDE) -> Image.Image:
    """Decode a downscaled RGBA preview with EXIF orientation applied.

    The file is opened read-only. Raises if Pillow cannot decode it,
    including Pillow's decompression-bomb guard for absurdly large images.
    """
    with Image.open(path) as image:
        # Lets the JPEG decoder downscale while decoding, and shrinks before
        # rotating: several times faster and far less memory for large photos.
        image.draft("RGB", (max_side, max_side))
        image.thumbnail((max_side, max_side))
        return ImageOps.exif_transpose(image).convert("RGBA")
