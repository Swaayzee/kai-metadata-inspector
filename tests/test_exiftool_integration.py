from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from kai_metadata_inspector.core.analyzer import build_analysis
from kai_metadata_inspector.core.cleaner import clean_metadata_copy
from kai_metadata_inspector.core.exiftool_runner import safe_run_exiftool
from kai_metadata_inspector.core.runtime import run_exiftool, runtime_diagnostics

pytestmark = pytest.mark.skipif(runtime_diagnostics()["status"] != "ok", reason="ExifTool is not installed")


def test_real_signed_gps_and_cleaning(tmp_path: Path) -> None:
    source = tmp_path / "private.jpg"
    cleaned = tmp_path / "clean.jpg"
    Image.new("RGB", (32, 24), "purple").save(source)
    write = run_exiftool([
        "-overwrite_original", "-GPSLatitude=33.9", "-GPSLatitudeRef=S",
        "-GPSLongitude=151.2", "-GPSLongitudeRef=W", "-Artist=Private test",
        "--", str(source),
    ])
    assert write.returncode == 0, write.stderr

    raw = safe_run_exiftool(source)
    analysis = build_analysis(source, raw, runtime_diagnostics()["exiftool_version"])
    assert analysis["flags"]["gps_latitude"].startswith("-33.9")
    assert analysis["flags"]["gps_longitude"].startswith("-151.2")

    result = clean_metadata_copy(source, cleaned)
    assert result["original_unchanged"] is True
    assert result["removed_tag_count"] > 0
    cleaned_raw = safe_run_exiftool(cleaned)
    assert "EXIF:Artist" not in cleaned_raw
