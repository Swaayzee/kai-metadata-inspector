from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from PySide6.QtCore import Qt, QUrl
    from PySide6.QtGui import QDesktopServices, QPixmap
    from PySide6.QtWidgets import (
        QAbstractItemView,
        QApplication,
        QFileDialog,
        QFrame,
        QGridLayout,
        QGroupBox,
        QHBoxLayout,
        QHeaderView,
        QLabel,
        QMainWindow,
        QMessageBox,
        QPushButton,
        QSizePolicy,
        QSplitter,
        QTableWidget,
        QTableWidgetItem,
        QVBoxLayout,
        QWidget,
        QPlainTextEdit,
    )
except ImportError:
    from PyQt6.QtCore import Qt, QUrl
    from PyQt6.QtGui import QDesktopServices, QPixmap
    from PyQt6.QtWidgets import (
        QAbstractItemView,
        QApplication,
        QFileDialog,
        QFrame,
        QGridLayout,
        QGroupBox,
        QHBoxLayout,
        QHeaderView,
        QLabel,
        QMainWindow,
        QMessageBox,
        QPushButton,
        QSizePolicy,
        QSplitter,
        QTableWidget,
        QTableWidgetItem,
        QVBoxLayout,
        QWidget,
        QPlainTextEdit,
    )

try:
    from PIL import ExifTags, Image, ImageOps
except ImportError:
    ExifTags = None
    Image = None
    ImageOps = None


APP_NAME = "Kai Metadata Inspector"


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def outputs_dir() -> Path:
    folder = project_root() / "outputs"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def human_bytes(size: int) -> str:
    value = float(size)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if value < 1024 or unit == "TB":
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} {unit}"
        value /= 1024
    return f"{size} B"


def safe_text(value: Any, limit: int = 3000) -> str:
    if value is None:
        return ""

    if isinstance(value, bytes):
        text = f"<bytes: {len(value)} bytes>"
    elif isinstance(value, (list, tuple, set)):
        text = ", ".join(safe_text(item, 500) for item in value)
    elif isinstance(value, dict):
        parts = [f"{safe_text(k, 200)}={safe_text(v, 500)}" for k, v in value.items()]
        text = "; ".join(parts)
    else:
        text = str(value)

    text = text.replace("\x00", "")

    if len(text) > limit:
        return text[:limit] + "..."

    return text


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def rational_to_float(value: Any) -> float:
    try:
        return float(value)
    except Exception:
        pass

    if isinstance(value, tuple) and len(value) == 2:
        numerator, denominator = value
        try:
            return float(numerator) / float(denominator)
        except Exception:
            return 0.0

    return 0.0


def gps_coord_to_decimal(coord: Any, ref: str) -> Optional[float]:
    try:
        degrees = rational_to_float(coord[0])
        minutes = rational_to_float(coord[1])
        seconds = rational_to_float(coord[2])

        decimal = degrees + minutes / 60.0 + seconds / 3600.0

        if ref in {"S", "W"}:
            decimal *= -1

        return decimal
    except Exception:
        return None


def decode_gps(raw_gps: Dict[Any, Any]) -> Dict[str, Any]:
    decoded: Dict[str, Any] = {}

    if not raw_gps or ExifTags is None:
        return decoded

    for key, value in raw_gps.items():
        name = ExifTags.GPSTAGS.get(key, key)
        decoded[str(name)] = value

    lat = gps_coord_to_decimal(decoded.get("GPSLatitude"), safe_text(decoded.get("GPSLatitudeRef")))
    lon = gps_coord_to_decimal(decoded.get("GPSLongitude"), safe_text(decoded.get("GPSLongitudeRef")))

    if lat is not None:
        decoded["GPSLatitudeDecimal"] = lat

    if lon is not None:
        decoded["GPSLongitudeDecimal"] = lon

    if lat is not None and lon is not None:
        decoded["GoogleMaps"] = f"https://maps.google.com/?q={lat},{lon}"

    return decoded


def count_metadata(path: Path) -> int:
    if Image is None:
        return 0

    try:
        with Image.open(path) as img:
            count = 0

            try:
                count += len(img.getexif() or {})
            except Exception:
                pass

            try:
                count += len(img.info or {})
            except Exception:
                pass

            return count
    except Exception:
        return 0


def read_metadata(path: Path) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "path": path,
        "file": {},
        "image": {},
        "exif": {},
        "gps": {},
        "embedded": {},
        "warnings": [],
    }

    stat = path.stat()

    result["file"] = {
        "Name": path.name,
        "Path": str(path),
        "Extension": path.suffix.lower(),
        "Size": human_bytes(stat.st_size),
        "SizeBytes": stat.st_size,
        "Created": datetime.fromtimestamp(stat.st_ctime).strftime("%Y-%m-%d %H:%M:%S"),
        "Modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
    }

    if Image is None:
        result["warnings"].append("Pillow is not installed, so only basic file metadata can be shown.")
        return result

    try:
        with Image.open(path) as img:
            result["image"] = {
                "Format": safe_text(img.format),
                "Mode": safe_text(img.mode),
                "Width": img.size[0],
                "Height": img.size[1],
                "Frames": getattr(img, "n_frames", 1),
            }

            embedded = {}

            for key, value in (img.info or {}).items():
                if key.lower() in {"exif", "icc_profile", "xmp"} and isinstance(value, bytes):
                    embedded[key] = f"<embedded {key}: {len(value)} bytes>"
                else:
                    embedded[key] = value

            result["embedded"] = embedded

            try:
                exif = img.getexif()
            except Exception as error:
                exif = None
                result["warnings"].append(f"Could not read EXIF: {error}")

            if exif:
                decoded_exif: Dict[str, Any] = {}

                for tag_id, value in exif.items():
                    tag_name = ExifTags.TAGS.get(tag_id, tag_id) if ExifTags else tag_id

                    if tag_name == "GPSInfo":
                        continue

                    decoded_exif[str(tag_name)] = value

                result["exif"] = decoded_exif

                gps_data: Dict[Any, Any] = {}

                try:
                    if hasattr(ExifTags, "IFD"):
                        gps_data = dict(exif.get_ifd(ExifTags.IFD.GPSInfo) or {})
                except Exception:
                    gps_data = {}

                if not gps_data:
                    try:
                        raw_gps = exif.get(34853)

                        if isinstance(raw_gps, dict):
                            gps_data = dict(raw_gps)
                    except Exception:
                        gps_data = {}

                if gps_data:
                    result["gps"] = decode_gps(gps_data)

    except Exception as error:
        result["warnings"].append(f"Could not inspect image metadata: {error}")

    return result


def metadata_rows(metadata: Dict[str, Any]) -> List[Tuple[str, str, str]]:
    rows: List[Tuple[str, str, str]] = []

    for category in ["file", "image", "gps", "exif", "embedded"]:
        values = metadata.get(category, {}) or {}
        label = category.title()

        for key in sorted(values.keys(), key=lambda item: str(item).lower()):
            rows.append((label, safe_text(key), safe_text(values[key])))

    for warning in metadata.get("warnings", []) or []:
        rows.append(("Warning", "Notice", safe_text(warning)))

    if not rows:
        rows.append(("Status", "Result", "No metadata found."))

    return rows


