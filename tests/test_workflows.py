"""End-to-end GUI workflows, run headless with Qt's offscreen platform."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest
from conftest import exiftool_write, make_image, needs_exiftool, pixels
from PySide6.QtWidgets import QApplication, QDialog, QFileDialog, QMessageBox

from kai_metadata_inspector.core.cleaner import sha256_file
from kai_metadata_inspector.core.exiftool_runner import safe_run_exiftool
from kai_metadata_inspector.ui import main_window as mw

pytestmark = needs_exiftool


@pytest.fixture
def window(monkeypatch):
    QApplication.instance() or QApplication([])
    messages: list[tuple[str, str]] = []
    for kind in ("information", "warning", "critical"):
        monkeypatch.setattr(
            QMessageBox, kind,
            staticmethod(lambda _parent, title, text, _kind=kind: messages.append((_kind, f"{title}: {text}"))),
        )
    win = mw.MainWindow()
    win.messages = messages
    win.show()
    yield win
    win.close()


def settle(win: mw.MainWindow, timeout: float = 30.0) -> None:
    """Process events until every background job has finished."""
    deadline = time.monotonic() + timeout
    QApplication.processEvents()
    while win._active_jobs:
        assert time.monotonic() < deadline, "background job did not finish"
        QApplication.processEvents()
        time.sleep(0.005)
    QApplication.processEvents()


def table_rows(win: mw.MainWindow, visible_only: bool = False) -> list[tuple[str, ...]]:
    return [
        tuple(win.table.item(row, col).text() for col in range(3))
        for row in range(win.table.rowCount())
        if not (visible_only and win.table.isRowHidden(row))
    ]


def edit_with(monkeypatch, edits: dict[str, str] | None, seen: dict | None = None) -> None:
    """Replace the editor dialog's exec(): apply ``edits`` and accept, or cancel."""

    def fake_exec(dialog: mw.MetadataEditorDialog) -> QDialog.DialogCode:
        if seen is not None:
            seen.update({key: edit.text() for key, edit in dialog.inputs.items()})
        if edits is None:
            return QDialog.DialogCode.Rejected
        for key, text in edits.items():
            dialog.inputs[key].setText(text)
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(mw.MetadataEditorDialog, "exec", fake_exec)


def test_open_file_shows_metadata_risk_and_preview(window, rich_jpg: Path) -> None:
    window.load_file(rich_jpg)
    settle(window)

    rows = table_rows(window)
    assert ("EXIF", "Make", "TestMake") in rows
    assert ("XMP", "Title", "Test Title") in rows
    assert ("IPTC", "Keywords", "iptc-keyword") in rows
    assert window.risk_label.text() == "CRITICAL // 16 PTS"
    assert "GPS/location metadata is present." in window.findings.toPlainText()
    assert not window.preview.pixmap().isNull()
    assert window.open_button.isEnabled()

    window.search.setText("gps")
    visible = table_rows(window, visible_only=True)
    assert visible and all("gps" in " ".join(row).casefold() for row in visible)


def test_missing_and_undecodable_files(window, tmp_path: Path) -> None:
    window.load_file(tmp_path / "nope.jpg")
    assert window.messages[-1][0] == "critical"

    corrupt = tmp_path / "corrupt.jpg"
    corrupt.write_bytes(b"\xff\xd8\xff\xe1garbage" * 5)
    window.load_file(corrupt)
    settle(window)
    assert "PREVIEW UNAVAILABLE" in window.preview.text()
    assert window.table.rowCount() > 0, "metadata is still shown for a damaged image"


def test_resize_only_rescales_cached_preview(window, rich_jpg: Path, monkeypatch) -> None:
    calls: list[Path] = []
    real = mw.load_preview_image
    monkeypatch.setattr(mw, "load_preview_image", lambda path: calls.append(path) or real(path))
    window.load_file(rich_jpg)
    settle(window)
    for width in (1000, 1100, 1200):
        window.resize(width, 700)
        QApplication.processEvents()
    assert len(calls) == 1
    assert not window.preview.pixmap().isNull()


def test_editor_prefills_and_writes_only_changes(window, rich_jpg: Path, monkeypatch) -> None:
    exiftool_write(rich_jpg, "-ModifyDate=2020:05:05 05:05:05")
    before_pixels = pixels(rich_jpg)
    window.load_file(rich_jpg)
    settle(window)

    seen: dict[str, str] = {}
    edit_with(monkeypatch, {"title": "Edited title", "camera_make": ""}, seen)
    window.edit_metadata()
    settle(window)

    assert seen["title"] == "Test Title"
    assert seen["keywords"] == "alpha, beta"
    assert seen["gps_latitude"] == "-33.5"
    assert seen["gps_altitude"] == "120"

    raw = safe_run_exiftool(rich_jpg)
    assert raw["XMP:Title"] == "Edited title"
    assert "EXIF:Make" not in raw
    # Untouched fields keep their own values (regression: they were rewritten).
    assert raw["EXIF:ModifyDate"] == "2020:05:05 05:05:05"
    assert raw["Composite:GPSLatitude"] == pytest.approx(-33.5)
    assert "XMP:GPSLatitude" not in raw
    assert raw["XMP:Subject"] == ["alpha", "beta"]
    assert pixels(rich_jpg) == before_pixels

    assert window.messages[-1][0] == "information" and "Recovery backup" in window.messages[-1][1]
    assert ("XMP", "Title", "Edited title") in table_rows(window), "table is reloaded from disk"


