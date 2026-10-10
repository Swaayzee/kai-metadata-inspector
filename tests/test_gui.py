from __future__ import annotations

from PySide6.QtWidgets import QApplication

from kai_metadata_inspector.ui.dialogs import CleaningComparisonDialog
from kai_metadata_inspector.ui.main_window import MainWindow
from kai_metadata_inspector.ui.workers import TaskWorker


def test_window_constructs() -> None:
    _app = QApplication.instance() or QApplication([])
    window = MainWindow()
    assert window.windowTitle() == "Kai Metadata Inspector 2.0.0"
    assert window.table.columnCount() == 3
    assert window.progress_bar.isHidden()
    window.close()


def test_cleaning_comparison_constructs() -> None:
    _app = QApplication.instance() or QApplication([])
    dialog = CleaningComparisonDialog({
        "before_tag_count": 12,
        "after_tag_count": 4,
        "removed_tag_count": 8,
        "original_unchanged": True,
        "removed_keys": ["EXIF:GPSLatitude"],
        "remaining_keys": ["File:FileType"],
        "output_path": "/tmp/photo-clean.jpg",
    })
    assert dialog.windowTitle() == "Cleaning comparison"
    assert dialog.inspect_requested is False
    dialog.close()


def test_overlapping_jobs_keep_controls_busy_until_all_finish() -> None:
    _app = QApplication.instance() or QApplication([])
    window = MainWindow()
    first = TaskWorker(lambda: None)
    second = TaskWorker(lambda: None)

    window._job_started(first)
    window._job_started(second)
    window._job_finished(first)
    assert window.open_button.isEnabled() is False

    window._job_finished(second)
    assert window.open_button.isEnabled() is True
    window.close()
