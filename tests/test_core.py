from __future__ import annotations

import json
from pathlib import Path

import pytest

from kai_metadata_inspector.config import outputs_dir
from kai_metadata_inspector.core.analyzer import build_analysis, signed_coordinate
from kai_metadata_inspector.core.folder_summary import build_folder_summary
from kai_metadata_inspector.ui.utils import json_safe


def test_signed_gps_uses_hemisphere_reference() -> None:
    raw = {"GPS:GPSLatitude": 33.9, "GPS:GPSLatitudeRef": "S", "GPS:GPSLongitude": 151.2, "GPS:GPSLongitudeRef": "W"}
    assert signed_coordinate(raw, "lat") == "-33.9"
    assert signed_coordinate(raw, "lon") == "-151.2"


def test_composite_signed_gps_is_not_double_negated() -> None:
    raw = {"Composite:GPSLatitude": -33.9, "GPS:GPSLatitudeRef": "S"}
    assert signed_coordinate(raw, "lat") == "-33.9"


def test_analysis_scores_sensitive_metadata(tmp_path: Path) -> None:
    image = tmp_path / "sample.jpg"
    image.write_bytes(b"sample")
    raw = {"Composite:GPSLatitude": 51.5, "Composite:GPSLongitude": -0.12, "EXIF:SerialNumber": "private"}
    analysis = build_analysis(image, raw, "test")
    assert analysis["flags"]["gps_found"] is True
    assert analysis["flags"]["serial_found"] is True
    assert analysis["flags"]["risk_level"] == "HIGH"


def test_json_safe_serializes_paths_and_bytes() -> None:
    value = {"path": Path("photo.jpg"), "payload": b"123", "items": (Path("a"),)}
    encoded = json.dumps(json_safe(value))
    assert "photo.jpg" in encoded
    assert "binary data: 3 bytes" in encoded


def test_outputs_directory_honors_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KAI_METADATA_HOME", str(tmp_path))
    assert outputs_dir() == tmp_path / "outputs"
    assert outputs_dir().is_dir()


def test_folder_summary_reports_progress_and_can_cancel(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    files = [tmp_path / f"photo-{index}.jpg" for index in range(3)]
    for path in files:
        path.write_bytes(b"sample")

    monkeypatch.setattr(
        "kai_metadata_inspector.core.folder_summary.safe_run_exiftool",
        lambda _path: {"EXIF:Make": "Kai"},
    )
    progress: list[tuple[int, int, str]] = []
    summary, report = build_folder_summary(
        tmp_path,
        files,
        "test",
        progress_callback=lambda current, total, name: progress.append((current, total, name)),
        should_cancel=lambda: len(progress) == 1,
    )

    assert summary["cancelled"] is True
    assert summary["scanned_ok"] == 1
    assert progress == [(1, 3, "photo-0.jpg")]
    assert "Cancelled: Yes" in report
