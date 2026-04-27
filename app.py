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


APP_NAME = "Kai Metadata Inspector"
APP_VERSION = "v0.5 Linux Alpha"

REPORTS_DIR = Path("reports")

MAX_FILE_SIZE_MB_WARNING = 250
MAX_PREVIEW_FILE_SIZE_MB = 50
MAX_FOLDER_FILES_WARNING = 300
MAX_FOLDER_SUMMARY_WARNING = 100
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

    -c %.8f formats GPS coordinates as decimal numbers where possible.
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
        "-c",
        "%.8f",
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


def clean_text(value: object, max_length: int = 5000) -> str:
    """
    Treat metadata as untrusted text.
    Keep it plain text and limit very large fields.
    """

    text = str(value)

    if len(text) > max_length:
        return text[:max_length] + "\n...[truncated for safe display]"

    return text


def format_section(title: str, data: dict) -> str:
    lines = [title, "=" * len(title), ""]

    for key, value in data.items():
        lines.append(f"{key}: {clean_text(value)}")

    return "\n".join(lines)


def gps_map_text(latitude: str, longitude: str) -> str:
    if latitude == "Not found" or longitude == "Not found":
        return "Not available"

    return f"https://maps.google.com/?q={latitude},{longitude}"


def timezone_status(raw: dict) -> tuple[str, str]:
    offset_original = get_any(raw, ["EXIF:OffsetTimeOriginal"])
    offset_digitized = get_any(raw, ["EXIF:OffsetTimeDigitized"])
    offset_general = get_any(raw, ["EXIF:OffsetTime"])

    gps_date = get_any(raw, ["GPS:GPSDateStamp"])
    gps_time = get_any(raw, ["GPS:GPSTimeStamp"])

    if offset_original != "Not found":
        return "Stored timezone offset found", f"OffsetTimeOriginal: {offset_original}"

    if offset_digitized != "Not found":
        return "Stored timezone offset found", f"OffsetTimeDigitized: {offset_digitized}"

    if offset_general != "Not found":
        return "Stored timezone offset found", f"OffsetTime: {offset_general}"

    if gps_date != "Not found" or gps_time != "Not found":
        return (
            "Timezone not directly stored",
            "GPS date/time exists and is usually UTC/GPS time. Local timezone may need manual interpretation."
        )

    return (
        "Timezone not found",
        "No timezone offset fields or GPS time fields were found."
    )


def find_supported_files(folder_path: Path) -> list[Path]:
    """
    Folder scan for v0.5.

    Security/scope:
    - scans only the selected folder, not subfolders
    - only lists supported extensions
    - metadata extraction happens only after user clicks a file
      or manually clicks Scan Folder Summary
    """

    files = []

    for item in folder_path.iterdir():
        if item.is_file() and item.suffix.lower() in SUPPORTED_EXTENSIONS:
            files.append(item)

    return sorted(files, key=lambda p: p.name.lower())


