from __future__ import annotations

from pathlib import Path

import pytest
from conftest import RICH_TAGS, exiftool_write, make_image, needs_exiftool, pixels
from PIL import Image, ImageCms

from kai_metadata_inspector.core.cleaner import clean_metadata_copy, sha256_file
from kai_metadata_inspector.core.exiftool_runner import safe_run_exiftool

pytestmark = needs_exiftool

PRIVATE_KEYS = [
    "EXIF:Make", "EXIF:Model", "EXIF:SerialNumber", "EXIF:Artist", "EXIF:Software",
    "EXIF:DateTimeOriginal", "EXIF:GPSLatitude", "EXIF:GPSLongitude", "Composite:GPSLatitude",
    "XMP:Title", "XMP:Subject", "IPTC:Keywords",
]


@pytest.mark.parametrize("suffix", [".jpg", ".png", ".webp", ".tif", ".heic", ".gif"])
def test_clean_removes_metadata_and_keeps_pixels(tmp_path: Path, suffix: str) -> None:
    source = make_image(tmp_path / f"photo{suffix}")
    exiftool_write(source, *[tag for tag in RICH_TAGS if suffix != ".gif" or tag.startswith("-XMP")])
    source_hash = sha256_file(source)
    output = tmp_path / "out" / f"photo_clean{suffix}"

    result = clean_metadata_copy(source, output)

    assert sha256_file(source) == source_hash, "original must not change"
    assert result["original_unchanged"] is True
    assert result["removed_tag_count"] > 0
    assert result["sensitive_remaining"] == []

    after = safe_run_exiftool(output)
    for key in PRIVATE_KEYS:
        assert key not in after, key

    assert pixels(output) == pixels(source), "image data must be bit-identical"
    assert sorted(p.name for p in output.parent.iterdir()) == [
        f"photo_clean{suffix}", "photo_clean_cleaning_report.txt",
    ]


def test_clean_keeps_orientation_and_colour_profile(tmp_path: Path) -> None:
    """Regression: "-all=" also removed the orientation tag and ICC profile,
    so cleaned phone photos appeared rotated and colours shifted."""
    source = tmp_path / "phone.jpg"
    profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    Image.new("RGB", (64, 48), "red").save(source, icc_profile=profile)
    exiftool_write(source, "-Orientation#=6", "-Make=TestMake", "-GPSLatitude=1", "-GPSLatitudeRef=N")

    output = tmp_path / "phone_clean.jpg"
    result = clean_metadata_copy(source, output)

    after = safe_run_exiftool(output)
    assert after["EXIF:Orientation"] == 6
    assert "EXIF:Make" not in after
    assert "EXIF:GPSLatitude" not in after
    assert result["sensitive_remaining"] == []
    with Image.open(output) as cleaned:
        assert cleaned.info.get("icc_profile") == profile


def test_clean_tiff_removes_ifd0_identity_tags(tmp_path: Path) -> None:
    """Regression: ExifTool's "-all=" cannot delete IFD0 in TIFF files, so
    make, model, artist, software and dates survived "cleaning"."""
    source = make_image(tmp_path / "scan.tif")
    exiftool_write(
        source, "-Make=M", "-Model=Mo", "-Artist=A", "-Software=S", "-Copyright=C",
        "-ImageDescription=D", "-ModifyDate=2024:01:01 00:00:00", "-HostComputer=H",
    )
    output = tmp_path / "scan_clean.tif"
    result = clean_metadata_copy(source, output)

    after = safe_run_exiftool(output)
    for tag in ("Make", "Model", "Artist", "Software", "Copyright", "ImageDescription",
                "ModifyDate", "HostComputer"):
        assert f"EXIF:{tag}" not in after, tag
    assert result["sensitive_remaining"] == []
    assert pixels(output) == pixels(source)


def test_clean_refuses_to_overwrite(tmp_path: Path, rich_jpg: Path) -> None:
    existing = tmp_path / "existing.jpg"
    existing.write_bytes(b"keep me")
    with pytest.raises(RuntimeError, match="already exists"):
        clean_metadata_copy(rich_jpg, existing)
    with pytest.raises(RuntimeError):
        clean_metadata_copy(rich_jpg, rich_jpg)
    assert existing.read_bytes() == b"keep me"


@pytest.mark.parametrize("kind", ["bmp", "corrupt"])
def test_failed_clean_leaves_nothing_behind(tmp_path: Path, kind: str) -> None:
    """A failed clean must not leave an uncleaned copy that looks cleaned."""
    if kind == "bmp":  # ExifTool cannot write BMP
        source = make_image(tmp_path / "pic.bmp")
    else:
        source = tmp_path / "corrupt.jpg"
        source.write_bytes(b"\xff\xd8\xff\xe1garbage" * 5)
    before = source.read_bytes()
    out_dir = tmp_path / "out"

    with pytest.raises(RuntimeError):
        clean_metadata_copy(source, out_dir / f"clean{source.suffix}")

    assert list(out_dir.iterdir()) == []
    assert source.read_bytes() == before


def test_clean_missing_source(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        clean_metadata_copy(tmp_path / "nope.jpg", tmp_path / "out.jpg")
