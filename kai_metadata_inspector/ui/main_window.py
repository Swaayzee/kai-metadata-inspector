from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path
from typing import Any, Callable

from PIL import Image, ImageOps
from PySide6.QtCore import QRunnable, Qt, QThreadPool
from PySide6.QtGui import QAction, QColor, QDesktopServices, QFont, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from kai_metadata_inspector.config import APP_NAME, APP_VERSION, SUPPORTED_EXTENSIONS, outputs_dir
from kai_metadata_inspector.core.analyzer import build_analysis
from kai_metadata_inspector.core.cleaner import clean_metadata_copy
from kai_metadata_inspector.core.exiftool_runner import get_exiftool_version, safe_run_exiftool
from kai_metadata_inspector.core.folder_summary import (
    build_folder_summary,
    build_folder_summary_csv,
    find_supported_files,
)
from kai_metadata_inspector.core.metadata_writer import write_metadata_to_original
from kai_metadata_inspector.core.report_builder import build_report
from kai_metadata_inspector.core.runtime import runtime_diagnostics
from kai_metadata_inspector.ui.dialogs import CleaningComparisonDialog, MetadataEditorDialog
from kai_metadata_inspector.ui.styles import APP_STYLESHEET
from kai_metadata_inspector.ui.utils import display_value, json_safe, now_stamp
from kai_metadata_inspector.ui.workers import CancellableWorker, TaskWorker

