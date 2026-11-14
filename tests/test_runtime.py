from __future__ import annotations

import os
from pathlib import Path

import pytest
from conftest import make_image, needs_exiftool

from kai_metadata_inspector.core.exiftool_runner import read_metadata_batch, safe_run_exiftool
from kai_metadata_inspector.core.metadata_writer import write_metadata_to_original
from kai_metadata_inspector.core.runtime import build_argument_file, use_argument_file


def test_argument_file_is_used_on_windows_or_when_forced(monkeypatch) -> None:
    monkeypatch.delenv("KAI_EXIFTOOL_ARGFILE", raising=False)
    assert use_argument_file() is (os.name == "nt")
    monkeypatch.setenv("KAI_EXIFTOOL_ARGFILE", "1")
    assert use_argument_file() is True
    monkeypatch.setenv("KAI_EXIFTOOL_ARGFILE", "0")
    assert use_argument_file() is False


def test_argument_file_makes_paths_absolute_and_keeps_values_literal() -> None:
    text = build_argument_file(["-XMP-dc:Title=#Zoë ©", "--", "#photo.jpg"])
    lines = text.splitlines()
    assert lines[:2] == ["-charset", "filename=UTF8"]
    assert lines[2:4] == ["-XMP-dc:Title=#Zoë ©", "--"]
    assert os.path.isabs(lines[4]) and lines[4].endswith("#photo.jpg")
    assert build_argument_file(["-XMP-dc:Description=two\nlines"]) is None


@needs_exiftool
@pytest.mark.parametrize("argfile", ["0", "1"])
def test_non_ascii_values_and_awkward_file_names(tmp_path: Path, monkeypatch, argfile: str) -> None:
    """Regression (Windows): metadata values were passed on the command line
    in the ANSI code page, corrupting text such as "Zoë" and "©". With the
    argument file forced on, this exercises the Windows code path anywhere."""
    monkeypatch.setenv("KAI_EXIFTOOL_ARGFILE", argfile)
    monkeypatch.chdir(tmp_path)
    names = ["Zoë ü 写真.jpg", "#hash.jpg", "-dash.jpg"]
    if os.name != "nt":
        names.append(" leading space.jpg")  # not a valid Windows file name

    for name in names:
        path = make_image(Path(name))  # relative on purpose
        result = write_metadata_to_original(path, {"creator": "Zoë Ångström", "rights": "© 2026 写真", "title": "#1 <=x"})
        assert result["unverified_fields"] == [], name
        raw = safe_run_exiftool(path)
        assert raw["XMP:Creator"] == "Zoë Ångström"
        assert raw["XMP:Rights"] == "© 2026 写真"
        assert raw["XMP:Title"] == "#1 <=x"
        assert raw["File:FileName"] == name

    found = read_metadata_batch([Path(name) for name in names])
    assert all(isinstance(found[Path(name)], dict) for name in names)
