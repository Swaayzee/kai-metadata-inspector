from __future__ import annotations

from pathlib import Path

import pytest
from conftest import make_image, needs_exiftool, pixels

from kai_metadata_inspector.core import metadata_writer
from kai_metadata_inspector.core.exiftool_runner import safe_run_exiftool
from kai_metadata_inspector.core.metadata_writer import (
    build_write_arguments,
    changed_fields,
    current_field_values,
    sha256_file,
    write_metadata_to_original,
)


def test_changed_fields_ignores_formatting_differences() -> None:
    original = {"title": "A", "keywords": "one, two", "gps_latitude": "-33.5", "camera_make": "Canon"}
    edited = {"title": "A ", "keywords": ["one", "two"], "gps_latitude": "-33.50000", "camera_make": ""}
    assert changed_fields(original, edited) == {"camera_make": ""}


@pytest.mark.parametrize("fields", [
    {"gps_latitude": "91"},
    {"gps_longitude": "-180.5"},
    {"gps_latitude": "N"},
    {"gps_latitude": "nan"},
    {"gps_altitude": "inf"},
    {"date_taken": "2024-01-02 03:04:05"},
    {"date_taken": "2024:13:45 03:04:05"},
    {"not_a_field": "x"},
])
def test_invalid_values_are_rejected(fields: dict) -> None:
    with pytest.raises(RuntimeError):
        build_write_arguments(fields)


def test_values_are_always_passed_as_literal_assignments() -> None:
    arguments = build_write_arguments({"title": "<=/etc/passwd", "creator": "-all=", "keywords": ["-k"]})
    assert all(argument.startswith(("-XMP-", "-EXIF:")) and "=" in argument for argument in arguments)


@needs_exiftool
@pytest.mark.parametrize("suffix", [".jpg", ".png", ".webp", ".tif", ".heic"])
def test_write_and_reopen(tmp_path: Path, kai_home: Path, suffix: str) -> None:
    path = make_image(tmp_path / f"img{suffix}")
    original_bytes = path.read_bytes()
    before_pixels = pixels(path)

    fields = {
        "title": "My title",
        "description": "A description",
        "creator": "Zoë Ångström",
        "rights": "© 2026 Me",
        "keywords": ["one", "two"],
        "camera_make": "Canon",
        "camera_model": "EOS R6",
        "lens_make": "Canon",
        "lens_model": "RF 50mm",
        "gps_latitude": "-33.8688",
        "gps_longitude": "151.2093",
        "gps_altitude": "-12.5",
        "date_taken": "2023:12:31 23:59:58",
    }
    result = write_metadata_to_original(path, fields)

    assert result["file_changed"] is True
    assert result["unverified_fields"] == []
    assert Path(result["backup_path"]).read_bytes() == original_bytes
    assert Path(result["backup_path"]).parent == kai_home / "backups"

    values = current_field_values(safe_run_exiftool(path))  # fresh read from disk
    assert values["title"] == "My title"
    assert values["creator"] == "Zoë Ångström"
    assert values["rights"] == "© 2026 Me"
    assert values["keywords"] == "one, two"
    assert values["camera_model"] == "EOS R6"
    assert values["lens_model"] == "RF 50mm"
    assert float(values["gps_latitude"]) == pytest.approx(-33.8688, abs=1e-6)
    assert float(values["gps_longitude"]) == pytest.approx(151.2093, abs=1e-6)
    assert float(values["gps_altitude"]) == pytest.approx(-12.5)
    assert values["date_taken"] == "2023:12:31 23:59:58"

    assert pixels(path) == before_pixels, "editing metadata must not touch image data"
    assert [p.name for p in tmp_path.iterdir() if p.is_file()] == [path.name], "no files left beside the photo"


@needs_exiftool
def test_xmp_gps_keeps_hemisphere(rich_jpg: Path) -> None:
    """Regression: XMP GPS was written as an absolute value, so southern and
    western positions were stored in the wrong hemisphere in XMP."""
    write_metadata_to_original(rich_jpg, {"gps_latitude": "-10.5", "gps_longitude": "-20.25"})
    raw = safe_run_exiftool(rich_jpg)
    assert raw["XMP:GPSLatitude"] == pytest.approx(-10.5)
    assert raw["XMP:GPSLongitude"] == pytest.approx(-20.25)
    assert raw["Composite:GPSLatitude"] == pytest.approx(-10.5)