def build_analysis(file_path: Path, raw: dict) -> dict:
    file_size_mb = file_path.stat().st_size / (1024 * 1024)

    gps_lat = get_any(raw, ["GPS:GPSLatitude", "Composite:GPSLatitude"])
    gps_lon = get_any(raw, ["GPS:GPSLongitude", "Composite:GPSLongitude"])

    tz_status, tz_explanation = timezone_status(raw)

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
        "Timezone status": tz_status,
        "Timezone explanation": tz_explanation,
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
    timezone_found = has_any(raw, ["EXIF:OffsetTimeOriginal", "EXIF:OffsetTimeDigitized", "EXIF:OffsetTime"])
    gps_time_found = has_any(raw, ["GPS:GPSDateStamp", "GPS:GPSTimeStamp"])
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
        reasons.append("GPS coordinates found. This may reveal where the image was taken.")

    if time_found:
        risk_points += 2
        reasons.append("Capture or creation timestamp found. This may reveal when the image was taken.")

    if timezone_found:
        risk_points += 1
        reasons.append("Timezone offset found. This can make timestamps more precise.")

    if gps_time_found:
        risk_points += 1
        reasons.append("GPS timestamp found. This may help reconstruct the exact capture timeline.")

    if device_found:
        risk_points += 1
        reasons.append("Camera or phone model found.")

    if serial_found:
        risk_points += 3
        reasons.append("Device serial number found. This can be sensitive.")

    if owner_found:
        risk_points += 3
        reasons.append("Owner, creator, artist or copyright information found.")

    if software_found:
        risk_points += 1
        reasons.append("Software or editing tool information found.")

    if not reasons:
        reasons.append("No obvious sensitive metadata found. Metadata may also have been stripped.")

    if risk_points >= 9:
        risk_level = "CRITICAL"
    elif risk_points >= 6:
        risk_level = "HIGH"
    elif risk_points >= 3:
        risk_level = "MEDIUM"
    else:
        risk_level = "LOW"

    privacy_info = {
        "Privacy risk": risk_level,
        "Risk score": f"{risk_points} point(s)",
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

    if timezone_found:
        interesting.append("Timezone offset is stored in the image metadata.")
    elif gps_time_found:
        interesting.append("GPS time exists, but local timezone offset was not directly found.")
    else:
        interesting.append("No timezone information found.")

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
        "Timezone": tz_status,
        "GPS": "Found" if gps_found else "Not found",
        "Privacy risk": risk_level,
        "Risk score": f"{risk_points} point(s)",
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
        "flags": {
            "gps_found": gps_found,
            "time_found": time_found,
            "timezone_found": timezone_found,
            "gps_time_found": gps_time_found,
            "device_found": device_found,
            "serial_found": serial_found,
            "owner_found": owner_found,
            "software_found": software_found,
            "risk_points": risk_points,
            "risk_level": risk_level,
        }
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
        "device model, timestamps, timezone offsets, serial numbers, owner information "
        "or editing history. Be careful before sharing it."
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
        value = clean_text(analysis["raw"][key])
        lines.append(f"{key}: {value}")

    lines.append("")
    lines.append("End of report.")
    return "\n".join(lines)


def build_folder_summary(folder_path: Path, files: list[Path]) -> tuple[dict, str]:
    """
    Scans metadata for each supported file in the selected folder.

    Security/scope:
    - still read-only
    - no internet
    - no file modification
    - each file uses safe ExifTool subprocess call
    """

    summary = {
        "folder_path": str(folder_path),
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_supported_files": len(files),
        "scanned_ok": 0,
        "scan_errors": 0,
        "gps_count": 0,
        "timestamp_count": 0,
        "timezone_count": 0,
        "gps_time_count": 0,
        "device_count": 0,
        "serial_count": 0,
        "owner_count": 0,
        "software_count": 0,
        "low_risk": 0,
        "medium_risk": 0,
        "high_risk": 0,
        "critical_risk": 0,
        "device_models": {},
        "file_rows": [],
        "errors": [],
    }

    for index, file_path in enumerate(files, start=1):
        try:
            raw = safe_run_exiftool(file_path)
            analysis = build_analysis(file_path, raw)
            flags = analysis["flags"]

            summary["scanned_ok"] += 1

            if flags["gps_found"]:
                summary["gps_count"] += 1

            if flags["time_found"]:
                summary["timestamp_count"] += 1

            if flags["timezone_found"]:
                summary["timezone_count"] += 1

            if flags["gps_time_found"]:
                summary["gps_time_count"] += 1

            if flags["device_found"]:
                summary["device_count"] += 1

            if flags["serial_found"]:
                summary["serial_count"] += 1

            if flags["owner_found"]:
                summary["owner_count"] += 1

            if flags["software_found"]:
                summary["software_count"] += 1

            risk_level = flags["risk_level"]

            if risk_level == "LOW":
                summary["low_risk"] += 1
            elif risk_level == "MEDIUM":
                summary["medium_risk"] += 1
            elif risk_level == "HIGH":
                summary["high_risk"] += 1
            elif risk_level == "CRITICAL":
                summary["critical_risk"] += 1

            device_make = analysis["device"]["Make"]
            device_model = analysis["device"]["Model"]

            if device_make != "Not found" or device_model != "Not found":
                device_name = f"{device_make} {device_model}".strip()
                summary["device_models"][device_name] = summary["device_models"].get(device_name, 0) + 1

            summary["file_rows"].append({
                "file": file_path.name,
                "risk": risk_level,
                "risk_points": flags["risk_points"],
                "gps": "Yes" if flags["gps_found"] else "No",
                "timestamp": "Yes" if flags["time_found"] else "No",
                "timezone": "Yes" if flags["timezone_found"] else "No",
                "device": f"{device_make} {device_model}".strip(),
                "software": analysis["software"]["Software"],
            })

        except Exception as error:
            summary["scan_errors"] += 1
            summary["errors"].append({
                "file": file_path.name,
                "error": str(error),
            })

    report = build_folder_summary_report(summary)
    return summary, report


def build_folder_summary_report(summary: dict) -> str:
    lines = []

    lines.append("KAI METADATA INSPECTOR — FOLDER SUMMARY REPORT")
    lines.append("==============================================")
    lines.append("")
    lines.append(f"App version: {APP_VERSION}")
    lines.append(f"Generated: {summary['generated']}")
    lines.append(f"Folder: {summary['folder_path']}")
    lines.append("")
    lines.append("SHARING WARNING")
    lines.append("---------------")
    lines.append(
        "This folder summary may reveal sensitive patterns, including how many files contain "
        "GPS coordinates, timestamps, device models, serial numbers, owner information or editing history."
    )
    lines.append("")

    lines.append("Summary Counts")
    lines.append("--------------")
    lines.append(f"Total supported files: {summary['total_supported_files']}")
    lines.append(f"Successfully scanned: {summary['scanned_ok']}")
    lines.append(f"Scan errors: {summary['scan_errors']}")
    lines.append(f"Files with GPS: {summary['gps_count']}")
    lines.append(f"Files with timestamps: {summary['timestamp_count']}")
    lines.append(f"Files with timezone offset: {summary['timezone_count']}")
    lines.append(f"Files with GPS time: {summary['gps_time_count']}")
    lines.append(f"Files with device make/model: {summary['device_count']}")
    lines.append(f"Files with serial number: {summary['serial_count']}")
    lines.append(f"Files with owner/creator/copyright info: {summary['owner_count']}")
    lines.append(f"Files with software/editing info: {summary['software_count']}")
    lines.append("")

    lines.append("Risk Breakdown")
    lines.append("--------------")
    lines.append(f"LOW: {summary['low_risk']}")
    lines.append(f"MEDIUM: {summary['medium_risk']}")
    lines.append(f"HIGH: {summary['high_risk']}")
    lines.append(f"CRITICAL: {summary['critical_risk']}")
    lines.append("")

    lines.append("Device Models")
    lines.append("-------------")
    if summary["device_models"]:
        for device, count in sorted(summary["device_models"].items()):
            lines.append(f"{device}: {count}")
    else:
        lines.append("No device models found.")
    lines.append("")

    lines.append("Per-File Overview")
    lines.append("-----------------")
    if summary["file_rows"]:
        for row in summary["file_rows"]:
            lines.append(
                f"{row['file']} | Risk: {row['risk']} ({row['risk_points']} pts) | "
                f"GPS: {row['gps']} | Timestamp: {row['timestamp']} | "
                f"Timezone: {row['timezone']} | Device: {row['device']} | "
                f"Software: {row['software']}"
            )
    else:
        lines.append("No files scanned successfully.")
    lines.append("")

    if summary["errors"]:
        lines.append("Scan Errors")
        lines.append("-----------")
        for error in summary["errors"]:
            lines.append(f"{error['file']}: {error['error']}")
        lines.append("")

    lines.append("End of folder summary report.")
    return "\n".join(lines)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

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
        self.export_summary_button = QPushButton("Export Folder Summary")
        self.clear_button = QPushButton("Clear")

        self.scan_summary_button.setEnabled(False)
        self.export_button.setEnabled(False)
        self.export_json_button.setEnabled(False)
        self.export_summary_button.setEnabled(False)

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

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.open_button)
        button_layout.addWidget(self.open_folder_button)
        button_layout.addWidget(self.scan_summary_button)
        button_layout.addWidget(self.export_button)
        button_layout.addWidget(self.export_json_button)
        button_layout.addWidget(self.export_summary_button)
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
        self.open_folder_button.clicked.connect(self.open_folder)
        self.scan_summary_button.clicked.connect(self.scan_folder_summary)
        self.export_button.clicked.connect(self.export_txt)
        self.export_json_button.clicked.connect(self.export_json)
        self.export_summary_button.clicked.connect(self.export_folder_summary)
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
            return

        if len(files) > MAX_FOLDER_FILES_WARNING:
            reply = QMessageBox.question(
                self,
                "Large folder warning",
                (
                    f"This folder contains {len(files)} supported files.\n\n"
                    "v0.5 lists the files but only scans metadata when you click one "
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

        self.folder_list.clear()

        for file_path in files:
            item = QListWidgetItem(file_path.name)
            item.setData(Qt.ItemDataRole.UserRole, str(file_path))
            self.folder_list.addItem(item)

        self.folder_label.setText(
            f"Folder files: {len(files)} supported file(s) found in {folder_path}"
        )
        self.scan_summary_button.setEnabled(True)
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

            summary, report = build_folder_summary(self.current_folder, self.folder_files)

            self.folder_summary = summary
            self.folder_summary_report = report

            self.tab_widgets["Folder Summary"].setPlainText(report)
            self.tabs.setCurrentWidget(self.tab_widgets["Folder Summary"])
            self.export_summary_button.setEnabled(True)

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
            analysis = build_analysis(file_path, raw)
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
        self.export_summary_button.setEnabled(False)
        self.scan_summary_button.setEnabled(False)

        self.status_label.setText("Status: Cleared.")


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()