def report_text(metadata: Dict[str, Any]) -> str:
    path = metadata.get("path")

    lines = [
        APP_NAME,
        "Metadata inspection report",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        f"File: {path}",
        "",
    ]

    rows = metadata_rows(metadata)
    current_category = None

    for category, field, value in rows:
        if category != current_category:
            lines.append(f"[{category}]")
            current_category = category

        lines.append(f"{field}: {value}")

    lines.append("")

    return "\n".join(lines)


def output_path_for_clean_copy(input_path: Path, image_format: Optional[str]) -> Tuple[Path, str]:
    suffix = input_path.suffix.lower()
    fmt = (image_format or "").upper()

    if suffix in {".jpg", ".jpeg"}:
        save_format = "JPEG"
        output_suffix = suffix
    elif suffix == ".png":
        save_format = "PNG"
        output_suffix = ".png"
    elif suffix == ".webp":
        save_format = "WEBP"
        output_suffix = ".webp"
    elif suffix in {".tif", ".tiff"}:
        save_format = "TIFF"
        output_suffix = suffix
    elif suffix == ".bmp":
        save_format = "BMP"
        output_suffix = ".bmp"
    elif fmt in {"JPEG", "JPG"}:
        save_format = "JPEG"
        output_suffix = ".jpg"
    elif fmt in {"PNG", "WEBP", "TIFF", "BMP"}:
        save_format = fmt
        output_suffix = ".tif" if fmt == "TIFF" else f".{fmt.lower()}"
    else:
        save_format = "PNG"
        output_suffix = ".png"

    destination = outputs_dir() / f"{input_path.stem}_clean_{now_stamp()}{output_suffix}"

    return destination, save_format


def clean_metadata_from_image(input_path: Path) -> Dict[str, Any]:
    if Image is None or ImageOps is None:
        raise RuntimeError("Pillow is not installed. Install it with: pip install pillow")

    if not input_path.exists():
        raise FileNotFoundError(f"Input file does not exist: {input_path}")

    original_hash_before = sha256_file(input_path)
    before_count = count_metadata(input_path)

    with Image.open(input_path) as img:
        destination, save_format = output_path_for_clean_copy(input_path, img.format)

        try:
            clean_img = ImageOps.exif_transpose(img)
        except Exception:
            clean_img = img.copy()

        if save_format == "JPEG":
            if clean_img.mode in {"RGBA", "LA"}:
                background = Image.new("RGB", clean_img.size, "white")
                alpha = clean_img.getchannel("A") if "A" in clean_img.getbands() else None
                background.paste(clean_img.convert("RGBA"), mask=alpha)
                clean_img = background
            elif clean_img.mode not in {"RGB", "L"}:
                clean_img = clean_img.convert("RGB")

            clean_img.save(destination, format="JPEG", quality=95, optimize=True)

        elif save_format == "PNG":
            clean_img.save(destination, format="PNG", optimize=True)

        elif save_format == "WEBP":
            clean_img.save(destination, format="WEBP", quality=95, method=6)

        elif save_format == "TIFF":
            clean_img.save(destination, format="TIFF")

        elif save_format == "BMP":
            clean_img.save(destination, format="BMP")

        else:
            clean_img.save(destination, format=save_format)

    after_count = count_metadata(destination)
    original_hash_after = sha256_file(input_path)
    original_unchanged = original_hash_before == original_hash_after

    report_path = outputs_dir() / f"{input_path.stem}_clean_report_{now_stamp()}.txt"

    summary = [
        APP_NAME,
        "Clean metadata report",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        f"Original file: {input_path}",
        f"Cleaned copy: {destination}",
        f"Original unchanged: {'YES' if original_unchanged else 'NO'}",
        f"Tags before: {before_count}",
        f"Tags after: {after_count}",
        f"Removed tags: {max(before_count - after_count, 0)}",
        "",
        "Recommendation: open the cleaned copy in this app and review remaining metadata.",
    ]

    report_path.write_text("\n".join(summary), encoding="utf-8")

    return {
        "source_path": str(input_path),
        "output_path": str(destination),
        "report_path": str(report_path),
        "before_tag_count": before_count,
        "after_tag_count": after_count,
        "removed_tag_count": max(before_count - after_count, 0),
        "original_unchanged": original_unchanged,
    }

from kai_metadata_inspector.core.exiftool_runner import get_exiftool_version
from kai_metadata_inspector.core.folder_summary import find_supported_files, build_folder_summary, build_folder_summary_csv


from io import BytesIO
from PIL import Image, ImageOps

try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
    HEIC_PREVIEW_AVAILABLE = True
except Exception:
    HEIC_PREVIEW_AVAILABLE = False

from PySide6.QtGui import QAction

from PySide6.QtWidgets import QListWidget, QListWidgetItem


from PySide6.QtWidgets import QLineEdit, QTextEdit

from kai_metadata_inspector.core.metadata_writer import write_metadata_to_original

