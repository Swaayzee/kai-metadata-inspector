from __future__ import annotations

from pathlib import Path

import pytest
from conftest import exiftool_write, make_image, needs_exiftool

from kai_metadata_inspector.core.analyzer import build_analysis
from kai_metadata_inspector.core.exiftool_runner import read_metadata_batch, safe_run_exiftool
from kai_metadata_inspector.core.folder_summary import (
    build_folder_summary,
    build_folder_summary_csv,
    find_supported_files,
)
from kai_metadata_inspector.core.metadata_writer import current_field_values
from kai_metadata_inspector.core.report_builder import build_report

pytestmark = needs_exiftool


def test_reads_exif_xmp_iptc_without_modifying_file(rich_jpg: Path) -> None:
    before = rich_jpg.read_bytes()
    raw = safe_run_exiftool(rich_jpg)
    assert raw["EXIF:Make"] == "TestMake"
    assert raw["EXIF:DateTimeOriginal"] == "2024:01:02 03:04:05"
    assert raw["XMP:Title"] == "Test Title"
    assert raw["XMP:Subject"] == ["alpha", "beta"]
    assert raw["IPTC:Keywords"] == "iptc-keyword"
    assert rich_jpg.read_bytes() == before


def test_filename_starting_with_dash_is_not_an_option(tmp_path: Path, monkeypatch) -> None:
    make_image(tmp_path / "-ver.jpg")
    monkeypatch.chdir(tmp_path)
    assert safe_run_exiftool(Path("-ver.jpg"))["File:FileName"] == "-ver.jpg"


def test_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        safe_run_exiftool(tmp_path / "nope.jpg")


def test_real_file_analysis_finds_gps_time_and_altitude(rich_jpg: Path) -> None:
    """Regression: with ExifTool's -G output GPS tags are in the "EXIF:"
    group, so GPS date/time were never detected and scores were too low."""
    analysis = build_analysis(rich_jpg, safe_run_exiftool(rich_jpg), "test")

    assert float(analysis["location"]["GPS latitude"]) == pytest.approx(-33.5)
    assert float(analysis["location"]["GPS longitude"]) == pytest.approx(-70.25)
    assert float(analysis["location"]["GPS altitude"]) == pytest.approx(120)
    assert analysis["time"]["GPS date stamp"] != "Not found"
    assert analysis["time"]["GPS time stamp"] != "Not found"

    flags = analysis["flags"]
    for flag in ("gps_found", "time_found", "timezone_found", "gps_time_found",
                 "device_found", "serial_found", "owner_found", "software_found"):
        assert flags[flag], flag
    assert flags["risk_points"] == 16
    assert flags["risk_level"] == "CRITICAL"


def test_unsigned_exif_gps_uses_exif_reference() -> None:
    """Regression: the hemisphere reference was only looked up as "GPS:"."""
    from kai_metadata_inspector.core.analyzer import signed_coordinate

    raw = {"EXIF:GPSLatitude": 33.5, "EXIF:GPSLatitudeRef": "S", "EXIF:GPSLongitude": 70.25, "EXIF:GPSLongitudeRef": "W"}
    assert signed_coordinate(raw, "lat") == "-33.5"
    assert signed_coordinate(raw, "lon") == "-70.25"


def test_image_without_metadata_is_low_risk(tmp_path: Path) -> None:
    plain = make_image(tmp_path / "plain.png")
    analysis = build_analysis(plain, safe_run_exiftool(plain), "test")
    assert analysis["flags"]["risk_points"] == 0
    assert analysis["flags"]["risk_level"] == "LOW"
    assert "Raw Metadata" in build_report(plain, analysis)


@pytest.mark.parametrize("suffix", [".jpg", ".png", ".webp", ".tif", ".heic"])
def test_inspect_formats(tmp_path: Path, suffix: str) -> None:
    path = make_image(tmp_path / f"img{suffix}")
    exiftool_write(path, "-Make=TestMake", "-XMP-dc:Title=Hello", "-GPSLatitude=10", "-GPSLatitudeRef=S",
                   "-GPSLongitude=20", "-GPSLongitudeRef=E")
    raw = safe_run_exiftool(path)
    assert raw["EXIF:Make"] == "TestMake"
    assert raw["XMP:Title"] == "Hello"
    values = current_field_values(raw)
    assert float(values["gps_latitude"]) == pytest.approx(-10)
    assert float(values["gps_longitude"]) == pytest.approx(20)


