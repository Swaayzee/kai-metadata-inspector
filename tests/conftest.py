"""Shared fixtures. Every test image is generated at run time — no real
photos are stored in the repository."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from PIL import Image

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from kai_metadata_inspector.core.runtime import run_exiftool, runtime_diagnostics  # noqa: E402

HAS_EXIFTOOL = runtime_diagnostics()["status"] == "ok"
needs_exiftool = pytest.mark.skipif(not HAS_EXIFTOOL, reason="ExifTool is not installed")

# CI sets this so a missing ExifTool fails the run instead of quietly
# skipping most of the suite.
if os.environ.get("KAI_REQUIRE_EXIFTOOL") and not HAS_EXIFTOOL:
    raise pytest.UsageError(f"KAI_REQUIRE_EXIFTOOL is set but ExifTool is unavailable: {runtime_diagnostics()['status']}")

RICH_TAGS = [
    "-Make=TestMake",
    "-Model=TestModel X1",
    "-LensModel=Test 50mm",
    "-SerialNumber=SN12345",
    "-Artist=Test Artist",
    "-Software=TestSoft 1.0",
    "-DateTimeOriginal=2024:01:02 03:04:05",
    "-OffsetTimeOriginal=+01:00",
    "-GPSLatitude=33.5",
    "-GPSLatitudeRef=S",
    "-GPSLongitude=70.25",
    "-GPSLongitudeRef=W",
    "-GPSAltitude=120",
    "-GPSAltitudeRef#=0",
    "-GPSDateStamp=2024:01:02",
    "-GPSTimeStamp=02:04:05",
    "-XMP-dc:Title=Test Title",
    "-XMP-dc:Subject=alpha",
    "-XMP-dc:Subject=beta",
    "-IPTC:Keywords=iptc-keyword",
]


def exiftool_write(path: Path, *args: str) -> None:
    result = run_exiftool(["-m", "-overwrite_original", *args, "--", str(path)])
    assert result.returncode == 0, result.stderr


def make_image(path: Path, size: tuple[int, int] = (64, 48)) -> Path:
    """A small image with a blue top-left quarter so orientation is detectable."""
    image = Image.new("RGB", size, (200, 30, 30))
    image.paste((30, 30, 200), (0, 0, size[0] // 2, size[1] // 2))

    if path.suffix.lower() in (".heic", ".heif"):
        import pillow_heif

        pillow_heif.register_heif_opener()

    image.save(path)
    return path


def pixels(path: Path) -> bytes:
    with Image.open(path) as image:
        return image.convert("RGB").tobytes()


@pytest.fixture(autouse=True)
def kai_home(tmp_path, monkeypatch) -> Path:
    """Keep outputs and recovery backups out of the real user profile."""
    home = tmp_path / "kai-home"
    monkeypatch.setenv("KAI_METADATA_HOME", str(home))
    return home


@pytest.fixture
def rich_jpg(tmp_path) -> Path:
    path = make_image(tmp_path / "rich.jpg")
    exiftool_write(path, *RICH_TAGS)
    return path