try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
except Exception:
    pass


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.current_path: Path | None = None
        self.current_raw: dict[str, Any] = {}
        self.current_analysis: dict[str, Any] = {}
        self.folder_path: Path | None = None
        self.folder_files: list[Path] = []
        self.folder_summary: dict[str, Any] | None = None
        self._preview: QPixmap | None = None
        self.thread_pool = QThreadPool.globalInstance()
        self._active_jobs = 0
        self._workers: set[QRunnable] = set()
        self._folder_worker: CancellableWorker | None = None
        self._pending_folder_scan = False

        self.setWindowTitle(f"{APP_NAME} {APP_VERSION}")
        self.resize(1320, 820)
        self.setMinimumSize(920, 600)
        self.setAcceptDrops(True)
        self._build_ui()
        self._build_menu()
        self._apply_style()
        self._set_busy(False)
        self.statusBar().showMessage("Ready — open or drag a file to inspect it locally")

    def _button(self, text: str, callback: Callable[[], None], primary: bool = False) -> QPushButton:
        button = QPushButton(text)
        if primary:
            button.setObjectName("PrimaryButton")
        button.clicked.connect(callback)
        return button

    def _build_ui(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(9)

        header = QHBoxLayout()
        title = QLabel("KAI // METADATA INSPECTOR")
        title.setObjectName("TitleLabel")
        self.risk_label = QLabel("NO FILE")
        self.risk_label.setObjectName("RiskLabel")
        header.addWidget(title)
        header.addStretch()
        header.addWidget(self.risk_label)
        layout.addLayout(header)

        actions = QHBoxLayout()
        self.open_button = self._button("OPEN FILE", self.open_file_dialog, True)
        self.folder_button = self._button("OPEN FOLDER", self.open_folder_dialog)
        self.clean_button = self._button("CREATE CLEAN COPY", self.create_clean_copy)
        self.edit_button = self._button("EDIT METADATA", self.edit_metadata)
        self.export_button = self._button("EXPORT", self.export_menu)
        self.outputs_button = self._button("OUTPUTS", self.open_outputs)
        for button in (self.open_button, self.folder_button, self.clean_button, self.edit_button, self.export_button, self.outputs_button):
            actions.addWidget(button)
        actions.addStretch()
        layout.addLayout(actions)

        self.path_label = QLabel("NO FILE SELECTED")
        self.path_label.setObjectName("PathLabel")
        self.path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.path_label)

        progress_row = QHBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("%p%")
        self.cancel_button = QPushButton("CANCEL SCAN")
        self.cancel_button.clicked.connect(self.cancel_folder_scan)
        progress_row.addWidget(self.progress_bar, 1)
        progress_row.addWidget(self.cancel_button)
        layout.addLayout(progress_row)
        self.progress_bar.hide()
        self.cancel_button.hide()

        split = QSplitter(Qt.Orientation.Horizontal)
        split.setChildrenCollapsible(False)
        layout.addWidget(split, 1)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 6, 0)
        self.preview = QLabel("DROP AN IMAGE HERE")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumSize(340, 340)
        self.preview.setFrameShape(QFrame.Shape.StyledPanel)
        left_layout.addWidget(self.preview, 3)
        self.findings = QPlainTextEdit()
        self.findings.setReadOnly(True)
        self.findings.setMaximumHeight(150)
        self.findings.setPlaceholderText("Privacy findings will appear here")
        left_layout.addWidget(self.findings)
        self.file_list = QListWidget()
        self.file_list.setMaximumHeight(190)
        self.file_list.itemActivated.connect(self._activate_folder_item)
        self.file_list.itemClicked.connect(self._activate_folder_item)
        left_layout.addWidget(self.file_list)
        self.file_list.hide()

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(6, 0, 0, 0)
        search_row = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Filter metadata by group, field, or value…")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._filter_table)
        self.count_label = QLabel("0 TAGS")
        self.count_label.setObjectName("CountLabel")
        search_row.addWidget(self.search, 1)
        search_row.addWidget(self.count_label)
        right_layout.addLayout(search_row)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["GROUP", "FIELD", "VALUE"])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().hide()
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        right_layout.addWidget(self.table, 1)
        split.addWidget(left)
        split.addWidget(right)
        split.setSizes([440, 850])

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("File")
        for label, slot in (("Open file", self.open_file_dialog), ("Open folder", self.open_folder_dialog),
                            ("Create clean copy", self.create_clean_copy), ("Export", self.export_menu)):
            action = QAction(label, self)
            action.triggered.connect(slot)
            file_menu.addAction(action)
        file_menu.addSeparator()
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)
        help_menu = self.menuBar().addMenu("Help")
        diagnostics = QAction("Diagnostics", self)
        diagnostics.triggered.connect(self.show_diagnostics)
        about = QAction("About", self)
        about.triggered.connect(self.show_about)
        help_menu.addActions([diagnostics, about])

    def _apply_style(self) -> None:
        QApplication.instance().setFont(QFont("DejaVu Sans Mono", 10))
        self.setStyleSheet(APP_STYLESHEET)

    def _set_busy(self, busy: bool) -> None:
        for widget in (self.open_button, self.folder_button, self.clean_button, self.edit_button, self.export_button):
            widget.setEnabled(not busy)
        if busy:
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        elif QApplication.overrideCursor() is not None:
            QApplication.restoreOverrideCursor()

    def _job_started(self, worker: QRunnable) -> None:
        self._workers.add(worker)
        self._active_jobs += 1
        if self._active_jobs == 1:
            self._set_busy(True)

    def _job_finished(self, worker: QRunnable) -> None:
        self._workers.discard(worker)
        self._active_jobs = max(0, self._active_jobs - 1)
        if self._active_jobs == 0:
            self._set_busy(False)

    def _run(
        self,
        task: Callable[[], Any],
        success: Callable[[Any], None],
        label: str,
        error: Callable[[str], None] | None = None,
    ) -> None:
        self.statusBar().showMessage(label)
        worker = TaskWorker(task)
        self._job_started(worker)
        worker.signals.result.connect(success)
        worker.signals.error.connect(error or self._show_error)
        worker.signals.finished.connect(lambda current=worker: self._job_finished(current))
        self.thread_pool.start(worker)

    def _show_error(self, message: str) -> None:
        QMessageBox.critical(self, "Kai Metadata Inspector", message)
        self.statusBar().showMessage("Operation failed")

    def open_file_dialog(self) -> None:
        pattern = " ".join(f"*{extension}" for extension in sorted(SUPPORTED_EXTENSIONS))
        filename, _ = QFileDialog.getOpenFileName(self, "Open file", str(Path.home()), f"Supported files ({pattern});;All files (*)")
        if filename:
            self.load_file(Path(filename))

    def load_file(self, path: Path, *, start_folder_scan: bool = False) -> None:
        path = path.expanduser().resolve()
        if not path.is_file():
            self._show_error(f"File does not exist: {path}")
            return
        self.current_path = path
        self._pending_folder_scan = start_folder_scan
        self.path_label.setText(str(path))
        self._load_preview(path)
        self._run(
            lambda: self._inspect(path),
            lambda result, source=path: self._inspection_ready(result, source),
            f"Inspecting {path.name}…",
            lambda message, source=path: self._inspection_failed(message, source),
        )

    @staticmethod
    def _inspect(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
        raw = safe_run_exiftool(path)
        return raw, build_analysis(path, raw, get_exiftool_version())

    def _inspection_failed(self, message: str, source: Path) -> None:
        if source != self.current_path:
            return
        self._show_error(message)
        if self._pending_folder_scan:
            self._pending_folder_scan = False
            self._start_folder_scan()

    def _inspection_ready(
        self,
        result: tuple[dict[str, Any], dict[str, Any]],
        source: Path | None = None,
    ) -> None:
        if source is not None and source != self.current_path:
            return
        self.current_raw, self.current_analysis = result
        self._populate_table(self.current_raw)
        flags = self.current_analysis["flags"]
        level = flags["risk_level"]
        self.risk_label.setText(f"{level} // {flags['risk_points']} PTS")
        colors = {"LOW": "#69f0ae", "MEDIUM": "#ffe66d", "HIGH": "#ff9b42", "CRITICAL": "#ff4d6d"}
        self.risk_label.setStyleSheet(f"color: {colors.get(level, '#8cf7ff')}; border: 1px solid {colors.get(level, '#31565c')}; padding: 6px 10px; font-weight: 700;")
        self.findings.setPlainText("\n".join(f"• {item}" for item in self.current_analysis.get("interesting", [])))
        self.statusBar().showMessage(f"Inspection complete — {len(self.current_raw)} tags")
        if self._pending_folder_scan:
            self._pending_folder_scan = False
            self._start_folder_scan()

    def _populate_table(self, raw: dict[str, Any]) -> None:
        rows = []
        for key, value in sorted(raw.items(), key=lambda item: item[0].lower()):
            group, _, field = key.partition(":")
            rows.append((group if field else "Metadata", field or group, self._display_value(value)))
        self.table.setRowCount(len(rows))
        for row, values in enumerate(rows):
            for column, text in enumerate(values):
                item = QTableWidgetItem(text)
                item.setToolTip(text)
                if column == 0:
                    item.setForeground(QColor("#8cf7ff"))
                self.table.setItem(row, column, item)
        self.count_label.setText(f"{len(rows)} TAGS")
        self._filter_table(self.search.text())

    @staticmethod
    def _display_value(value: Any) -> str:
        return display_value(value)

    def _filter_table(self, query: str) -> None:
        needle = query.casefold().strip()
        visible = 0
        for row in range(self.table.rowCount()):
            haystack = " ".join(self.table.item(row, col).text() for col in range(3)).casefold()
            show = not needle or needle in haystack
            self.table.setRowHidden(row, not show)
            visible += int(show)
        self.count_label.setText(f"{visible}/{self.table.rowCount()} TAGS" if needle else f"{self.table.rowCount()} TAGS")

    def _load_preview(self, path: Path) -> None:
        self._preview = None
        try:
            with Image.open(path) as image:
                image = ImageOps.exif_transpose(image)
                image.thumbnail((1600, 1200))
                if image.mode not in ("RGB", "RGBA"):
                    image = image.convert("RGB")
                buffer = BytesIO()
                image.save(buffer, "PNG")
            pixmap = QPixmap()
            if pixmap.loadFromData(buffer.getvalue(), "PNG"):
                self._preview = pixmap
        except Exception:
            pixmap = QPixmap(str(path))
            if not pixmap.isNull():
                self._preview = pixmap
        self._scale_preview()

    def _scale_preview(self) -> None:
        if self._preview:
            self.preview.setText("")
            self.preview.setPixmap(self._preview.scaled(self.preview.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        else:
            self.preview.setPixmap(QPixmap())
            self.preview.setText(
                "PREVIEW UNAVAILABLE\nMETADATA CAN STILL BE INSPECTED"
                if self.current_path else "DROP AN IMAGE HERE"
            )

    def resizeEvent(self, event: Any) -> None:
        super().resizeEvent(event)
        self._scale_preview()

    def open_folder_dialog(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Open folder", str(Path.home()))
        if folder:
            self.load_folder(Path(folder))

    def load_folder(self, folder: Path) -> None:
        self.cancel_folder_scan()
        self._pending_folder_scan = False
        self.folder_path = folder.expanduser().resolve()
        try:
            self.folder_files = find_supported_files(self.folder_path)
        except Exception as exc:
            self._show_error(str(exc))
            return
        self.file_list.clear()
        for path in self.folder_files:
            item = QListWidgetItem(path.name)
            item.setData(Qt.ItemDataRole.UserRole, str(path))
            self.file_list.addItem(item)
        self.file_list.setVisible(bool(self.folder_files))
        if not self.folder_files:
            self.statusBar().showMessage("No supported files in this folder")
            return
        self.folder_summary = None
        self.load_file(self.folder_files[0], start_folder_scan=True)

    def _start_folder_scan(self) -> None:
        if not self.folder_path or not self.folder_files:
            return
        folder_path = self.folder_path
        files = list(self.folder_files)
        exiftool_version = get_exiftool_version()

        worker = CancellableWorker(
            lambda progress, cancelled: build_folder_summary(
                folder_path,
                files,
                exiftool_version,
                progress_callback=progress,
                should_cancel=cancelled,
            )
        )
        self._folder_worker = worker
        self._job_started(worker)
        self.progress_bar.setRange(0, len(files))
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat(f"0/{len(files)}")
        self.progress_bar.show()
        self.cancel_button.setEnabled(True)
        self.cancel_button.show()
        worker.signals.progress.connect(
            lambda current, total, filename, scan_worker=worker: self._folder_progress(
                scan_worker, current, total, filename
            )
        )
        worker.signals.result.connect(
            lambda result, source=folder_path, scan_worker=worker: self._folder_scan_ready(
                scan_worker, result, source
            )
        )
        worker.signals.error.connect(
            lambda message, scan_worker=worker: self._folder_scan_error(scan_worker, message)
        )
        worker.signals.finished.connect(lambda current=worker: self._folder_scan_finished(current))
        self.statusBar().showMessage(f"Scanning {len(files)} files in background…")
        self.thread_pool.start(worker)

    def _folder_progress(
        self,
        worker: CancellableWorker,
        current: int,
        total: int,
        filename: str,
    ) -> None:
        if self._folder_worker is not worker:
            return
        self.progress_bar.setRange(0, max(1, total))
        self.progress_bar.setValue(current)
        self.progress_bar.setFormat(f"{current}/{total}  {filename}")

    def cancel_folder_scan(self) -> None:
        if self._folder_worker:
            self._folder_worker.cancel()
            self.cancel_button.setEnabled(False)
            self.statusBar().showMessage("Cancelling folder scan after the current file…")

    def _folder_scan_finished(self, worker: CancellableWorker) -> None:
        if self._folder_worker is worker:
            self._folder_worker = None
            self.cancel_button.setEnabled(True)
            self.cancel_button.hide()
            self.progress_bar.hide()
        self._job_finished(worker)

    def _folder_scan_error(self, worker: CancellableWorker, message: str) -> None:
        if self._folder_worker is worker:
            self._show_error(message)

    def _activate_folder_item(self, item: QListWidgetItem) -> None:
        self.load_file(
            Path(item.data(Qt.ItemDataRole.UserRole)),
            start_folder_scan=self._pending_folder_scan,
        )

    def _folder_scan_ready(
        self,
        worker: CancellableWorker,
        result: tuple[dict, str],
        source: Path | None = None,
    ) -> None:
        if self._folder_worker is not worker or (source is not None and source != self.folder_path):
            return
        self.folder_summary, _report = result
        if self.folder_summary.get("cancelled"):
            self.statusBar().showMessage(
                f"Folder scan cancelled — {self.folder_summary['scanned_ok']} file(s) completed"
            )
        else:
            self.statusBar().showMessage(
                f"Folder scan complete — {self.folder_summary['scanned_ok']} inspected, "
                f"{self.folder_summary['scan_errors']} errors"
            )

    def create_clean_copy(self) -> None:
        if not self.current_path:
            QMessageBox.information(self, APP_NAME, "Open a file first.")
            return
        source = self.current_path
        default = outputs_dir() / f"{source.stem}_clean_{now_stamp()}{source.suffix}"
        filename, _ = QFileDialog.getSaveFileName(self, "Save clean copy", str(default), "All files (*)")
        if not filename:
            return
        destination = Path(filename)
        self._run(lambda: clean_metadata_copy(source, destination), self._clean_ready, "Creating and verifying clean copy…")

    def _clean_ready(self, result: dict[str, Any]) -> None:
        self.statusBar().showMessage(f"Clean copy verified — {result['removed_tag_count']} tags removed")
        comparison = CleaningComparisonDialog(result, self)
        comparison.exec()
        if comparison.inspect_requested:
            self.load_file(Path(result["output_path"]))

    def edit_metadata(self) -> None:
        if not self.current_path or not self.current_analysis:
            QMessageBox.information(self, APP_NAME, "Open and inspect a file first.")
            return
        initial = {
            "camera_make": self.current_analysis["device"]["Make"].replace("Not found", ""),
            "camera_model": self.current_analysis["device"]["Model"].replace("Not found", ""),
            "lens_make": self.current_analysis["device"]["Lens make"].replace("Not found", ""),
            "lens_model": self.current_analysis["device"]["Lens model"].replace("Not found", ""),
            "gps_latitude": self.current_analysis["flags"]["gps_latitude"].replace("Not found", ""),
            "gps_longitude": self.current_analysis["flags"]["gps_longitude"].replace("Not found", ""),
            "gps_altitude": "", "date_taken": self.current_analysis["time"]["Date/time original"].replace("Not found", ""),
        }
        dialog = MetadataEditorDialog(initial, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        values = dialog.values()
        if not any(values.values()):
            return
        path = self.current_path
        self._run(lambda: write_metadata_to_original(path, values), self._edit_ready, "Writing metadata with recovery backup…")

    def _edit_ready(self, result: dict[str, Any]) -> None:
        self.statusBar().showMessage("Metadata saved; recovery backup created")
        QMessageBox.information(self, "Metadata saved", f"File updated.\n\nRecovery backup:\n{result['backup_path']}")
        if self.current_path:
            self.load_file(self.current_path)

    def export_menu(self) -> None:
        if not self.current_path or not self.current_analysis:
            QMessageBox.information(self, APP_NAME, "Open and inspect a file first.")
            return
        box = QMessageBox(self)
        box.setWindowTitle("Export")
        box.setText("Choose an export format. Reports can contain sensitive metadata.")
        txt = box.addButton("TXT report", QMessageBox.ButtonRole.ActionRole)
        jsn = box.addButton("Raw JSON", QMessageBox.ButtonRole.ActionRole)
        csv = box.addButton("Folder CSV", QMessageBox.ButtonRole.ActionRole)
        box.addButton(QMessageBox.StandardButton.Cancel)
        box.exec()
        if box.clickedButton() == txt:
            self._export_text()
        elif box.clickedButton() == jsn:
            self._export_json()
        elif box.clickedButton() == csv:
            self._export_folder_csv()

    def _choose_export(self, filename: str, file_filter: str) -> Path | None:
        selected, _ = QFileDialog.getSaveFileName(self, "Export", str(outputs_dir() / filename), file_filter)
        return Path(selected) if selected else None

    def _export_text(self) -> None:
        destination = self._choose_export(f"{self.current_path.stem}_metadata_{now_stamp()}.txt", "Text (*.txt)")
        if destination:
            destination.write_text(build_report(self.current_path, self.current_analysis), encoding="utf-8")
            self.statusBar().showMessage(f"Exported {destination}")

    def _export_json(self) -> None:
        destination = self._choose_export(f"{self.current_path.stem}_metadata_{now_stamp()}.json", "JSON (*.json)")
        if destination:
            destination.write_text(json.dumps(json_safe(self.current_raw), indent=2, ensure_ascii=False), encoding="utf-8")
            self.statusBar().showMessage(f"Exported {destination}")

    def _export_folder_csv(self) -> None:
        if not self.folder_summary:
            QMessageBox.information(self, APP_NAME, "Open a folder and wait for its scan to finish first.")
            return
        destination = self._choose_export(f"folder_summary_{now_stamp()}.csv", "CSV (*.csv)")
        if destination:
            destination.write_text(build_folder_summary_csv(self.folder_summary), encoding="utf-8-sig")
            self.statusBar().showMessage(f"Exported {destination}")

    def open_outputs(self) -> None:
        QDesktopServices.openUrl(outputs_dir().as_uri())

    def show_diagnostics(self) -> None:
        diagnostics = runtime_diagnostics()
        QMessageBox.information(self, "Diagnostics", "\n".join(f"{key}: {value}" for key, value in diagnostics.items()))

    def show_about(self) -> None:
        QMessageBox.information(
            self, f"About {APP_NAME}",
            f"{APP_NAME} {APP_VERSION}\n\nOffline metadata inspection, privacy analysis, verified cleaning, and careful editing.\n\nNo telemetry. No uploads."
        )

    def dragEnterEvent(self, event: Any) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: Any) -> None:
        paths = [Path(url.toLocalFile()) for url in event.mimeData().urls() if url.isLocalFile()]
        if not paths:
            return
        if paths[0].is_dir():
            self.load_folder(paths[0])
        else:
            self.load_file(paths[0])


MetadataInspectorWindow = MainWindow
KaiMetadataInspectorWindow = MainWindow
