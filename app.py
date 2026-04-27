import json
import shutil
import subprocess
import sys
from pathlib import Path
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
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


APP_NAME = "Kai Metadata Inspector"
APP_VERSION = "v0.2 Linux Alpha"

REPORTS_DIR = Path("reports")

MAX_FILE_SIZE_MB_WARNING = 250
MAX_PREVIEW_FILE_SIZE_MB = 50
EXIFTOOL_TIMEOUT_SECONDS = 30


SUPPORTED_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif",
    ".tif", ".tiff", ".bmp", ".gif", ".avif", ".dng",
    ".cr2", ".cr3", ".nef", ".arw", ".rw2", ".orf",
    ".raf", ".pef", ".srw", ".psd", ".xmp"
}


PREVIEW_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"
}


def safe_run_exiftool(file_path: Path) -> dict:
    """
    Safely runs ExifTool.

    Security rules:
    - no shell=True
    - file path passed as argument list
    - timeout enabled
    - output parsed as JSON
    - original file is never modified
    """

    if not shutil.which("exiftool"):
        raise RuntimeError(
            "ExifTool is not installed. Install it with:\n"
            "sudo apt install libimage-exiftool-perl"
        )

    if not file_path.exists():
        raise FileNotFoundError("Selected file does not exist.")

    if not file_path.is_file():
        raise RuntimeError("Selected path is not a file.")

    cmd = [
        "exiftool",
        "-json",
        "-G",
        "-a",
        "-s",
        str(file_path),
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=EXIFTOOL_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(
            f"ExifTool timed out after {EXIFTOOL_TIMEOUT_SECONDS} seconds."
        )

    if result.returncode != 0:
        error_text = result.stderr.strip() or "Unknown ExifTool error."
        raise RuntimeError(error_text)

    try:
        parsed = json.loads(result.stdout)
    except json.JSONDecodeError:
        raise RuntimeError("ExifTool returned invalid JSON.")

    if not parsed:
        raise RuntimeError("No metadata returned by ExifTool.")

    return parsed[0]


def get_exiftool_version() -> str:
    if not shutil.which("exiftool"):
        return "Not installed"

    try:
        result = subprocess.run(
            ["exiftool", "-ver"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        return result.stdout.strip() or "Unknown"
    except Exception:
        return "Unknown"


def get_any(metadata: dict, possible_keys: list[str], default: str = "Not found") -> str:
    for key in possible_keys:
        value = metadata.get(key)
        if value not in [None, ""]:
            return str(value)
    return default


def has_any(metadata: dict, possible_keys: list[str]) -> bool:
    for key in possible_keys:
        value = metadata.get(key)
        if value not in [None, "", "Not found"]:
            return True
    return False


def format_section(title: str, data: dict) -> str:
    lines = [title, "=" * len(title), ""]

    for key, value in data.items():
        lines.append(f"{key}: {value}")

    return "\n".join(lines)


def gps_map_text(latitude: str, longitude: str) -> str:
    if latitude == "Not found" or longitude == "Not found":
        return "Not available"

    return f"https://maps.google.com/?q={latitude},{longitude}"


def build_analysis(file_path: Path, raw: dict) -> dict:
    file_size_mb = file_path.stat().st_size / (1024 * 1024)

    gps_lat = get_any(raw, ["GPS:GPSLatitude", "Composite:GPSLatitude"])
    gps_lon = get_any(raw, ["GPS:GPSLongitude", "Composite:GPSLongitude"])

    file_info = {
        "File name": file_path.name,
        "File path": str(file_path.resolve()),
        "File extension": file_path.suffix.lower(),
        "File size": f"{file_size_mb:.2f} MB",
        "ExifTool version": get_exiftool_version(),
        "File type": get_any(raw, ["File:FileType", "File:FileTypeExtension"]),
        "MIME type": get_any(raw, ["File:MIMEType"]),
        "Image width": get_any(raw, ["File:ImageWidth", "EXIF:ExifImageWidth", "PNG:ImageWidth"]),
        "Image height": get_any(raw, ["File:ImageHeight", "EXIF:ExifImageHeight", "PNG:ImageHeight"]),
        "Megapixels": get_any(raw, ["Composite:Megapixels"]),
        "Color profile": get_any(raw, ["ICC_Profile:ProfileDescription", "ICC_Profile:ColorSpaceData"]),
    }

    device_info = {
        "Make": get_any(raw, ["EXIF:Make", "IFD0:Make", "QuickTime:Make"]),
        "Model": get_any(raw, ["EXIF:Model", "IFD0:Model", "QuickTime:Model"]),
        "Lens model": get_any(raw, ["EXIF:LensModel", "Composite:LensID", "MakerNotes:LensModel"]),
        "Lens make": get_any(raw, ["EXIF:LensMake"]),
        "Serial number": get_any(raw, [
            "EXIF:SerialNumber",
            "MakerNotes:SerialNumber",
            "MakerNotes:CameraSerialNumber",
            "Composite:SerialNumber",
        ]),
        "Firmware": get_any(raw, ["MakerNotes:FirmwareVersion", "EXIF:FirmwareVersion"]),
    }

    time_info = {
        "Date/time original": get_any(raw, ["EXIF:DateTimeOriginal", "XMP:DateCreated"]),
        "Create date": get_any(raw, ["EXIF:CreateDate", "QuickTime:CreateDate", "XMP:CreateDate"]),
        "Modify date": get_any(raw, ["EXIF:ModifyDate", "File:FileModifyDate", "XMP:ModifyDate"]),
        "Offset time original": get_any(raw, ["EXIF:OffsetTimeOriginal"]),
        "Offset time digitized": get_any(raw, ["EXIF:OffsetTimeDigitized"]),
        "Offset time": get_any(raw, ["EXIF:OffsetTime"]),
        "GPS date stamp": get_any(raw, ["GPS:GPSDateStamp"]),
        "GPS time stamp": get_any(raw, ["GPS:GPSTimeStamp"]),
        "Timezone note": "If offset fields are missing, timezone may not be stored in the file.",
    }

    location_info = {
        "GPS latitude": gps_lat,
        "GPS longitude": gps_lon,
        "GPS altitude": get_any(raw, ["GPS:GPSAltitude", "Composite:GPSAltitude"]),
        "GPS speed": get_any(raw, ["GPS:GPSSpeed"]),
        "GPS direction": get_any(raw, ["GPS:GPSImgDirection", "Composite:GPSImgDirection"]),
        "Map link text": gps_map_text(gps_lat, gps_lon),
        "Location note": "No online lookup is performed. Coordinates are displayed locally only.",
    }

    camera_info = {
        "ISO": get_any(raw, ["EXIF:ISO", "MakerNotes:ISO"]),
        "Aperture": get_any(raw, ["EXIF:FNumber", "Composite:Aperture"]),
        "Exposure time": get_any(raw, ["EXIF:ExposureTime"]),
        "Shutter speed": get_any(raw, ["Composite:ShutterSpeed"]),
        "Focal length": get_any(raw, ["EXIF:FocalLength", "Composite:FocalLength"]),
        "35mm equivalent focal length": get_any(raw, ["EXIF:FocalLengthIn35mmFormat"]),
        "Flash": get_any(raw, ["EXIF:Flash"]),
        "White balance": get_any(raw, ["EXIF:WhiteBalance"]),
        "Exposure mode": get_any(raw, ["EXIF:ExposureMode"]),
        "Metering mode": get_any(raw, ["EXIF:MeteringMode"]),
    }

    software_info = {
        "Software": get_any(raw, ["EXIF:Software", "IFD0:Software"]),
        "Creator tool": get_any(raw, ["XMP:CreatorTool"]),
        "Processing software": get_any(raw, ["EXIF:ProcessingSoftware"]),
        "History": get_any(raw, ["XMP:HistoryAction", "XMP:HistorySoftwareAgent"]),
        "Artist": get_any(raw, ["EXIF:Artist", "IFD0:Artist", "XMP:Creator"]),
        "Copyright": get_any(raw, ["EXIF:Copyright", "IFD0:Copyright", "XMP:Rights"]),
    }

    gps_found = has_any(raw, ["GPS:GPSLatitude", "GPS:GPSLongitude", "Composite:GPSLatitude", "Composite:GPSLongitude"])
    time_found = has_any(raw, ["EXIF:DateTimeOriginal", "EXIF:CreateDate", "QuickTime:CreateDate", "XMP:CreateDate"])
    device_found = has_any(raw, ["EXIF:Make", "EXIF:Model", "IFD0:Make", "IFD0:Model", "QuickTime:Model"])
    serial_found = has_any(raw, [
        "EXIF:SerialNumber",
        "MakerNotes:SerialNumber",
        "MakerNotes:CameraSerialNumber",
        "Composite:SerialNumber",
    ])
    owner_found = has_any(raw, ["EXIF:Artist", "IFD0:Artist", "XMP:Creator", "XMP:Rights", "EXIF:Copyright"])
    software_found = has_any(raw, ["EXIF:Software", "IFD0:Software", "XMP:CreatorTool"])

    risk_points = 0
    reasons = []

    if gps_found:
        risk_points += 4
        reasons.append("GPS coordinates found.")

    if time_found:
        risk_points += 2
        reasons.append("Capture or creation timestamp found.")

    if device_found:
        risk_points += 1
        reasons.append("Camera or phone model found.")

    if serial_found:
        risk_points += 3
        reasons.append("Device serial number found.")

    if owner_found:
        risk_points += 3
        reasons.append("Owner, creator, artist or copyright information found.")

    if software_found:
        risk_points += 1
        reasons.append("Software or editing tool information found.")

    if not reasons:
        reasons.append("No obvious sensitive metadata found. Metadata may also have been stripped.")

    if risk_points >= 8:
        risk_level = "CRITICAL"
    elif risk_points >= 5:
        risk_level = "HIGH"
    elif risk_points >= 2:
        risk_level = "MEDIUM"
    else:
        risk_level = "LOW"

    privacy_info = {
        "Privacy risk": risk_level,
        "Reasons": "\n- " + "\n- ".join(reasons),
        "Important warning": (
            "Exported reports may contain sensitive information. "
            "Be careful before sharing reports or screenshots."
        ),
    }

    interesting = []

    if gps_found:
        interesting.append("GPS/location metadata is present.")
    else:
        interesting.append("No GPS coordinates found.")

    if time_found:
        interesting.append("Timestamp metadata is present.")
    else:
        interesting.append("No obvious original timestamp found.")

    if device_found:
        interesting.append("Device make/model metadata is present.")

    if serial_found:
        interesting.append("Serial number metadata is present. This can be sensitive.")

    if owner_found:
        interesting.append("Creator/owner/copyright metadata is present.")

    if software_found:
        interesting.append("Software/editing metadata is present.")

    if file_size_mb > MAX_FILE_SIZE_MB_WARNING:
        interesting.append(
            f"Large file warning: file is {file_size_mb:.2f} MB."
        )

    overview = {
        "App version": APP_VERSION,
        "File": file_path.name,
        "Format": file_info["File type"],
        "Device": f"{device_info['Make']} {device_info['Model']}",
        "Capture time": time_info["Date/time original"],
        "GPS": "Found" if gps_found else "Not found",
        "Privacy risk": risk_level,
        "Interesting findings": "\n- " + "\n- ".join(interesting),
    }

    return {
        "overview": overview,
        "file": file_info,
        "device": device_info,
        "time": time_info,
        "location": location_info,
        "camera": camera_info,
        "software": software_info,
        "privacy": privacy_info,
        "interesting": interesting,
        "raw": raw,
    }


def build_report(file_path: Path, analysis: dict) -> str:
    lines = []

    lines.append("KAI METADATA INSPECTOR REPORT")
    lines.append("=============================")
    lines.append("")
    lines.append(f"App version: {APP_VERSION}")
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"Source file: {file_path}")
    lines.append("")
    lines.append("SHARING WARNING")
    lines.append("---------------")
    lines.append(
        "This report may contain sensitive information such as GPS coordinates, "
        "device model, timestamps, serial numbers, owner information or editing history. "
        "Be careful before sharing it."
    )
    lines.append("")

    section_order = [
        ("Overview", "overview"),
        ("File Information", "file"),
        ("Device Information", "device"),
        ("Time Information", "time"),
        ("Location Information", "location"),
        ("Camera Settings", "camera"),
        ("Software / Editing", "software"),
        ("Privacy Risk", "privacy"),
    ]

    for title, key in section_order:
        lines.append(format_section(title, analysis[key]))
        lines.append("")

    lines.append("Raw Metadata")
    lines.append("============")
    lines.append("")

    for key in sorted(analysis["raw"].keys()):
        value = analysis["raw"][key]
        lines.append(f"{key}: {value}")

    lines.append("")
    lines.append("End of report.")
    return "\n".join(lines)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.current_file: Path | None = None
        self.current_analysis: dict | None = None
        self.current_report: str | None = None
        self.current_pixmap: QPixmap | None = None
        self.raw_metadata_lines: list[str] = []

        self.setWindowTitle(f"{APP_NAME} — {APP_VERSION}")
        self.resize(1250, 780)

        self.open_button = QPushButton("Open Image / File")
        self.export_button = QPushButton("Export TXT")
        self.clear_button = QPushButton("Clear")

        self.export_button.setEnabled(False)

        self.file_label = QLabel("Selected file: none")
        self.file_label.setWordWrap(True)

        self.status_label = QLabel("Status: Ready")
        self.status_label.setWordWrap(True)

        self.preview_title = QLabel("Preview")
        self.preview_title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.preview_label = QLabel("No preview loaded")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setWordWrap(True)
        self.preview_label.setMinimumSize(320, 320)
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
        self.left_info.setMaximumHeight(170)

        left_panel = QWidget()
        left_layout = QVBoxLayout()
        left_layout.addWidget(self.preview_title)
        left_layout.addWidget(self.preview_scroll)
        left_layout.addWidget(QLabel("Quick File Info"))
        left_layout.addWidget(self.left_info)
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
        splitter.setSizes([430, 820])

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.open_button)
        button_layout.addWidget(self.export_button)
        button_layout.addWidget(self.clear_button)
        button_layout.addStretch()

        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setFrameShadow(QFrame.Shadow.Sunken)

        main_layout = QVBoxLayout()
        main_layout.addLayout(button_layout)
        main_layout.addWidget(self.file_label)
        main_layout.addWidget(divider)
        main_layout.addWidget(splitter)
        main_layout.addWidget(self.status_label)

        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)

        self.open_button.clicked.connect(self.open_file)
        self.export_button.clicked.connect(self.export_txt)
        self.clear_button.clicked.connect(self.clear_data)

        self.show_startup_info()

    def show_startup_info(self):
        version = get_exiftool_version()
        self.status_label.setText(f"Status: Ready | ExifTool version: {version}")

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

        file_path = Path(selected_file)

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
            analysis = build_analysis(file_path, raw)
            report = build_report(file_path, analysis)

            self.current_file = file_path
            self.current_analysis = analysis
            self.current_report = report

            self.file_label.setText(f"Selected file: {file_path}")
            self.populate_tabs(analysis)
            self.update_left_info(file_path, analysis)
            self.load_preview(file_path)

            self.export_button.setEnabled(True)
            self.status_label.setText("Status: Metadata extracted successfully.")

        except Exception as error:
            QMessageBox.critical(self, "Error", str(error))
            self.status_label.setText("Status: Error while extracting metadata.")

    def update_left_info(self, file_path: Path, analysis: dict):
        quick_info = {
            "File name": analysis["file"]["File name"],
            "File type": analysis["file"]["File type"],
            "Size": analysis["file"]["File size"],
            "Dimensions": f"{analysis['file']['Image width']} x {analysis['file']['Image height']}",
            "Device": analysis["overview"]["Device"],
            "Capture time": analysis["overview"]["Capture time"],
            "GPS": analysis["overview"]["GPS"],
            "Privacy risk": analysis["overview"]["Privacy risk"],
        }

        self.left_info.setPlainText(format_section("Quick File Info", quick_info))

    def load_preview(self, file_path: Path):
        self.current_pixmap = None

        suffix = file_path.suffix.lower()
        file_size_mb = file_path.stat().st_size / (1024 * 1024)

        if suffix not in PREVIEW_EXTENSIONS:
            self.preview_label.setText(
                "Preview unavailable for this format.\n\n"
                "Metadata extraction still worked.\n\n"
                "Preview support in Alpha:\n"
                "JPG, JPEG, PNG, WEBP, BMP, GIF"
            )
            return

        if file_size_mb > MAX_PREVIEW_FILE_SIZE_MB:
            self.preview_label.setText(
                f"Preview skipped because the file is {file_size_mb:.2f} MB.\n\n"
                "Metadata extraction still worked."
            )
            return

        pixmap = QPixmap(str(file_path))

        if pixmap.isNull():
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
            self.raw_metadata_lines.append(f"{key}: {analysis['raw'][key]}")

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
            self.status_label.setText(f"Status: Report exported to {save_path}")

        except Exception as error:
            QMessageBox.critical(self, "Export error", str(error))
            self.status_label.setText("Status: Error while exporting report.")

    def clear_data(self):
        self.current_file = None
        self.current_analysis = None
        self.current_report = None
        self.current_pixmap = None
        self.raw_metadata_lines = []

        self.file_label.setText("Selected file: none")
        self.left_info.clear()
        self.preview_label.clear()
        self.preview_label.setText("No preview loaded")
        self.raw_search.clear()

        for text_box in self.tab_widgets.values():
            text_box.clear()

        self.export_button.setEnabled(False)
        self.status_label.setText("Status: Cleared.")


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
