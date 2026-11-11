from __future__ import annotations

from pathlib import Path

import pytest
from conftest import make_image
from PIL import Image

from kai_metadata_inspector.core.preview import HEIC_PREVIEW_AVAILABLE, load_preview_image

BLUE, RED = (30, 30, 200), (200, 30, 30)


def close(pixel: tuple, colour: tuple, tolerance: int = 40) -> bool:
    return all(abs(a - b) <= tolerance for a, b in zip(pixel[:3], colour, strict=True))


@pytest.mark.parametrize("suffix", [".jpg", ".png", ".webp", ".tif", ".bmp", ".gif"])
def test_preview_common_formats(tmp_path: Path, suffix: str) -> None:
    preview = load_preview_image(make_image(tmp_path / f"img{suffix}"))
    assert preview.mode == "RGBA"
    assert preview.size == (64, 48)
    assert close(preview.getpixel((2, 2)), BLUE)
    assert close(preview.getpixel((60, 44)), RED)


def test_preview_heic(tmp_path: Path) -> None:
    assert HEIC_PREVIEW_AVAILABLE
    preview = load_preview_image(make_image(tmp_path / "img.heic"))
    assert preview.size == (64, 48)
    assert close(preview.getpixel((2, 2)), BLUE)


def test_preview_applies_exif_orientation_without_touching_file(tmp_path: Path) -> None:
    path = make_image(tmp_path / "phone.jpg")
    with Image.open(path) as image:
        exif = image.getexif()
        exif[0x0112] = 6  # rotate 90° clockwise to display
        image.save(path, exif=exif)
    stored = path.read_bytes()

    preview = load_preview_image(path)

    assert preview.size == (48, 64)
    # The blue top-left block moves to the top-right when rotated 90° CW.
    assert close(preview.getpixel((45, 2)), BLUE)
    assert close(preview.getpixel((2, 60)), RED)
    assert path.read_bytes() == stored


def test_preview_downscales_large_images(tmp_path: Path) -> None:
    path = tmp_path / "big.jpg"
    Image.new("RGB", (6000, 4000), "green").save(path, quality=60)
    preview = load_preview_image(path, max_side=1024)
    assert max(preview.size) <= 1024
    assert preview.size[0] / preview.size[1] == pytest.approx(1.5, abs=0.01)


def test_preview_keeps_transparency(tmp_path: Path) -> None:
    path = tmp_path / "alpha.png"
    Image.new("RGBA", (10, 10), (0, 255, 0, 128)).save(path)
    assert load_preview_image(path).getpixel((0, 0)) == (0, 255, 0, 128)


@pytest.mark.parametrize("content", [b"", b"not an image", b"\xff\xd8\xff\xe1garbage" * 5])
def test_preview_rejects_bad_files(tmp_path: Path, content: bytes) -> None:
    bad = tmp_path / "bad.jpg"
    bad.write_bytes(content)
    with pytest.raises(Exception):  # noqa: B017 - any decode error is acceptable
        load_preview_image(bad)
