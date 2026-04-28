import json
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from kai_metadata_inspector.config import (
    APP_NAME,
    APP_VERSION,
    REPORTS_DIR,
    SUPPORTED_EXTENSIONS,
    PREVIEW_EXTENSIONS,
    MAX_FILE_SIZE_MB_WARNING,
    MAX_PREVIEW_FILE_SIZE_MB,
    MAX_FOLDER_FILES_WARNING,
    MAX_FOLDER_SUMMARY_WARNING,
)
from kai_metadata_inspector.core.exiftool_runner import (
    safe_run_exiftool,
    get_exiftool_version,
)
from kai_metadata_inspector.core.analyzer import (
    build_analysis,
    format_section,
    clean_text,
)
from kai_metadata_inspector.core.report_builder import build_report
from kai_metadata_inspector.core.cleaner import clean_metadata_copy
from kai_metadata_inspector.core.folder_summary import (
    find_supported_files,
    build_folder_summary,
    build_folder_summary_csv,
)



def safe_output_name(name: str) -> str:
    """
    Creates safer output filenames for reports.
    Useful for Linux now and Windows later.
    """

    unsafe_chars = '<>:"/\\|?*'
    cleaned = name

    for char in unsafe_chars:
        cleaned = cleaned.replace(char, "_")

    cleaned = cleaned.strip().replace(" ", "_")

    if not cleaned:
        return "file"

    return cleaned


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.exiftool_version = get_exiftool_version()

        self.current_file: Path | None = None
        self.current_analysis: dict | None = None
        self.current_report: str | None = None
        self.current_pixmap: QPixmap | None = None
        self.raw_metadata_lines: list[str] = []

        self.current_folder: Path | None = None
        self.folder_files: list[Path] = []
        self.folder_summary: dict | None = None
        self.folder_summary_report: str | None = None

        self.setWindowTitle(f"{APP_NAME} — {APP_VERSION}")
        self.resize(1400, 850)

        self.open_button = QPushButton("Open Image / File")
        self.open_folder_button = QPushButton("Open Folder")
        self.scan_summary_button = QPushButton("Scan Folder Summary")
        self.export_button = QPushButton("Export TXT")
        self.export_json_button = QPushButton("Export Raw JSON")
        self.clean_copy_button = QPushButton("Create Clean Copy")
        self.export_summary_button = QPushButton("Export Folder Summary")
        self.export_summary_csv_button = QPushButton("Export Summary CSV")
        self.export_all_txt_button = QPushButton("Export All TXT")
        self.export_all_json_button = QPushButton("Export All JSON")
        self.clear_button = QPushButton("Clear")

        self.scan_summary_button.setEnabled(False)
        self.export_button.setEnabled(False)
        self.export_json_button.setEnabled(False)
        self.clean_copy_button.setEnabled(False)
        self.export_summary_button.setEnabled(False)
        self.export_summary_csv_button.setEnabled(False)
        self.export_all_txt_button.setEnabled(False)
        self.export_all_json_button.setEnabled(False)

        self.file_label = QLabel("Selected file: none")
        self.file_label.setWordWrap(True)

        self.status_label = QLabel("Status: Ready")
        self.status_label.setWordWrap(True)

        self.preview_title = QLabel("Preview")
        self.preview_title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.preview_label = QLabel("No preview loaded")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setWordWrap(True)
        self.preview_label.setMinimumSize(320, 260)
        self.preview_label.setStyleSheet(
            "border: 1px solid #555; border-radius: 8px; padding: 10px;"
        )
        self.preview_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        self.preview_scroll = QScrollArea()
        self.preview_scroll.setWidgetResizable(True)
        self.preview_scroll.setWidget(self.preview_label)

        self.left_info = QTextEdit()
        self.left_info.setReadOnly(True)
        self.left_info.setMaximumHeight(160)

        self.folder_label = QLabel("Folder files: none")
        self.folder_label.setWordWrap(True)

        self.folder_list = QListWidget()
        self.folder_list.setMinimumHeight(160)
        self.folder_list.itemClicked.connect(self.load_folder_item)

        left_panel = QWidget()
        left_layout = QVBoxLayout()
        left_layout.addWidget(self.preview_title)
        left_layout.addWidget(self.preview_scroll)
        left_layout.addWidget(QLabel("Quick File Info"))
        left_layout.addWidget(self.left_info)
        left_layout.addWidget(self.folder_label)
        left_layout.addWidget(self.folder_list)
        left_panel.setLayout(left_layout)

        self.tabs = QTabWidget()

        self.tab_widgets = {}
        for name in [
            "Overview",
            "File",
            "Device",
            "Time",
            "Location",
            "Camera",
            "Software",
            "Privacy",
            "Raw Metadata",
            "Folder Summary",
        ]:
            text_box = QTextEdit()
            text_box.setReadOnly(True)
            text_box.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
            self.tabs.addTab(text_box, name)
            self.tab_widgets[name] = text_box

        self.raw_search = QLineEdit()
        self.raw_search.setPlaceholderText("Search raw metadata tags or values...")
        self.raw_search.textChanged.connect(self.filter_raw_metadata)

        right_panel = QWidget()
        right_layout = QVBoxLayout()
        right_layout.addWidget(self.tabs)
        right_layout.addWidget(QLabel("Raw Metadata Search"))
        right_layout.addWidget(self.raw_search)
        right_panel.setLayout(right_layout)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([480, 920])

        action_button_layout = QHBoxLayout()
        action_button_layout.addWidget(self.open_button)
        action_button_layout.addWidget(self.open_folder_button)
        action_button_layout.addWidget(self.scan_summary_button)
        action_button_layout.addWidget(self.clear_button)
        action_button_layout.addStretch()

        export_button_layout = QHBoxLayout()
        export_button_layout.addWidget(self.export_button)
        export_button_layout.addWidget(self.export_json_button)
        export_button_layout.addWidget(self.clean_copy_button)
        export_button_layout.addWidget(self.export_summary_button)
        export_button_layout.addWidget(self.export_summary_csv_button)
        export_button_layout.addWidget(self.export_all_txt_button)
        export_button_layout.addWidget(self.export_all_json_button)
        export_button_layout.addStretch()

        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setFrameShadow(QFrame.Shadow.Sunken)

        main_layout = QVBoxLayout()
        main_layout.addWidget(QLabel("Actions"))
        main_layout.addLayout(action_button_layout)
        main_layout.addWidget(QLabel("Exports"))
        main_layout.addLayout(export_button_layout)
        main_layout.addWidget(self.file_label)
        main_layout.addWidget(divider)
        main_layout.addWidget(splitter)
        main_layout.addWidget(self.status_label)

        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)

        self.open_button.clicked.connect(self.open_file)
        self.open_folder_button.clicked.connect(self.open_folder)
        self.scan_summary_button.clicked.connect(self.scan_folder_summary)
        self.export_button.clicked.connect(self.export_txt)
        self.export_json_button.clicked.connect(self.export_json)
        self.clean_copy_button.clicked.connect(self.create_clean_copy)
        self.export_summary_button.clicked.connect(self.export_folder_summary)
        self.export_summary_csv_button.clicked.connect(self.export_folder_summary_csv)
        self.export_all_txt_button.clicked.connect(self.export_all_txt_reports)
        self.export_all_json_button.clicked.connect(self.export_all_json_reports)
        self.clear_button.clicked.connect(self.clear_data)

        self.show_startup_info()

    def show_startup_info(self):
        self.status_label.setText(f"Status: Ready | ExifTool version: {self.exiftool_version}")

    def open_file(self):
        file_filter = (
            "Supported files (*.jpg *.jpeg *.png *.webp *.heic *.heif *.tif *.tiff "
            "*.bmp *.gif *.avif *.dng *.cr2 *.cr3 *.nef *.arw *.rw2 *.orf "
            "*.raf *.pef *.srw *.psd *.xmp);;All files (*)"
        )

        selected_file, _ = QFileDialog.getOpenFileName(
            self,
            "Open image or metadata file",
            str(Path.home()),
            file_filter,
        )

        if not selected_file:
            return

        self.load_file(Path(selected_file))

    def open_folder(self):
        selected_folder = QFileDialog.getExistingDirectory(
            self,
            "Open folder containing images",
            str(Path.home()),
        )

        if not selected_folder:
            return

        folder_path = Path(selected_folder)

        try:
            files = find_supported_files(folder_path)
        except Exception as error:
            QMessageBox.critical(self, "Folder error", str(error))
            return

        if not files:
            QMessageBox.information(
                self,
                "No supported files",
                "No supported image/metadata files were found in this folder.",
            )
            self.current_folder = folder_path
            self.folder_files = []
            self.folder_list.clear()
            self.folder_label.setText(f"Folder files: none found in {folder_path}")
            self.scan_summary_button.setEnabled(False)
            self.export_all_txt_button.setEnabled(False)
            self.export_all_json_button.setEnabled(False)
            return

        if len(files) > MAX_FOLDER_FILES_WARNING:
            reply = QMessageBox.question(
                self,
                "Large folder warning",
                (
                    f"This folder contains {len(files)} supported files.\n\n"
                    "v0.7 lists the files but only scans metadata when you click one "
                    "or when you manually click Scan Folder Summary.\n\n"
                    "Do you want to continue?"
                ),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )

            if reply != QMessageBox.StandardButton.Yes:
                return

        self.current_folder = folder_path
        self.folder_files = files
        self.folder_summary = None
        self.folder_summary_report = None
        self.export_summary_button.setEnabled(False)
        self.export_summary_csv_button.setEnabled(False)
        self.export_all_txt_button.setEnabled(False)
        self.export_all_json_button.setEnabled(False)

        self.folder_list.clear()

        for file_path in files:
            item = QListWidgetItem(file_path.name)
            item.setData(Qt.ItemDataRole.UserRole, str(file_path))
            self.folder_list.addItem(item)

        self.folder_label.setText(
            f"Folder files: {len(files)} supported file(s) found in {folder_path}"
        )
        self.scan_summary_button.setEnabled(True)
        self.export_all_txt_button.setEnabled(True)
        self.export_all_json_button.setEnabled(True)
        self.tab_widgets["Folder Summary"].setPlainText(
            "Folder loaded.\n\nClick 'Scan Folder Summary' to analyse all supported files in this folder."
        )
        self.status_label.setText(
            "Status: Folder loaded. Click a file to inspect it or scan folder summary."
        )

        if files:
            self.load_file(files[0])

    def scan_folder_summary(self):
        if not self.current_folder or not self.folder_files:
            QMessageBox.warning(self, "No folder loaded", "Open a folder first.")
            return

        if len(self.folder_files) > MAX_FOLDER_SUMMARY_WARNING:
            reply = QMessageBox.question(
                self,
                "Folder summary warning",
                (
                    f"This will scan metadata from {len(self.folder_files)} file(s).\n\n"
                    "This may take a while and the app may pause during scanning.\n\n"
                    "Do you want to continue?"
                ),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )

            if reply != QMessageBox.StandardButton.Yes:
                return

        try:
            self.status_label.setText("Status: Scanning folder summary...")
            self.tab_widgets["Folder Summary"].setPlainText("Scanning folder summary. Please wait...")
            QApplication.processEvents()

            summary, report = build_folder_summary(
                self.current_folder,
                self.folder_files,
                self.exiftool_version,
            )

            self.folder_summary = summary
            self.folder_summary_report = report

            self.tab_widgets["Folder Summary"].setPlainText(report)
            self.tabs.setCurrentWidget(self.tab_widgets["Folder Summary"])
            self.export_summary_button.setEnabled(True)
            self.export_summary_csv_button.setEnabled(True)

            self.status_label.setText(
                f"Status: Folder summary complete. "
                f"Scanned {summary['scanned_ok']} file(s), {summary['scan_errors']} error(s)."
            )

        except Exception as error:
            QMessageBox.critical(self, "Folder summary error", str(error))
            self.status_label.setText("Status: Error while scanning folder summary.")

    def load_folder_item(self, item: QListWidgetItem):
        file_path_str = item.data(Qt.ItemDataRole.UserRole)

        if not file_path_str:
            return

        self.load_file(Path(file_path_str))

    def load_file(self, file_path: Path):
        if file_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            reply = QMessageBox.question(
                self,
                "Unsupported extension",
                (
                    "This file extension is not on the supported list for Alpha.\n\n"
                    "ExifTool may still be able to read it.\n\n"
                    "Do you want to try anyway?"
                ),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )

            if reply != QMessageBox.StandardButton.Yes:
                return

        try:
            file_size_mb = file_path.stat().st_size / (1024 * 1024)
            if file_size_mb > MAX_FILE_SIZE_MB_WARNING:
                reply = QMessageBox.question(
                    self,
                    "Large file warning",
                    (
                        f"This file is {file_size_mb:.2f} MB.\n\n"
                        "Large or corrupted files may take longer to scan.\n\n"
                        "Do you want to continue?"
                    ),
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )

                if reply != QMessageBox.StandardButton.Yes:
                    return

            self.status_label.setText("Status: Extracting metadata...")
            QApplication.processEvents()

            raw = safe_run_exiftool(file_path)
            analysis = build_analysis(file_path, raw, self.exiftool_version)
            report = build_report(file_path, analysis)

            self.current_file = file_path
            self.current_analysis = analysis
            self.current_report = report

            self.file_label.setText(f"Selected file: {file_path}")
            self.populate_tabs(analysis)
            self.update_left_info(analysis)
            self.load_preview(file_path)

            self.export_button.setEnabled(True)
            self.export_json_button.setEnabled(True)
            self.clean_copy_button.setEnabled(True)
            self.status_label.setText("Status: Metadata extracted successfully.")

        except Exception as error:
            QMessageBox.critical(self, "Error", str(error))
            self.status_label.setText("Status: Error while extracting metadata.")

    def update_left_info(self, analysis: dict):
        quick_info = {
            "File name": analysis["file"]["File name"],
            "File type": analysis["file"]["File type"],
            "Size": analysis["file"]["File size"],
            "Dimensions": f"{analysis['file']['Image width']} x {analysis['file']['Image height']}",
            "Device": analysis["overview"]["Device"],
            "Capture time": analysis["overview"]["Capture time"],
            "Timezone": analysis["overview"]["Timezone"],
            "GPS": analysis["overview"]["GPS"],
            "Privacy risk": analysis["overview"]["Privacy risk"],
            "Risk score": analysis["overview"]["Risk score"],
        }

        self.left_info.setPlainText(format_section("Quick File Info", quick_info))

    def load_preview(self, file_path: Path):
        self.current_pixmap = None

        suffix = file_path.suffix.lower()
        file_size_mb = file_path.stat().st_size / (1024 * 1024)

        if suffix not in PREVIEW_EXTENSIONS:
            self.preview_label.setPixmap(QPixmap())
            self.preview_label.setText(
                "Preview unavailable for this format.\n\n"
                "Metadata extraction still worked.\n\n"
                "Preview support in Alpha:\n"
                "JPG, JPEG, PNG, WEBP, BMP, GIF"
            )
            return

        if file_size_mb > MAX_PREVIEW_FILE_SIZE_MB:
            self.preview_label.setPixmap(QPixmap())
            self.preview_label.setText(
                f"Preview skipped because the file is {file_size_mb:.2f} MB.\n\n"
                "Metadata extraction still worked."
            )
            return

        pixmap = QPixmap(str(file_path))

        if pixmap.isNull():
            self.preview_label.setPixmap(QPixmap())
            self.preview_label.setText(
                "Preview could not be loaded.\n\n"
                "Metadata extraction still worked."
            )
            return

        self.current_pixmap = pixmap
        self.update_preview_size()

    def update_preview_size(self):
        if not self.current_pixmap:
            return

        available_width = max(250, self.preview_scroll.viewport().width() - 20)
        available_height = max(250, self.preview_scroll.viewport().height() - 20)

        scaled = self.current_pixmap.scaled(
            available_width,
            available_height,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

        self.preview_label.setText("")
        self.preview_label.setPixmap(scaled)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_preview_size()

    def populate_tabs(self, analysis: dict):
        self.tab_widgets["Overview"].setPlainText(format_section("Overview", analysis["overview"]))
        self.tab_widgets["File"].setPlainText(format_section("File Information", analysis["file"]))
        self.tab_widgets["Device"].setPlainText(format_section("Device Information", analysis["device"]))
        self.tab_widgets["Time"].setPlainText(format_section("Time Information", analysis["time"]))
        self.tab_widgets["Location"].setPlainText(format_section("Location Information", analysis["location"]))
        self.tab_widgets["Camera"].setPlainText(format_section("Camera Settings", analysis["camera"]))
        self.tab_widgets["Software"].setPlainText(format_section("Software / Editing", analysis["software"]))
        self.tab_widgets["Privacy"].setPlainText(format_section("Privacy Risk", analysis["privacy"]))

        self.raw_metadata_lines = []
        for key in sorted(analysis["raw"].keys()):
            self.raw_metadata_lines.append(f"{key}: {clean_text(analysis['raw'][key])}")

        self.raw_search.clear()
        self.tab_widgets["Raw Metadata"].setPlainText("\n".join(self.raw_metadata_lines))

    def filter_raw_metadata(self):
        search_text = self.raw_search.text().strip().lower()

        if not search_text:
            self.tab_widgets["Raw Metadata"].setPlainText("\n".join(self.raw_metadata_lines))
            return

        filtered = [
            line for line in self.raw_metadata_lines
            if search_text in line.lower()
        ]

        if filtered:
            self.tab_widgets["Raw Metadata"].setPlainText("\n".join(filtered))
        else:
            self.tab_widgets["Raw Metadata"].setPlainText("No matching metadata found.")

    def export_txt(self):
        if not self.current_file or not self.current_report:
            QMessageBox.warning(self, "Nothing to export", "Open a file first.")
            return

        REPORTS_DIR.mkdir(exist_ok=True)

        default_name = f"{self.current_file.stem}_metadata_report.txt"
        default_path = REPORTS_DIR / default_name

        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export TXT report",
            str(default_path),
            "Text files (*.txt);;All files (*)",
        )

        if not save_path:
            return

        try:
            Path(save_path).write_text(self.current_report, encoding="utf-8")
            QMessageBox.information(
                self,
                "Export complete",
                f"Report saved to:\n{save_path}",
            )
            self.status_label.setText(f"Status: TXT report exported to {save_path}")

        except Exception as error:
            QMessageBox.critical(self, "Export error", str(error))
            self.status_label.setText("Status: Error while exporting TXT report.")

    def export_json(self):
        if not self.current_file or not self.current_analysis:
            QMessageBox.warning(self, "Nothing to export", "Open a file first.")
            return

        REPORTS_DIR.mkdir(exist_ok=True)

        default_name = f"{self.current_file.stem}_raw_metadata.json"
        default_path = REPORTS_DIR / default_name

        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export raw JSON metadata",
            str(default_path),
            "JSON files (*.json);;All files (*)",
        )

        if not save_path:
            return

        try:
            raw_metadata = self.current_analysis["raw"]
            Path(save_path).write_text(
                json.dumps(raw_metadata, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            QMessageBox.information(
                self,
                "Export complete",
                f"Raw JSON saved to:\n{save_path}",
            )
            self.status_label.setText(f"Status: Raw JSON exported to {save_path}")

        except Exception as error:
            QMessageBox.critical(self, "Export error", str(error))
            self.status_label.setText("Status: Error while exporting raw JSON.")

    def export_folder_summary(self):
        if not self.folder_summary_report or not self.current_folder:
            QMessageBox.warning(self, "Nothing to export", "Scan folder summary first.")
            return

        REPORTS_DIR.mkdir(exist_ok=True)

        safe_folder_name = self.current_folder.name or "folder"
        default_name = f"{safe_folder_name}_folder_summary_report.txt"
        default_path = REPORTS_DIR / default_name

        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export folder summary report",
            str(default_path),
            "Text files (*.txt);;All files (*)",
        )

        if not save_path:
            return

        try:
            Path(save_path).write_text(self.folder_summary_report, encoding="utf-8")
            QMessageBox.information(
                self,
                "Export complete",
                f"Folder summary saved to:\n{save_path}",
            )
            self.status_label.setText(f"Status: Folder summary exported to {save_path}")

        except Exception as error:
            QMessageBox.critical(self, "Export error", str(error))
            self.status_label.setText("Status: Error while exporting folder summary.")

    def export_folder_summary_csv(self):
        if not self.folder_summary or not self.current_folder:
            QMessageBox.warning(self, "Nothing to export", "Scan folder summary first.")
            return

        REPORTS_DIR.mkdir(exist_ok=True)

        safe_folder_name = self.current_folder.name or "folder"
        default_name = f"{safe_folder_name}_folder_summary.csv"
        default_path = REPORTS_DIR / default_name

        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export folder summary CSV",
            str(default_path),
            "CSV files (*.csv);;All files (*)",
        )

        if not save_path:
            return

        try:
            csv_text = build_folder_summary_csv(self.folder_summary)
            Path(save_path).write_text(csv_text, encoding="utf-8")
            QMessageBox.information(
                self,
                "Export complete",
                f"Folder summary CSV saved to:\n{save_path}",
            )
            self.status_label.setText(f"Status: Folder summary CSV exported to {save_path}")

        except Exception as error:
            QMessageBox.critical(self, "CSV export error", str(error))
            self.status_label.setText("Status: Error while exporting folder summary CSV.")

    def export_all_txt_reports(self):
        if not self.current_folder or not self.folder_files:
            QMessageBox.warning(self, "No folder loaded", "Open a folder first.")
            return

        reply = QMessageBox.question(
            self,
            "Export all TXT reports",
            (
                f"This will scan and export TXT reports from {len(self.folder_files)} file(s).\n\n"
                "The app may pause during export.\n\n"
                "Original files will not be modified.\n\n"
                "Do you want to continue?"
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        selected_folder = QFileDialog.getExistingDirectory(
            self,
            "Choose output folder for all TXT reports",
            str(REPORTS_DIR.resolve() if REPORTS_DIR.exists() else Path.home()),
        )

        if not selected_folder:
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        export_root = Path(selected_folder) / f"kai_metadata_txt_export_{timestamp}"
        txt_dir = export_root / "txt_reports"
        txt_dir.mkdir(parents=True, exist_ok=True)

        errors = []
        exported = 0

        self.status_label.setText("Status: Exporting all TXT reports...")
        QApplication.processEvents()

        for index, file_path in enumerate(self.folder_files, start=1):
            try:
                self.status_label.setText(
                    f"Status: Exporting TXT {index}/{len(self.folder_files)} — {file_path.name}"
                )
                QApplication.processEvents()

                raw = safe_run_exiftool(file_path)
                analysis = build_analysis(file_path, raw, self.exiftool_version)
                report = build_report(file_path, analysis)

                output_name = f"{safe_output_name(file_path.stem)}_metadata_report.txt"
                output_path = txt_dir / output_name
                output_path.write_text(report, encoding="utf-8")

                exported += 1

            except Exception as error:
                errors.append(f"{file_path.name}: {error}")

        if errors:
            error_log = export_root / "txt_export_errors.txt"
            error_log.write_text("\n".join(errors), encoding="utf-8")

        QMessageBox.information(
            self,
            "Export complete",
            (
                f"TXT export finished.\n\n"
                f"Exported: {exported}\n"
                f"Errors: {len(errors)}\n\n"
                f"Output folder:\n{export_root}"
            ),
        )

        self.status_label.setText(
            f"Status: Exported {exported} TXT report(s), {len(errors)} error(s)."
        )

    def export_all_json_reports(self):
        if not self.current_folder or not self.folder_files:
            QMessageBox.warning(self, "No folder loaded", "Open a folder first.")
            return

        reply = QMessageBox.question(
            self,
            "Export all raw JSON reports",
            (
                f"This will scan and export raw JSON metadata from {len(self.folder_files)} file(s).\n\n"
                "The app may pause during export.\n\n"
                "Original files will not be modified.\n\n"
                "Do you want to continue?"
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        selected_folder = QFileDialog.getExistingDirectory(
            self,
            "Choose output folder for all raw JSON reports",
            str(REPORTS_DIR.resolve() if REPORTS_DIR.exists() else Path.home()),
        )

        if not selected_folder:
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        export_root = Path(selected_folder) / f"kai_metadata_json_export_{timestamp}"
        json_dir = export_root / "json_reports"
        json_dir.mkdir(parents=True, exist_ok=True)

        errors = []
        exported = 0

        self.status_label.setText("Status: Exporting all raw JSON reports...")
        QApplication.processEvents()

        for index, file_path in enumerate(self.folder_files, start=1):
            try:
                self.status_label.setText(
                    f"Status: Exporting JSON {index}/{len(self.folder_files)} — {file_path.name}"
                )
                QApplication.processEvents()

                raw = safe_run_exiftool(file_path)

                output_name = f"{safe_output_name(file_path.stem)}_raw_metadata.json"
                output_path = json_dir / output_name
                output_path.write_text(
                    json.dumps(raw, indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )

                exported += 1

            except Exception as error:
                errors.append(f"{file_path.name}: {error}")

        if errors:
            error_log = export_root / "json_export_errors.txt"
            error_log.write_text("\n".join(errors), encoding="utf-8")

        QMessageBox.information(
            self,
            "Export complete",
            (
                f"Raw JSON export finished.\n\n"
                f"Exported: {exported}\n"
                f"Errors: {len(errors)}\n\n"
                f"Output folder:\n{export_root}"
            ),
        )

        self.status_label.setText(
            f"Status: Exported {exported} raw JSON file(s), {len(errors)} error(s)."
        )

    def create_clean_copy(self):
        if not self.current_file:
            QMessageBox.warning(self, "No file selected", "Open a file first.")
            return

        reply = QMessageBox.question(
            self,
            "Create cleaned copy",
            (
                "This will create a new copy with metadata removed.\n\n"
                "The original file will NOT be modified.\n\n"
                "A cleaning report will also be created.\n\n"
                "Continue?"
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        default_name = f"{self.current_file.stem}_cleaned{self.current_file.suffix}"
        default_path = REPORTS_DIR / "cleaned" / default_name

        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save cleaned copy",
            str(default_path),
            "All files (*)",
        )

        if not save_path:
            return

        output_path = Path(save_path)

        try:
            self.status_label.setText("Status: Creating cleaned copy...")
            QApplication.processEvents()

            result = clean_metadata_copy(self.current_file, output_path)

            QMessageBox.information(
                self,
                "Cleaned copy created",
                (
                    "Cleaned copy created successfully.\n\n"
                    f"Original file:\n{result['source_path']}\n\n"
                    f"Cleaned copy:\n{result['output_path']}\n\n"
                    f"Cleaning report:\n{result['report_path']}\n\n"
                    f"Tags before: {result['before_tag_count']}\n"
                    f"Tags after: {result['after_tag_count']}\n"
                    f"Removed tags: {result['removed_tag_count']}\n\n"
                    "Recommended: open the cleaned copy in this app and review remaining metadata."
                ),
            )

            self.status_label.setText(
                f"Status: Cleaned copy created at {result['output_path']}"
            )

        except Exception as error:
            QMessageBox.critical(self, "Cleaning error", str(error))
            self.status_label.setText("Status: Error while creating cleaned copy.")

    def clear_data(self):
        self.current_file = None
        self.current_analysis = None
        self.current_report = None
        self.current_pixmap = None
        self.raw_metadata_lines = []

        self.current_folder = None
        self.folder_files = []
        self.folder_summary = None
        self.folder_summary_report = None

        self.file_label.setText("Selected file: none")
        self.left_info.clear()
        self.preview_label.clear()
        self.preview_label.setPixmap(QPixmap())
        self.preview_label.setText("No preview loaded")
        self.raw_search.clear()
        self.folder_list.clear()
        self.folder_label.setText("Folder files: none")

        for text_box in self.tab_widgets.values():
            text_box.clear()

        self.export_button.setEnabled(False)
        self.export_json_button.setEnabled(False)
        self.clean_copy_button.setEnabled(False)
        self.export_summary_button.setEnabled(False)
        self.export_summary_csv_button.setEnabled(False)
        self.export_all_txt_button.setEnabled(False)
        self.export_all_json_button.setEnabled(False)
        self.scan_summary_button.setEnabled(False)

        self.status_label.setText("Status: Cleared.")