class MainWindow(QMainWindow):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__()

        self.current_path: Optional[Path] = None
        self.current_metadata: Optional[Dict[str, Any]] = None

        self.current_folder: Optional[Path] = None
        self.folder_files: List[Path] = []
        self.folder_index: int = 0
        self.folder_summary: Optional[Dict[str, Any]] = None
        self.folder_summary_report: Optional[str] = None

        self.setWindowTitle(APP_NAME)
        self.resize(1120, 760)
        self.setAcceptDrops(True)

        self._build_ui()
        self._build_menu()
        self._apply_dark_style()


        self.status_label.setText("Status: Ready. Open or drag an image file to inspect metadata.")

    def _build_menu(self) -> None:
        help_menu = self.menuBar().addMenu("Help")

        about_action = QAction("About Kai Metadata Inspector", self)
        privacy_action = QAction("Privacy and safety notes", self)
        formats_action = QAction("Supported formats", self)
        cleaning_action = QAction("Cleaning mode notes", self)

        about_action.triggered.connect(self.show_about_dialog)
        privacy_action.triggered.connect(self.show_privacy_dialog)
        formats_action.triggered.connect(self.show_supported_formats_dialog)
        cleaning_action.triggered.connect(self.show_cleaning_notes_dialog)

        help_menu.addAction(about_action)
        help_menu.addAction(privacy_action)
        help_menu.addAction(formats_action)
        help_menu.addAction(cleaning_action)

    def show_about_dialog(self) -> None:
        QMessageBox.information(
            self,
            "About Kai Metadata Inspector",
            (
                "Kai Metadata Inspector\n\n"
                "A privacy-focused image metadata inspection tool for Linux.\n\n"
                "Main features:\n"
                "- Inspect image metadata\n"
                "- Preview common image formats\n"
                "- HEIC/HEIF preview support when available\n"
                "- Search and read metadata in a clean table\n"
                "- Export reports\n"
                "- Scan folders\n"
                "- Create cleaned copies without modifying originals\n\n"
                "Design goal:\n"
                "Help users understand what their images reveal before sharing them."
            ),
        )

    def show_privacy_dialog(self) -> None:
        QMessageBox.warning(
            self,
            "Privacy and safety notes",
            (
                "Metadata can reveal sensitive information.\n\n"
                "Images may contain:\n"
                "- GPS coordinates\n"
                "- Date and time\n"
                "- Camera or phone model\n"
                "- Software/editing history\n"
                "- Device serial numbers\n"
                "- Owner or copyright information\n\n"
                "This app is designed to be offline-first and read-only for inspection.\n\n"
                "Exported TXT/JSON/CSV reports may also contain sensitive information. "
                "Review reports before sharing them."
            ),
        )

    def show_supported_formats_dialog(self) -> None:
        QMessageBox.information(
            self,
            "Supported formats",
            (
                "Metadata extraction is powered mainly by ExifTool.\n\n"
                "Common target formats:\n"
                "- JPG / JPEG\n"
                "- PNG\n"
                "- WEBP\n"
                "- HEIC / HEIF\n"
                "- TIFF\n"
                "- BMP\n"
                "- GIF\n"
                "- AVIF\n"
                "- DNG and RAW camera files where supported by ExifTool\n"
                "- XMP sidecar files\n\n"
                "Preview support depends on installed image libraries.\n"
                "Some files may extract metadata correctly even if preview is unavailable."
            ),
        )

    def show_cleaning_notes_dialog(self) -> None:
        QMessageBox.warning(
            self,
            "Cleaning mode notes",
            (
                "Cleaning mode creates a NEW cleaned copy.\n\n"
                "Safety rules:\n"
                "- The original file should not be modified\n"
                "- A new cleaned copy is created\n"
                "- A cleaning report is generated\n"
                "- SHA256 checks are used to confirm the original stayed unchanged\n\n"
                "Important limitation:\n"
                "No metadata cleaner can guarantee that every hidden or proprietary field "
                "has been removed from every file format.\n\n"
                "Always open and inspect the cleaned copy before sharing."
            ),
        )

    def _build_ui(self) -> None:
        central = QWidget(self)
        self.setCentralWidget(central)

        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.setSpacing(10)

        title = QLabel(APP_NAME)
        title.setObjectName("TitleLabel")
        root_layout.addWidget(title)

        button_row = QHBoxLayout()

        self.open_button = QPushButton("Open image")
        self.inspect_button = QPushButton("Inspect metadata")
        self.export_button = QPushButton("Export report")
        self.clean_button = QPushButton("Create cleaned copy")
        self.write_metadata_button = QPushButton("Edit metadata")
        self.outputs_button = QPushButton("Open outputs")
        self.clear_button = QPushButton("Clear")

        for button in [
            self.open_button,
            self.inspect_button,
            self.export_button,
            self.clean_button,
            self.write_metadata_button,
            self.outputs_button,
            self.clear_button,
        ]:
            button.setMinimumHeight(34)
            button_row.addWidget(button)

        button_row.addStretch(1)
        root_layout.addLayout(button_row)

        folder_tools_label = QLabel("Folder tools")
        folder_tools_label.setObjectName("SectionLabel")
        root_layout.addWidget(folder_tools_label)

        folder_button_row = QHBoxLayout()

        self.open_folder_button = QPushButton("Open folder")
        self.previous_folder_file_button = QPushButton("Previous file")
        self.next_folder_file_button = QPushButton("Next file")
        self.scan_folder_button = QPushButton("Scan folder summary")
        self.export_folder_summary_button = QPushButton("Export folder summary")
        self.export_folder_csv_button = QPushButton("Export folder CSV")
        self.export_all_reports_button = QPushButton("Export all reports")
        self.export_all_json_button = QPushButton("Export all JSON")

        self.previous_folder_file_button.setEnabled(False)
        self.next_folder_file_button.setEnabled(False)
        self.scan_folder_button.setEnabled(False)
        self.export_folder_summary_button.setEnabled(False)
        self.export_folder_csv_button.setEnabled(False)
        self.export_all_reports_button.setEnabled(False)
        self.export_all_json_button.setEnabled(False)

        for button in [
            self.open_folder_button,
            self.previous_folder_file_button,
            self.next_folder_file_button,
            self.scan_folder_button,
            self.export_folder_summary_button,
            self.export_folder_csv_button,
            self.export_all_reports_button,
            self.export_all_json_button,
        ]:
            button.setMinimumHeight(34)
            folder_button_row.addWidget(button)

        folder_button_row.addStretch(1)
        root_layout.addLayout(folder_button_row)

        self.path_label = QLabel("No file selected")
        self.path_label.setObjectName("PathLabel")
        self.path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        root_layout.addWidget(self.path_label)

        self.metadata_editor_group = QGroupBox("Edit metadata")
        self.metadata_editor_group.setVisible(False)

        metadata_editor_layout = QGridLayout(self.metadata_editor_group)

        self.edit_title_input = QLineEdit()
        self.edit_description_input = QTextEdit()
        self.edit_description_input.setMaximumHeight(70)
        self.edit_creator_input = QLineEdit()
        self.edit_rights_input = QLineEdit()
        self.edit_keywords_input = QLineEdit()

        self.edit_camera_make_input = QLineEdit()
        self.edit_camera_model_input = QLineEdit()
        self.edit_lens_make_input = QLineEdit()
        self.edit_lens_model_input = QLineEdit()
        self.edit_gps_latitude_input = QLineEdit()
        self.edit_gps_longitude_input = QLineEdit()
        self.edit_gps_altitude_input = QLineEdit()
        self.edit_date_taken_input = QLineEdit()

        self.edit_title_input.setPlaceholderText("Optional title")
        self.edit_description_input.setPlaceholderText("Optional description")
        self.edit_creator_input.setPlaceholderText("Creator / Author")
        self.edit_rights_input.setPlaceholderText("Copyright / Rights")
        self.edit_keywords_input.setPlaceholderText("Example: travel, product, personal")
        self.edit_camera_make_input.setPlaceholderText("Example: Apple, Samsung, Canon")
        self.edit_camera_model_input.setPlaceholderText("Example: iPhone XS, Galaxy S23, EOS R6")
        self.edit_lens_make_input.setPlaceholderText("Example: Canon, Nikon, Sony")
        self.edit_lens_model_input.setPlaceholderText("Example: EF 50mm f/1.8")
        self.edit_gps_latitude_input.setPlaceholderText("Decimal degrees: 53.5431 or -53.5431")
        self.edit_gps_longitude_input.setPlaceholderText("Decimal degrees: -2.6327 or 2.6327")
        self.edit_gps_altitude_input.setPlaceholderText("Metres, optional")
        self.edit_date_taken_input.setPlaceholderText("EXIF format: YYYY:MM:DD HH:MM:SS")

        self.save_metadata_button = QPushButton("Save metadata")
        self.clear_metadata_fields_button = QPushButton("Clear fields")
        self.cancel_metadata_button = QPushButton("Cancel edit")

        metadata_editor_layout.addWidget(QLabel("Title"), 0, 0)
        metadata_editor_layout.addWidget(self.edit_title_input, 0, 1)

        metadata_editor_layout.addWidget(QLabel("Description"), 1, 0)
        metadata_editor_layout.addWidget(self.edit_description_input, 1, 1)

        metadata_editor_layout.addWidget(QLabel("Creator / Author"), 2, 0)
        metadata_editor_layout.addWidget(self.edit_creator_input, 2, 1)

        metadata_editor_layout.addWidget(QLabel("Copyright / Rights"), 3, 0)
        metadata_editor_layout.addWidget(self.edit_rights_input, 3, 1)

        metadata_editor_layout.addWidget(QLabel("Keywords"), 4, 0)
        metadata_editor_layout.addWidget(self.edit_keywords_input, 4, 1)

        metadata_editor_layout.addWidget(QLabel("Camera make"), 5, 0)
        metadata_editor_layout.addWidget(self.edit_camera_make_input, 5, 1)

        metadata_editor_layout.addWidget(QLabel("Camera / phone model"), 6, 0)
        metadata_editor_layout.addWidget(self.edit_camera_model_input, 6, 1)

        metadata_editor_layout.addWidget(QLabel("Lens make"), 7, 0)
        metadata_editor_layout.addWidget(self.edit_lens_make_input, 7, 1)

        metadata_editor_layout.addWidget(QLabel("Lens model"), 8, 0)
        metadata_editor_layout.addWidget(self.edit_lens_model_input, 8, 1)

        metadata_editor_layout.addWidget(QLabel("GPS latitude"), 9, 0)
        metadata_editor_layout.addWidget(self.edit_gps_latitude_input, 9, 1)

        metadata_editor_layout.addWidget(QLabel("GPS longitude"), 10, 0)
        metadata_editor_layout.addWidget(self.edit_gps_longitude_input, 10, 1)

        metadata_editor_layout.addWidget(QLabel("GPS altitude"), 11, 0)
        metadata_editor_layout.addWidget(self.edit_gps_altitude_input, 11, 1)

        metadata_editor_layout.addWidget(QLabel("Date/time taken"), 12, 0)
        metadata_editor_layout.addWidget(self.edit_date_taken_input, 12, 1)

        editor_note = QLabel(
            "Note: saving writes metadata directly to the selected original file. "
            "GPS uses decimal degrees. Date/time uses YYYY:MM:DD HH:MM:SS."
        )
        editor_note.setObjectName("PathLabel")
        metadata_editor_layout.addWidget(editor_note, 13, 1)

        editor_button_row = QHBoxLayout()
        editor_button_row.addWidget(self.save_metadata_button)
        editor_button_row.addWidget(self.clear_metadata_fields_button)
        editor_button_row.addWidget(self.cancel_metadata_button)
        editor_button_row.addStretch(1)

        metadata_editor_layout.addLayout(editor_button_row, 14, 1)

        root_layout.addWidget(self.metadata_editor_group)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        root_layout.addWidget(splitter, stretch=1)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 8, 0)

        preview_group = QGroupBox("Preview")
        preview_layout = QVBoxLayout(preview_group)

        self.preview_label = QLabel("Open an image to preview it here")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setFrameShape(QFrame.Shape.StyledPanel)
        self.preview_label.setMinimumSize(360, 360)
        self.preview_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.preview_label.setScaledContents(False)

        preview_layout.addWidget(self.preview_label)
        left_layout.addWidget(preview_group, stretch=3)

        quick_group = QGroupBox("Quick summary")
        quick_layout = QGridLayout(quick_group)

        self.summary_file = QLabel("-")
        self.summary_size = QLabel("-")
        self.summary_dimensions = QLabel("-")
        self.summary_gps = QLabel("-")

        for label in [
            self.summary_file,
            self.summary_size,
            self.summary_dimensions,
            self.summary_gps,
        ]:
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            label.setWordWrap(True)

        quick_layout.addWidget(QLabel("File:"), 0, 0)
        quick_layout.addWidget(self.summary_file, 0, 1)

        quick_layout.addWidget(QLabel("Size:"), 1, 0)
        quick_layout.addWidget(self.summary_size, 1, 1)

        quick_layout.addWidget(QLabel("Dimensions:"), 2, 0)
        quick_layout.addWidget(self.summary_dimensions, 2, 1)

        quick_layout.addWidget(QLabel("GPS:"), 3, 0)
        quick_layout.addWidget(self.summary_gps, 3, 1)

        left_layout.addWidget(quick_group, stretch=1)

        folder_files_group = QGroupBox("Folder files")
        folder_files_layout = QVBoxLayout(folder_files_group)

        self.folder_file_list = QListWidget()
        self.folder_file_list.setMinimumHeight(120)
        self.folder_file_list.itemClicked.connect(self.load_selected_folder_file)

        folder_files_layout.addWidget(self.folder_file_list)
        left_layout.addWidget(folder_files_group, stretch=1)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(8, 0, 0, 0)

        metadata_group = QGroupBox("Metadata")
        metadata_layout = QVBoxLayout(metadata_group)

        self.metadata_table = QTableWidget(0, 3)
        self.metadata_table.setHorizontalHeaderLabels(["Category", "Field", "Value"])
        self.metadata_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.metadata_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.metadata_table.verticalHeader().setVisible(False)
        self.metadata_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.metadata_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.metadata_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)

        metadata_layout.addWidget(self.metadata_table)
        right_layout.addWidget(metadata_group, stretch=3)

        report_group = QGroupBox("Report text")
        report_layout = QVBoxLayout(report_group)

        self.report_box = QPlainTextEdit()
        self.report_box.setReadOnly(True)
        self.report_box.setPlaceholderText("The plain-text report will appear here after inspection.")

        report_layout.addWidget(self.report_box)
        right_layout.addWidget(report_group, stretch=2)

        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([420, 700])

        self.status_label = QLabel("Status: Ready")
        self.status_label.setObjectName("StatusLabel")
        self.status_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        root_layout.addWidget(self.status_label)





        self.open_button.clicked.connect(self.open_file_dialog)
        self.inspect_button.clicked.connect(self.inspect_current_file)
        self.export_button.clicked.connect(self.export_report)
        self.clean_button.clicked.connect(self.create_clean_copy)
        self.write_metadata_button.clicked.connect(self.show_metadata_editor)
        self.save_metadata_button.clicked.connect(self.save_new_metadata)
        self.clear_metadata_fields_button.clicked.connect(self.clear_metadata_editor_fields)
        self.cancel_metadata_button.clicked.connect(self.hide_metadata_editor)
        self.outputs_button.clicked.connect(self.open_outputs_folder)

        self.open_folder_button.clicked.connect(self.open_folder_dialog)
        self.previous_folder_file_button.clicked.connect(self.load_previous_folder_file)
        self.next_folder_file_button.clicked.connect(self.load_next_folder_file)
        self.scan_folder_button.clicked.connect(self.scan_folder_summary)
        self.export_folder_summary_button.clicked.connect(self.export_folder_summary)
        self.export_folder_csv_button.clicked.connect(self.export_folder_csv)
        self.export_all_reports_button.clicked.connect(self.export_all_reports)
        self.export_all_json_button.clicked.connect(self.export_all_json)
        self.clear_button.clicked.connect(self.clear_view)

    def _apply_dark_style(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow, QWidget {
                background-color: #121212;
                color: #eeeeee;
                font-size: 13px;
            }

            QLabel#TitleLabel {
                font-size: 24px;
                font-weight: bold;
                color: #ffffff;
            }

            QLabel#PathLabel, QLabel#StatusLabel {
                color: #cfcfcf;
                padding: 4px;
            }

            QPushButton {
                background-color: #242424;
                color: #ffffff;
                border: 1px solid #5a5a5a;
                border-radius: 6px;
                padding: 7px 11px;
            }

            QPushButton:hover {
                background-color: #333333;
            }

            QPushButton:pressed {
                background-color: #444444;
            }

            QGroupBox {
                border: 1px solid #444444;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
                font-weight: bold;
            }

            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 4px;
            }

            QTableWidget, QPlainTextEdit {
                background-color: #181818;
                color: #eeeeee;
                border: 1px solid #444444;
                gridline-color: #333333;
                selection-background-color: #3a3a3a;
            }

            QHeaderView::section {
                background-color: #252525;
                color: #ffffff;
                border: 1px solid #444444;
                padding: 5px;
            }
            """
        )

    def open_file_dialog(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open image file",
            str(Path.home()),
            "Image files (*.jpg *.jpeg *.png *.webp *.tif *.tiff *.bmp *.gif *.heic *.heif);;All files (*.*)",
        )

        if file_path:
            self.load_file(Path(file_path))

    def load_file(self, path: Path) -> None:
        path = Path(path).expanduser().resolve()

        if not path.exists():
            QMessageBox.warning(self, "File not found", f"File does not exist:\n{path}")
            return

        self.current_path = path
        self.path_label.setText(f"Selected: {path}")
        self.status_label.setText("Status: File loaded. Inspecting metadata...")

        self._update_preview(path)
        self.inspect_current_file()

    def _update_preview(self, path: Path) -> None:
        """
        Load image preview.

        Uses Pillow ImageOps.exif_transpose so phone photos with EXIF orientation
        display correctly without modifying the original file.
        """

        self.preview_label.setPixmap(QPixmap())

        try:
            with Image.open(path) as image:
                image = ImageOps.exif_transpose(image)

                # Convert unusual modes into something Qt can preview reliably.
                if image.mode not in ("RGB", "RGBA"):
                    image = image.convert("RGB")

                buffer = BytesIO()
                image.save(buffer, format="PNG")
                image_bytes = buffer.getvalue()

            pixmap = QPixmap()
            loaded = pixmap.loadFromData(image_bytes, "PNG")

            if not loaded or pixmap.isNull():
                self.preview_label.setText("Preview unavailable for this file type")
                return

            target_size = self.preview_label.size()
            scaled = pixmap.scaled(
                target_size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )

            self.preview_label.setText("")
            self.preview_label.setPixmap(scaled)

        except Exception:
            # Fallback to Qt's normal loader if Pillow cannot read the file.
            pixmap = QPixmap(str(path))

            if pixmap.isNull():
                self.preview_label.setText("Preview unavailable for this file type")
                self.preview_label.setPixmap(QPixmap())
                return

            target_size = self.preview_label.size()
            scaled = pixmap.scaled(
                target_size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )

            self.preview_label.setText("")
            self.preview_label.setPixmap(scaled)

    def resizeEvent(self, event: Any) -> None:
        super().resizeEvent(event)

        if self.current_path:
            self._update_preview(self.current_path)

    def inspect_current_file(self) -> None:
        if not self.current_path:
            QMessageBox.information(self, "No file selected", "Open an image file first.")
            return

        try:
            metadata = read_metadata(self.current_path)
        except Exception as error:
            QMessageBox.critical(self, "Inspection error", f"Could not inspect metadata:\n{error}")
            self.status_label.setText("Status: Error while inspecting metadata.")
            return

        self.current_metadata = metadata

        self._fill_table(metadata)
        self._fill_summary(metadata)

        self.report_box.setPlainText(report_text(metadata))

        row_count = self.metadata_table.rowCount()
        self.status_label.setText(f"Status: Inspection complete. {row_count} metadata rows shown.")

    def _fill_table(self, metadata: Dict[str, Any]) -> None:
        rows = metadata_rows(metadata)

        self.metadata_table.setRowCount(len(rows))

        for row_index, (category, field, value) in enumerate(rows):
            for col_index, text in enumerate([category, field, value]):
                item = QTableWidgetItem(text)
                item.setToolTip(text)
                self.metadata_table.setItem(row_index, col_index, item)

        self.metadata_table.resizeRowsToContents()

    def _fill_summary(self, metadata: Dict[str, Any]) -> None:
        file_meta = metadata.get("file", {}) or {}
        image_meta = metadata.get("image", {}) or {}
        gps_meta = metadata.get("gps", {}) or {}

        self.summary_file.setText(safe_text(file_meta.get("Name", "-")))
        self.summary_size.setText(safe_text(file_meta.get("Size", "-")))

        width = image_meta.get("Width")
        height = image_meta.get("Height")
        fmt = image_meta.get("Format", "")

        if width and height:
            self.summary_dimensions.setText(f"{width} x {height} ({fmt})")
        else:
            self.summary_dimensions.setText("-")

        lat = gps_meta.get("GPSLatitudeDecimal")
        lon = gps_meta.get("GPSLongitudeDecimal")

        if lat is not None and lon is not None:
            self.summary_gps.setText(f"{lat}, {lon}")
        else:
            self.summary_gps.setText("No GPS coordinates found")

    def export_report(self) -> None:
        if not self.current_path:
            QMessageBox.information(self, "No file selected", "Open and inspect an image first.")
            return

        if self.current_metadata is None:
            self.inspect_current_file()

        if self.current_metadata is None:
            return

        default_path = outputs_dir() / f"{self.current_path.stem}_metadata_report_{now_stamp()}.txt"

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save report",
            str(default_path),
            "Text files (*.txt);;All files (*.*)",
        )

        if not file_path:
            return

        destination = Path(file_path)

        try:
            destination.write_text(report_text(self.current_metadata), encoding="utf-8")
        except Exception as error:
            QMessageBox.critical(self, "Export error", f"Could not save report:\n{error}")
            self.status_label.setText("Status: Error while exporting report.")
            return

        QMessageBox.information(self, "Report exported", f"Report saved to:\n{destination}")
        self.status_label.setText(f"Status: Report exported to {destination}")

    def _find_metadata_value(self, metadata: Dict[str, Any], possible_names: List[str]) -> str:
        possible_lower = [name.lower() for name in possible_names]

        def search(value: Any) -> Optional[str]:
            if isinstance(value, dict):
                for key, item in value.items():
                    key_lower = str(key).lower()

                    for possible in possible_lower:
                        if possible == key_lower or possible in key_lower:
                            if isinstance(item, (str, int, float)):
                                return str(item)
                            if isinstance(item, list):
                                return ", ".join(str(x) for x in item)

                    found = search(item)
                    if found:
                        return found

            elif isinstance(value, list):
                for item in value:
                    found = search(item)
                    if found:
                        return found

            return None

        return search(metadata) or ""

    def show_metadata_editor(self) -> None:
        if not self.current_path:
            QMessageBox.information(self, "No file selected", "Open an image file first.")
            return

        if self.current_metadata is None:
            self.inspect_current_file()

        metadata = self.current_metadata or {}

        self.edit_title_input.setText(
            self._find_metadata_value(metadata, ["title", "headline", "xmp-dc:title"])
        )

        self.edit_description_input.setPlainText(
            self._find_metadata_value(
                metadata,
                ["description", "caption", "image description", "xmp-dc:description"],
            )
        )

        self.edit_creator_input.setText(
            self._find_metadata_value(metadata, ["creator", "artist", "author", "xmp-dc:creator"])
        )

        self.edit_rights_input.setText(
            self._find_metadata_value(metadata, ["rights", "copyright", "xmp-dc:rights"])
        )

        self.edit_keywords_input.setText(
            self._find_metadata_value(metadata, ["keywords", "subject", "xmp-dc:subject"])
        )

        self.edit_camera_make_input.setText(
            self._find_metadata_value(metadata, ["make", "camera make", "xmp-tiff:make"])
        )

        self.edit_camera_model_input.setText(
            self._find_metadata_value(metadata, ["model", "camera model", "hostcomputer", "xmp-tiff:model"])
        )

        self.edit_lens_make_input.setText(
            self._find_metadata_value(metadata, ["lensmake", "lens make"])
        )

        self.edit_lens_model_input.setText(
            self._find_metadata_value(metadata, ["lensmodel", "lens model"])
        )

        self.edit_gps_latitude_input.setText(
            self._find_metadata_value(metadata, ["gpslatitudedecimal", "gpslatitude"])
        )

        self.edit_gps_longitude_input.setText(
            self._find_metadata_value(metadata, ["gpslongitudedecimal", "gpslongitude"])
        )

        self.edit_gps_altitude_input.setText(
            self._find_metadata_value(metadata, ["gpsaltitude"])
        )

        self.edit_date_taken_input.setText(
            self._find_metadata_value(metadata, ["datetimeoriginal", "createdate", "date/time original", "datetime"])
        )

        self.metadata_editor_group.setVisible(True)
        self.status_label.setText("Status: Metadata editor opened.")

    def hide_metadata_editor(self) -> None:
        self.metadata_editor_group.setVisible(False)
        self.status_label.setText("Status: Metadata editor closed.")

    def clear_metadata_editor_fields(self) -> None:
        self.edit_title_input.clear()
        self.edit_description_input.clear()
        self.edit_creator_input.clear()
        self.edit_rights_input.clear()
        self.edit_keywords_input.clear()
        self.edit_camera_make_input.clear()
        self.edit_camera_model_input.clear()
        self.edit_lens_make_input.clear()
        self.edit_lens_model_input.clear()
        self.edit_gps_latitude_input.clear()
        self.edit_gps_longitude_input.clear()
        self.edit_gps_altitude_input.clear()
        self.edit_date_taken_input.clear()
        self.status_label.setText("Status: Metadata editor fields cleared.")

    def save_new_metadata(self) -> None:
        if not self.current_path:
            QMessageBox.information(self, "No file selected", "Open an image file first.")
            return

        keywords = [
            keyword.strip()
            for keyword in self.edit_keywords_input.text().split(",")
            if keyword.strip()
        ]

        fields = {
            "title": self.edit_title_input.text().strip(),
            "description": self.edit_description_input.toPlainText().strip(),
            "creator": self.edit_creator_input.text().strip(),
            "rights": self.edit_rights_input.text().strip(),
            "keywords": keywords,
            "camera_make": self.edit_camera_make_input.text().strip(),
            "camera_model": self.edit_camera_model_input.text().strip(),
            "lens_make": self.edit_lens_make_input.text().strip(),
            "lens_model": self.edit_lens_model_input.text().strip(),
            "gps_latitude": self.edit_gps_latitude_input.text().strip(),
            "gps_longitude": self.edit_gps_longitude_input.text().strip(),
            "gps_altitude": self.edit_gps_altitude_input.text().strip(),
            "date_taken": self.edit_date_taken_input.text().strip(),
        }

        if not any(fields.values()):
            self.status_label.setText("Status: No metadata entered. Nothing saved.")
            return

        try:
            self.status_label.setText("Status: Saving metadata to original file...")
            QApplication.processEvents()

            result = write_metadata_to_original(self.current_path, fields)

            self.load_file(Path(result["file_path"]))
            self.inspect_current_file()
            self.metadata_editor_group.setVisible(False)

            self.status_label.setText(
                f"Status: Metadata saved. Report created: {result['report_path']}"
            )

        except Exception as error:
            QMessageBox.critical(self, "Save metadata error", f"Could not save metadata:\n{error}")
            self.status_label.setText("Status: Error while saving metadata.")

    def create_clean_copy(self) -> None:
        if not self.current_path:
            QMessageBox.information(self, "No file selected", "Open an image file first.")
            return

        confirm_reply = QMessageBox.question(
            self,
            "Create cleaned copy?",
            (
                "This will create a NEW copy with metadata removed.\n\n"
                "Your original file will NOT be changed.\n\n"
                "Do you want to continue?"
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if confirm_reply != QMessageBox.StandardButton.Yes:
            self.status_label.setText("Status: Clean copy cancelled.")
            return

        try:
            result = clean_metadata_from_image(self.current_path)
        except Exception as error:
            QMessageBox.critical(self, "Cleaning error", f"Error while creating cleaned copy:\n{error}")
            self.status_label.setText("Status: Error while creating cleaned copy.")
            return

        summary_text = (
            "Cleaned copy created successfully.\n\n"
            f"Original file:\n{result['source_path']}\n\n"
            f"Cleaned copy:\n{result['output_path']}\n\n"
            f"Cleaning report:\n{result['report_path']}\n\n"
            f"Tags before: {result['before_tag_count']}\n"
            f"Tags after: {result['after_tag_count']}\n"
            f"Removed tags: {result['removed_tag_count']}\n\n"
            f"Original unchanged: {'YES' if result['original_unchanged'] else 'NO'}\n\n"
            "Recommended: open the cleaned copy in this app and review remaining metadata."
        )

        QMessageBox.information(self, "Cleaned copy created", summary_text)

        open_reply = QMessageBox.question(
            self,
            "Open cleaned copy?",
            "Do you want to open the cleaned copy now and inspect its remaining metadata?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )

        if open_reply == QMessageBox.StandardButton.Yes:
            self.load_file(Path(result["output_path"]))
            self.status_label.setText(
                f"Status: Cleaned copy opened for verification: {result['output_path']}"
            )
        else:
            self.status_label.setText(f"Status: Cleaned copy created at {result['output_path']}")

    def start_progress(self, maximum: int, text: str) -> None:
        """
        Status-only progress helper.

        Uses the status label for progress feedback.
        """

        self._progress_max = max(1, maximum)
        self._progress_current = 0
        self.status_label.setText(text)
        QApplication.processEvents()

    def update_progress(self, value: int, text: str) -> None:
        self._progress_current = value
        maximum = getattr(self, "_progress_max", 1)
        percent = int((value / maximum) * 100) if maximum else 0
        self.status_label.setText(f"{text} ({percent}%)")
        QApplication.processEvents()

    def finish_progress(self, text: str) -> None:
        self._progress_current = getattr(self, "_progress_max", 1)
        self.status_label.setText(text)
        QApplication.processEvents()

    def hide_progress(self) -> None:
        self._progress_current = 0
        QApplication.processEvents()

    def open_folder_dialog(self) -> None:
        folder_path = QFileDialog.getExistingDirectory(
            self,
            "Open folder containing images",
            str(Path.home()),
        )

        if not folder_path:
            return

        folder = Path(folder_path)

        try:
            files = find_supported_files(folder)
        except Exception as error:
            QMessageBox.critical(self, "Folder error", f"Could not read folder:\n{error}")
            self.status_label.setText("Status: Error while opening folder.")
            return

        self.current_folder = folder
        self.folder_files = files
        self.folder_index = 0
        self.folder_summary = None
        self.folder_summary_report = None

        if hasattr(self, "folder_file_list"):
            self.folder_file_list.clear()

        self.export_folder_summary_button.setEnabled(False)
        self.export_folder_csv_button.setEnabled(False)
        self.export_all_reports_button.setEnabled(False)
        self.export_all_json_button.setEnabled(False)
        self.previous_folder_file_button.setEnabled(False)
        self.next_folder_file_button.setEnabled(False)

        if not files:
            self.scan_folder_button.setEnabled(False)
            self.previous_folder_file_button.setEnabled(False)
            self.next_folder_file_button.setEnabled(False)
            self.export_folder_csv_button.setEnabled(False)
            self.export_all_reports_button.setEnabled(False)
            self.export_all_json_button.setEnabled(False)
            self.report_box.setPlainText(
                f"Folder loaded:\n{folder}\n\nNo supported files were found."
            )
            self.status_label.setText("Status: Folder loaded, but no supported files found.")
            return

        self.scan_folder_button.setEnabled(True)
        self.export_all_reports_button.setEnabled(True)
        self.export_all_json_button.setEnabled(True)
        self.previous_folder_file_button.setEnabled(False)
        self.next_folder_file_button.setEnabled(len(files) > 1)

        if hasattr(self, "folder_file_list"):
            self.folder_file_list.clear()

            for index, file_path in enumerate(files):
                item = QListWidgetItem(f"{index + 1}. {file_path.name}")
                item.setData(Qt.ItemDataRole.UserRole, index)
                self.folder_file_list.addItem(item)

            if files:
                self.folder_file_list.setCurrentRow(0)

        file_list_preview = "\n".join(f"- {file.name}" for file in files[:50])

        if len(files) > 50:
            file_list_preview += f"\n...and {len(files) - 50} more file(s)."

        self.report_box.setPlainText(
            "Folder loaded\n"
            "=============\n\n"
            f"Folder: {folder}\n"
            f"Supported files found: {len(files)}\n\n"
            "Files:\n"
            f"{file_list_preview}\n\n"
            "Click 'Scan folder summary' to analyse the folder."
        )

        self.status_label.setText(
            f"Status: Folder loaded. {len(files)} supported file(s) found. Loading first file..."
        )

        # Automatically inspect the first file in the folder.
        self.load_file(files[0])
        self.status_label.setText(
            f"Status: Folder loaded. Showing 1/{len(files)} — {files[0].name}"
        )

    def load_selected_folder_file(self, item: Any) -> None:
        index = item.data(Qt.ItemDataRole.UserRole)

        if isinstance(index, int):
            self.load_folder_file_at_index(index)

    def load_folder_file_at_index(self, index: int) -> None:
        if not self.folder_files:
            QMessageBox.information(self, "No folder loaded", "Open a folder first.")
            return

        if index < 0 or index >= len(self.folder_files):
            return

        self.folder_index = index
        file_path = self.folder_files[self.folder_index]

        self.previous_folder_file_button.setEnabled(self.folder_index > 0)
        self.next_folder_file_button.setEnabled(self.folder_index < len(self.folder_files) - 1)

        if hasattr(self, "folder_file_list"):
            self.folder_file_list.blockSignals(True)
            self.folder_file_list.setCurrentRow(self.folder_index)
            self.folder_file_list.blockSignals(False)

        self.load_file(file_path)
        self.status_label.setText(
            f"Status: Showing folder file {self.folder_index + 1}/{len(self.folder_files)} — {file_path.name}"
        )

    def load_previous_folder_file(self) -> None:
        self.load_folder_file_at_index(self.folder_index - 1)

    def load_next_folder_file(self) -> None:
        self.load_folder_file_at_index(self.folder_index + 1)

    def scan_folder_summary(self) -> None:
        if not self.current_folder or not self.folder_files:
            QMessageBox.information(self, "No folder loaded", "Open a folder first.")
            return

        if len(self.folder_files) > 100:
            reply = QMessageBox.question(
                self,
                "Large folder warning",
                (
                    f"This will scan {len(self.folder_files)} file(s).\n\n"
                    "The app may pause while scanning.\n\n"
                    "Continue?"
                ),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )

            if reply != QMessageBox.StandardButton.Yes:
                self.status_label.setText("Status: Folder summary cancelled.")
                return

        try:
            self.status_label.setText("Status: Scanning folder summary...")
            self.report_box.setPlainText("Scanning folder summary. Please wait...")
            QApplication.processEvents()

            summary, report = build_folder_summary(
                self.current_folder,
                self.folder_files,
                get_exiftool_version(),
            )

            self.folder_summary = summary
            self.folder_summary_report = report
            self.report_box.setPlainText(report)
            self.export_folder_summary_button.setEnabled(True)
            self.export_folder_csv_button.setEnabled(True)

            self.status_label.setText(
                f"Status: Folder summary complete. {len(self.folder_files)} file(s) checked."
            )

        except Exception as error:
            QMessageBox.critical(self, "Folder summary error", f"Could not scan folder:\n{error}")
            self.status_label.setText("Status: Error while scanning folder summary.")

    def export_folder_summary(self) -> None:
        if not self.folder_summary_report or not self.current_folder:
            QMessageBox.information(
                self,
                "No folder summary",
                "Scan a folder summary first.",
            )
            return

        default_path = outputs_dir() / f"{self.current_folder.name}_folder_summary_{now_stamp()}.txt"

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save folder summary",
            str(default_path),
            "Text files (*.txt);;All files (*.*)",
        )

        if not file_path:
            return

        destination = Path(file_path)

        try:
            destination.write_text(self.folder_summary_report, encoding="utf-8")
        except Exception as error:
            QMessageBox.critical(self, "Export error", f"Could not save folder summary:\n{error}")
            self.status_label.setText("Status: Error while exporting folder summary.")
            return

        QMessageBox.information(
            self,
            "Folder summary exported",
            f"Folder summary saved to:\n{destination}",
        )
        self.status_label.setText(f"Status: Folder summary exported to {destination}")

    def export_folder_csv(self) -> None:
        if not self.folder_summary or not self.current_folder:
            QMessageBox.information(
                self,
                "No folder summary",
                "Scan a folder summary first.",
            )
            return

        default_path = outputs_dir() / f"{self.current_folder.name}_folder_summary_{now_stamp()}.csv"

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save folder summary CSV",
            str(default_path),
            "CSV files (*.csv);;All files (*.*)",
        )

        if not file_path:
            return

        destination = Path(file_path)

        try:
            csv_text = build_folder_summary_csv(self.folder_summary)
            destination.write_text(csv_text, encoding="utf-8")
        except Exception as error:
            QMessageBox.critical(self, "Export error", f"Could not save folder CSV:\n{error}")
            self.status_label.setText("Status: Error while exporting folder CSV.")
            return

        QMessageBox.information(
            self,
            "Folder CSV exported",
            f"Folder CSV saved to:\n{destination}",
        )
        self.status_label.setText(f"Status: Folder CSV exported to {destination}")

    def export_all_reports(self) -> None:
        if not self.current_folder or not self.folder_files:
            QMessageBox.information(self, "No folder loaded", "Open a folder first.")
            return

        confirm_reply = QMessageBox.question(
            self,
            "Export all reports?",
            (
                f"This will inspect and export TXT reports for {len(self.folder_files)} file(s).\n\n"
                "Original files will NOT be modified.\n\n"
                "The app may pause during export.\n\n"
                "Continue?"
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if confirm_reply != QMessageBox.StandardButton.Yes:
            self.status_label.setText("Status: Export all reports cancelled.")
            return

        export_root = outputs_dir() / f"folder_reports_{now_stamp()}"
        reports_dir = export_root / "txt_reports"
        reports_dir.mkdir(parents=True, exist_ok=True)

        exported = 0
        errors: List[str] = []
        used_names: Dict[str, int] = {}

        self.start_progress(
            len(self.folder_files),
            "Status: Exporting folder reports..."
        )

        for index, file_path in enumerate(self.folder_files, start=1):
            try:
                self.update_progress(
                    index,
                    f"Status: Exporting report {index}/{len(self.folder_files)} — {file_path.name}"
                )

                metadata = read_metadata(file_path)
                report = report_text(metadata)

                safe_stem = "".join(
                    char if char.isalnum() or char in "._-" else "_"
                    for char in file_path.stem
                ).strip("_") or "file"

                duplicate_number = used_names.get(safe_stem, 0)
                used_names[safe_stem] = duplicate_number + 1

                if duplicate_number:
                    output_name = f"{safe_stem}_{duplicate_number + 1}_metadata_report.txt"
                else:
                    output_name = f"{safe_stem}_metadata_report.txt"

                output_path = reports_dir / output_name
                output_path.write_text(report, encoding="utf-8")

                exported += 1

            except Exception as error:
                errors.append(f"{file_path.name}: {error}")

        if errors:
            error_log = export_root / "export_errors.txt"
            error_log.write_text("\n".join(errors), encoding="utf-8")

        QMessageBox.information(
            self,
            "Export complete",
            (
                f"Folder report export finished.\n\n"
                f"Exported reports: {exported}\n"
                f"Errors: {len(errors)}\n\n"
                f"Output folder:\n{export_root}"
            ),
        )

        self.finish_progress(
            f"Status: Exported {exported} folder report(s), {len(errors)} error(s)."
        )

    def export_all_json(self) -> None:
        if not self.current_folder or not self.folder_files:
            QMessageBox.information(self, "No folder loaded", "Open a folder first.")
            return

        confirm_reply = QMessageBox.question(
            self,
            "Export all JSON?",
            (
                f"This will inspect and export raw JSON metadata for {len(self.folder_files)} file(s).\n\n"
                "Original files will NOT be modified.\n\n"
                "The app may pause during export.\n\n"
                "Continue?"
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if confirm_reply != QMessageBox.StandardButton.Yes:
            self.status_label.setText("Status: Export all JSON cancelled.")
            return

        export_root = outputs_dir() / f"folder_json_{now_stamp()}"
        json_dir = export_root / "json_metadata"
        json_dir.mkdir(parents=True, exist_ok=True)

        exported = 0
        errors: List[str] = []
        used_names: Dict[str, int] = {}

        self.start_progress(
            len(self.folder_files),
            "Status: Exporting folder JSON metadata..."
        )

        for index, file_path in enumerate(self.folder_files, start=1):
            try:
                self.update_progress(
                    index,
                    f"Status: Exporting JSON {index}/{len(self.folder_files)} — {file_path.name}"
                )

                metadata = read_metadata(file_path)

                safe_stem = "".join(
                    char if char.isalnum() or char in "._-" else "_"
                    for char in file_path.stem
                ).strip("_") or "file"

                duplicate_number = used_names.get(safe_stem, 0)
                used_names[safe_stem] = duplicate_number + 1

                if duplicate_number:
                    output_name = f"{safe_stem}_{duplicate_number + 1}_metadata.json"
                else:
                    output_name = f"{safe_stem}_metadata.json"

                output_path = json_dir / output_name
                output_path.write_text(
                    json.dumps(metadata, indent=2, ensure_ascii=False),
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
                f"Folder JSON export finished.\n\n"
                f"Exported JSON files: {exported}\n"
                f"Errors: {len(errors)}\n\n"
                f"Output folder:\n{export_root}"
            ),
        )

        self.finish_progress(
            f"Status: Exported {exported} JSON file(s), {len(errors)} error(s)."
        )

    def open_outputs_folder(self) -> None:
        folder = outputs_dir()

        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

        self.status_label.setText(f"Status: Opened outputs folder: {folder}")

    def clear_view(self) -> None:
        if hasattr(self, "progress_bar"):
            self.hide_progress()

        self.current_path = None
        self.current_metadata = None

        self.current_folder = None
        self.folder_files = []
        self.folder_index = 0
        self.folder_summary = None
        self.folder_summary_report = None

        if hasattr(self, "folder_file_list"):
            self.folder_file_list.clear()

        if hasattr(self, "previous_folder_file_button"):
            self.previous_folder_file_button.setEnabled(False)

        if hasattr(self, "next_folder_file_button"):
            self.next_folder_file_button.setEnabled(False)

        if hasattr(self, "scan_folder_button"):
            self.scan_folder_button.setEnabled(False)

        if hasattr(self, "export_folder_summary_button"):
            self.export_folder_summary_button.setEnabled(False)

        if hasattr(self, "export_folder_csv_button"):
            self.export_folder_csv_button.setEnabled(False)

        if hasattr(self, "export_all_reports_button"):
            self.export_all_reports_button.setEnabled(False)

        if hasattr(self, "export_all_json_button"):
            self.export_all_json_button.setEnabled(False)

        self.path_label.setText("No file selected")

        self.preview_label.setPixmap(QPixmap())
        self.preview_label.setText("Open an image to preview it here")

        self.metadata_table.setRowCount(0)
        self.report_box.clear()

        self.summary_file.setText("-")
        self.summary_size.setText("-")
        self.summary_dimensions.setText("-")
        self.summary_gps.setText("-")

        self.status_label.setText("Status: Cleared.")

    def dragEnterEvent(self, event: Any) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: Any) -> None:
        urls = event.mimeData().urls()

        if not urls:
            return

        local_path = urls[0].toLocalFile()

        if local_path:
            self.load_file(Path(local_path))


MetadataInspectorWindow = MainWindow
KaiMetadataInspectorWindow = MainWindow


if __name__ == "__main__":
    app = QApplication([])
    window = MainWindow()
    window.show()
    app.exec()