def test_editor_values_reflect_the_file(rich_jpg: Path) -> None:
    """Regression: title, keywords and altitude were never pre-filled."""
    values = current_field_values(safe_run_exiftool(rich_jpg))
    assert values == {
        "title": "Test Title",
        "description": "",
        "creator": "Test Artist",
        "rights": "",
        "keywords": "alpha, beta",
        "camera_make": "TestMake",
        "camera_model": "TestModel X1",
        "lens_make": "",
        "lens_model": "Test 50mm",
        "gps_latitude": "-33.5",
        "gps_longitude": "-70.25",
        "gps_altitude": "120",
        "date_taken": "2024:01:02 03:04:05",
    }


def test_editor_date_drops_timezone_suffix(tmp_path: Path) -> None:
    """Regression: a file whose only date is XMP (with a time zone) pre-filled
    a value the editor itself rejected, so no field could be saved."""
    path = make_image(tmp_path / "xmpdate.jpg")
    exiftool_write(path, "-XMP-photoshop:DateCreated=2024:01:02 03:04:05+01:00")
    assert current_field_values(safe_run_exiftool(path))["date_taken"] == "2024:01:02 03:04:05"


def make_folder(tmp_path: Path, rich_jpg: Path) -> Path:
    folder = tmp_path / "folder"
    folder.mkdir()
    rich_jpg.rename(folder / "b_rich.jpg")
    make_image(folder / "a_plain.png")
    (folder / "c_empty.jpg").write_bytes(b"")
    (folder / "notes.txt").write_text("ignored")
    (folder / "sub").mkdir()
    make_image(folder / "sub" / "nested.jpg")
    return folder


def test_batch_read_reports_every_file(tmp_path: Path, rich_jpg: Path) -> None:
    empty = tmp_path / "empty.jpg"
    empty.write_bytes(b"")
    missing = tmp_path / "missing.jpg"

    found = read_metadata_batch([rich_jpg, empty, missing])

    assert found[rich_jpg]["EXIF:Make"] == "TestMake"
    assert found[rich_jpg]["XMP:Title"] == safe_run_exiftool(rich_jpg)["XMP:Title"]
    assert isinstance(found[empty], str) and "empty" in found[empty].lower()
    assert isinstance(found[missing], str)
    assert read_metadata_batch([]) == {}


def test_folder_summary_with_real_files(tmp_path: Path, rich_jpg: Path) -> None:
    folder = make_folder(tmp_path, rich_jpg)
    files = find_supported_files(folder)
    assert [f.name for f in files] == ["a_plain.png", "b_rich.jpg", "c_empty.jpg"]
    before = {f: f.read_bytes() for f in files}
    progress: list[tuple[int, int, str]] = []

    summary, report = build_folder_summary(
        folder, files, "test", progress_callback=lambda *args: progress.append(args)
    )

    assert summary["scanned_ok"] == 2
    assert summary["scan_errors"] == 1
    assert summary["errors"][0]["file"] == "c_empty.jpg"
    assert summary["gps_count"] == 1
    assert summary["gps_time_count"] == 1
    assert summary["critical_risk"] == 1
    assert summary["low_risk"] == 1
    assert summary["cancelled"] is False
    assert progress == [(1, 3, "a_plain.png"), (2, 3, "b_rich.jpg"), (3, 3, "c_empty.jpg")]
    assert "b_rich.jpg | Risk: CRITICAL" in report
    assert "b_rich.jpg,CRITICAL" in build_folder_summary_csv(summary)
    assert {f: f.read_bytes() for f in files} == before, "scanning must not modify files"


def test_folder_scan_spans_several_batches(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("kai_metadata_inspector.core.folder_summary.FOLDER_BATCH_SIZE", 2)
    folder = tmp_path / "many"
    folder.mkdir()
    for index in range(5):
        make_image(folder / f"img{index}.png", size=(8, 8))
    summary, _report = build_folder_summary(folder, find_supported_files(folder), "test")
    assert summary["scanned_ok"] == 5
    assert [row["file"] for row in summary["file_rows"]] == [f"img{i}.png" for i in range(5)]


def test_batch_matches_windows_style_source_files() -> None:
    """Regression: on Windows ExifTool reports SourceFile with forward
    slashes, so no file matched and every folder scan came back empty."""
    from kai_metadata_inspector.core.exiftool_runner import source_key

    assert source_key(r"C:\Users\Me\Pictures\a.JPG", windows=True) == source_key("C:/Users/Me/Pictures/a.jpg", windows=True)
    assert source_key("/home/me/A.jpg", windows=False) != source_key("/home/me/a.jpg", windows=False)