def test_editor_without_changes_or_cancelled_keeps_file(window, rich_jpg: Path, kai_home: Path, monkeypatch) -> None:
    before = sha256_file(rich_jpg)
    window.load_file(rich_jpg)
    settle(window)

    edit_with(monkeypatch, {})  # Save pressed without editing anything
    window.edit_metadata()
    settle(window)
    assert "No fields were changed" in window.statusBar().currentMessage()

    edit_with(monkeypatch, None)  # Cancel
    window.edit_metadata()
    settle(window)

    assert sha256_file(rich_jpg) == before
    assert not (kai_home / "backups").exists()


def test_editor_rejects_invalid_value_before_writing(window, rich_jpg: Path, monkeypatch) -> None:
    before = sha256_file(rich_jpg)
    window.load_file(rich_jpg)
    settle(window)
    edit_with(monkeypatch, {"gps_latitude": "north"})
    window.edit_metadata()
    settle(window)
    assert window.messages[-1][0] == "warning" and "not modified" in window.messages[-1][1]
    assert sha256_file(rich_jpg) == before


def test_editor_reports_unsupported_file_type(window, tmp_path: Path, monkeypatch) -> None:
    bmp = make_image(tmp_path / "pic.bmp")
    before = sha256_file(bmp)
    window.load_file(bmp)
    settle(window)
    edit_with(monkeypatch, {"title": "x"})
    window.edit_metadata()
    settle(window)
    assert window.messages[-1][0] == "critical" and "not yet supported" in window.messages[-1][1]
    assert sha256_file(bmp) == before
    assert window.open_button.isEnabled(), "controls are usable again after a failed job"


def test_clean_copy_workflow(window, rich_jpg: Path, tmp_path: Path, monkeypatch) -> None:
    destination = tmp_path / "cleaned" / "rich_clean.jpg"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *args, **kwargs: (str(destination), "")))
    shown: list[dict] = []

    def fake_exec(dialog: mw.CleaningComparisonDialog) -> None:
        dialog.inspect_requested = True

    real_init = mw.CleaningComparisonDialog.__init__
    monkeypatch.setattr(
        mw.CleaningComparisonDialog, "__init__",
        lambda dialog, result, parent=None: (shown.append(result), real_init(dialog, result, parent))[1],
    )
    monkeypatch.setattr(mw.CleaningComparisonDialog, "exec", fake_exec)

    before = sha256_file(rich_jpg)
    window.load_file(rich_jpg)
    settle(window)
    window.create_clean_copy()
    settle(window)

    assert sha256_file(rich_jpg) == before
    assert shown[0]["original_unchanged"] is True
    assert shown[0]["sensitive_remaining"] == []
    raw = safe_run_exiftool(destination)
    assert not [key for key in raw if "GPS" in key or key in ("EXIF:Make", "XMP:Title", "IPTC:Keywords")]
    assert pixels(destination) == pixels(rich_jpg)
    # "Inspect cleaned copy" was chosen: the cleaned file is now loaded.
    assert window.current_path == destination.resolve()
    assert window.risk_label.text().startswith("LOW")


def test_folder_scan_export_and_cancel(window, rich_jpg: Path, tmp_path: Path, monkeypatch) -> None:
    folder = tmp_path / "folder"
    folder.mkdir()
    rich_jpg.rename(folder / "b_rich.jpg")
    make_image(folder / "a_plain.png")
    (folder / "c_empty.jpg").write_bytes(b"")

    window.load_folder(folder)
    settle(window)

    assert window.file_list.count() == 3
    assert window.current_path.name == "a_plain.png"
    assert window.folder_summary["scanned_ok"] == 2
    assert window.folder_summary["scan_errors"] == 1
    assert window.progress_bar.isHidden() and window.cancel_button.isHidden()

    csv_path = tmp_path / "summary.csv"
    monkeypatch.setattr(window, "_choose_export", lambda *_args: csv_path)
    window._export_folder_csv()
    assert "b_rich.jpg,CRITICAL" in csv_path.read_text(encoding="utf-8-sig")

    window._activate_folder_item(window.file_list.item(1))
    settle(window)
    assert window.current_path.name == "b_rich.jpg"
    json_path = tmp_path / "raw.json"
    monkeypatch.setattr(window, "_choose_export", lambda *_args: json_path)
    window._export_json()
    assert json.loads(json_path.read_text(encoding="utf-8"))["EXIF:Make"] == "TestMake"

    # An unwritable destination is reported instead of raising inside a Qt slot.
    monkeypatch.setattr(window, "_choose_export", lambda *_args: tmp_path / "missing-dir" / "report.txt")
    window._export_text()
    assert window.messages[-1][0] == "critical" and "Could not save" in window.messages[-1][1]


def test_closing_window_cancels_running_scan(tmp_path: Path, monkeypatch) -> None:
    QApplication.instance() or QApplication([])
    monkeypatch.setattr("kai_metadata_inspector.core.folder_summary.FOLDER_BATCH_SIZE", 1)
    folder = tmp_path / "many"
    folder.mkdir()
    for index in range(40):
        make_image(folder / f"img{index:02}.png", size=(8, 8))

    win = mw.MainWindow()
    win.show()
    win.load_folder(folder)
    deadline = time.monotonic() + 30
    while win._folder_worker is None:
        assert time.monotonic() < deadline
        QApplication.processEvents()
    worker = win._folder_worker

    started = time.monotonic()
    win.close()

    assert worker.is_cancelled()
    assert win.thread_pool.activeThreadCount() == 0, "no job keeps running after the window closes"
    assert time.monotonic() - started < 5
    settle(win)