@needs_exiftool
def test_only_given_fields_change(rich_jpg: Path) -> None:
    """Regression: a title-only edit rewrote every pre-filled field,
    overwriting ModifyDate and the XMP dates with the capture date."""
    from conftest import exiftool_write

    exiftool_write(rich_jpg, "-ModifyDate=2020:05:05 05:05:05", "-XMP-xmp:CreateDate=2019:01:01 01:01:01")
    before = safe_run_exiftool(rich_jpg)

    write_metadata_to_original(rich_jpg, {"title": "New"})

    after = safe_run_exiftool(rich_jpg)
    assert after["XMP:Title"] == "New"
    volatile = ("File:", "ExifTool:", "XMP:XMPToolkit")
    changed = {
        key for key in set(before) | set(after)
        if before.get(key) != after.get(key) and not key.startswith(volatile)
    }
    assert changed == {"XMP:Title"}


@needs_exiftool
def test_keywords_are_replaced_not_duplicated(rich_jpg: Path) -> None:
    """Regression: every save appended the keywords again."""
    for _ in range(2):
        write_metadata_to_original(rich_jpg, {"keywords": ["alpha", "gamma"]})
    assert safe_run_exiftool(rich_jpg)["XMP:Subject"] == ["alpha", "gamma"]


@needs_exiftool
def test_empty_value_removes_field(rich_jpg: Path) -> None:
    write_metadata_to_original(
        rich_jpg,
        {"camera_make": "", "gps_latitude": "", "gps_longitude": "", "gps_altitude": "",
         "keywords": [], "date_taken": ""},
    )
    raw = safe_run_exiftool(rich_jpg)
    for key in ("EXIF:Make", "EXIF:GPSLatitude", "EXIF:GPSLatitudeRef", "EXIF:GPSLongitude",
                "Composite:GPSLatitude", "EXIF:GPSAltitude", "XMP:Subject", "EXIF:DateTimeOriginal"):
        assert key not in raw, key
    assert raw["EXIF:Model"] == "TestModel X1"


@needs_exiftool
@pytest.mark.parametrize("fields", [{"gps_latitude": "nan"}, {"date_taken": "2024:13:45 03:04:05"}, {}])
def test_invalid_input_never_touches_file(rich_jpg: Path, kai_home: Path, fields: dict) -> None:
    """Regression: "nan" passed validation; ExifTool then rejected the value
    but still rewrote the hemisphere reference, moving the photo north."""
    before = sha256_file(rich_jpg)
    with pytest.raises(RuntimeError):
        write_metadata_to_original(rich_jpg, fields)
    assert sha256_file(rich_jpg) == before
    assert not (kai_home / "backups").exists(), "no backup is needed when nothing is written"


@needs_exiftool
def test_tricky_values_are_stored_literally(rich_jpg: Path, tmp_path: Path) -> None:
    secret = tmp_path / "secret.txt"
    secret.write_text("TOP SECRET")
    tricky = f"<={secret}"
    write_metadata_to_original(rich_jpg, {"title": tricky, "creator": "-all="})
    raw = safe_run_exiftool(rich_jpg)
    assert raw["XMP:Title"] == tricky
    assert raw["XMP:Creator"] == "-all="
    assert raw["EXIF:Make"] == "TestMake"


@needs_exiftool
def test_unsupported_format_reports_error_and_keeps_file(tmp_path: Path) -> None:
    path = make_image(tmp_path / "pic.bmp")
    before = sha256_file(path)
    with pytest.raises(RuntimeError, match="not yet supported"):
        write_metadata_to_original(path, {"title": "x"})
    assert sha256_file(path) == before


@needs_exiftool
def test_restores_backup_when_result_is_unreadable(rich_jpg: Path, monkeypatch) -> None:
    before = sha256_file(rich_jpg)

    def unreadable(_path: Path) -> dict:
        raise RuntimeError("simulated corruption")

    monkeypatch.setattr(metadata_writer, "safe_run_exiftool", unreadable)
    with pytest.raises(RuntimeError, match="simulated corruption"):
        write_metadata_to_original(rich_jpg, {"title": "x"})
    assert sha256_file(rich_jpg) == before


def test_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        write_metadata_to_original(tmp_path / "nope.jpg", {"title": "x"})
