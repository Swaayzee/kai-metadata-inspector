import hashlib
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from kai_metadata_inspector.config import backups_dir
from kai_metadata_inspector.core.exiftool_runner import safe_run_exiftool
from kai_metadata_inspector.core.runtime import run_exiftool


def sha256_file(file_path: Path) -> str:
    hasher = hashlib.sha256()

    with file_path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            hasher.update(chunk)

    return hasher.hexdigest()


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _parse_decimal(value: Any) -> Optional[float]:
    text = _clean_text(value)

    if not text:
        return None

    try:
        return float(text)
    except ValueError:
        raise RuntimeError(f"Invalid decimal number: {text}")


def _gps_ref_lat(latitude: float) -> str:
    return "S" if latitude < 0 else "N"


def _gps_ref_lon(longitude: float) -> str:
    return "W" if longitude < 0 else "E"


def _validate_exif_datetime(value: Any) -> str:
    """
    Expected EXIF format:
    YYYY:MM:DD HH:MM:SS
    """

    text = _clean_text(value)

    if not text:
        return ""

    import re

    if not re.match(r"^\d{4}:\d{2}:\d{2} \d{2}:\d{2}:\d{2}$", text):
        raise RuntimeError("Invalid Date/Time format. Use: YYYY:MM:DD HH:MM:SS")

    return text


def write_metadata_to_original(file_path: Path, fields: Dict[str, Any]) -> dict:
    """
    Writes user-provided metadata directly into the selected original file.

    This modifies the selected file.
    ExifTool is run with:
    - -m to ignore minor warnings like MakerNotes warnings
    - -overwrite_original so no ExifTool backup file is created
    """

    if not file_path.exists():
        raise FileNotFoundError("File does not exist.")

    if not file_path.is_file():
        raise RuntimeError("Selected path is not a file.")

    original_hash_before = sha256_file(file_path)

    cmd = [
        "-m",
        "-overwrite_original",
    ]

    title = _clean_text(fields.get("title", ""))
    description = _clean_text(fields.get("description", ""))
    creator = _clean_text(fields.get("creator", ""))
    rights = _clean_text(fields.get("rights", ""))
    keywords: List[str] = fields.get("keywords", []) or []

    camera_make = _clean_text(fields.get("camera_make", ""))
    camera_model = _clean_text(fields.get("camera_model", ""))
    lens_make = _clean_text(fields.get("lens_make", ""))
    lens_model = _clean_text(fields.get("lens_model", ""))

    gps_latitude = _parse_decimal(fields.get("gps_latitude", ""))
    gps_longitude = _parse_decimal(fields.get("gps_longitude", ""))
    gps_altitude = _parse_decimal(fields.get("gps_altitude", ""))

    date_taken = _validate_exif_datetime(fields.get("date_taken", ""))

    if title:
        cmd.append(f"-XMP-dc:Title={title}")

    if description:
        cmd.append(f"-XMP-dc:Description={description}")
        cmd.append(f"-EXIF:ImageDescription={description}")

    if creator:
        cmd.append(f"-XMP-dc:Creator={creator}")
        cmd.append(f"-EXIF:Artist={creator}")

    if rights:
        cmd.append(f"-XMP-dc:Rights={rights}")
        cmd.append(f"-EXIF:Copyright={rights}")

    for keyword in keywords:
        clean_keyword = str(keyword).strip()
        if clean_keyword:
            cmd.append(f"-XMP-dc:Subject+={clean_keyword}")

    if camera_make:
        cmd.append(f"-EXIF:Make={camera_make}")
        cmd.append(f"-XMP-tiff:Make={camera_make}")

    if camera_model:
        cmd.append(f"-EXIF:Model={camera_model}")
        cmd.append(f"-XMP-tiff:Model={camera_model}")

    if lens_make:
        cmd.append(f"-EXIF:LensMake={lens_make}")
        cmd.append(f"-XMP-exifEX:LensMake={lens_make}")

    if lens_model:
        cmd.append(f"-EXIF:LensModel={lens_model}")
        cmd.append(f"-XMP-exifEX:LensModel={lens_model}")

    if gps_latitude is not None:
        if gps_latitude < -90 or gps_latitude > 90:
            raise RuntimeError("GPS latitude must be between -90 and 90.")

        cmd.append(f"-EXIF:GPSLatitude={abs(gps_latitude)}")
        cmd.append(f"-EXIF:GPSLatitudeRef={_gps_ref_lat(gps_latitude)}")
        cmd.append(f"-XMP-exif:GPSLatitude={abs(gps_latitude)}")
        cmd.append(f"-XMP-exif:GPSLatitudeRef={_gps_ref_lat(gps_latitude)}")

    if gps_longitude is not None:
        if gps_longitude < -180 or gps_longitude > 180:
            raise RuntimeError("GPS longitude must be between -180 and 180.")

        cmd.append(f"-EXIF:GPSLongitude={abs(gps_longitude)}")
        cmd.append(f"-EXIF:GPSLongitudeRef={_gps_ref_lon(gps_longitude)}")
        cmd.append(f"-XMP-exif:GPSLongitude={abs(gps_longitude)}")
        cmd.append(f"-XMP-exif:GPSLongitudeRef={_gps_ref_lon(gps_longitude)}")

    if gps_altitude is not None:
        cmd.append(f"-EXIF:GPSAltitude={abs(gps_altitude)}")
        cmd.append(f"-EXIF:GPSAltitudeRef={1 if gps_altitude < 0 else 0}")
        cmd.append(f"-XMP-exif:GPSAltitude={abs(gps_altitude)}")
        cmd.append(f"-XMP-exif:GPSAltitudeRef={1 if gps_altitude < 0 else 0}")

    if date_taken:
        cmd.append(f"-EXIF:DateTimeOriginal={date_taken}")
        cmd.append(f"-EXIF:CreateDate={date_taken}")
        cmd.append(f"-EXIF:ModifyDate={date_taken}")
        cmd.append(f"-XMP-xmp:CreateDate={date_taken}")
        cmd.append(f"-XMP-xmp:ModifyDate={date_taken}")
        cmd.append(f"-XMP-photoshop:DateCreated={date_taken}")

    if len(cmd) <= 2:
        raise RuntimeError("No metadata fields were provided.")

    backup_path = backups_dir() / f"{file_path.stem}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}{file_path.suffix}"
    shutil.copy2(file_path, backup_path)
    cmd.extend(["--", str(file_path)])

    try:
        result = run_exiftool(cmd)
    except Exception:
        shutil.copy2(backup_path, file_path)
        raise

    if result.returncode != 0:
        shutil.copy2(backup_path, file_path)
        error_text = result.stderr.strip() or "Unknown ExifTool metadata writing error."
        raise RuntimeError(error_text)

    original_hash_after = sha256_file(file_path)
    after_raw = safe_run_exiftool(file_path)

    report = build_write_original_report(
        file_path=file_path,
        fields=fields,
        original_hash_before=original_hash_before,
        original_hash_after=original_hash_after,
        after_count=len(after_raw.keys()),
        exiftool_stdout=result.stdout.strip(),
        exiftool_stderr=result.stderr.strip(),
    )

    report_path = file_path.with_name(f"{file_path.stem}_write_metadata_report.txt")
    report_path.write_text(report, encoding="utf-8")

    return {
        "file_path": str(file_path),
        "report_path": str(report_path),
        "after_tag_count": len(after_raw.keys()),
        "original_hash_before": original_hash_before,
        "original_hash_after": original_hash_after,
        "file_changed": original_hash_before != original_hash_after,
        "backup_path": str(backup_path),
    }


def build_write_original_report(
    file_path: Path,
    fields: Dict[str, Any],
    original_hash_before: str,
    original_hash_after: str,
    after_count: int,
    exiftool_stdout: str,
    exiftool_stderr: str,
) -> str:
    lines = []

    lines.append("KAI METADATA INSPECTOR — WRITE METADATA TO ORIGINAL REPORT")
    lines.append("=========================================================")
    lines.append("")
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"Modified file: {file_path}")
    lines.append("")
    lines.append("WARNING")
    lines.append("-------")
    lines.append("This operation wrote metadata directly into the original file.")
    lines.append("ExifTool was run with -m -overwrite_original.")
    lines.append("")
    lines.append("HASH CHECK")
    lines.append("----------")
    lines.append(f"SHA256 before writing: {original_hash_before}")
    lines.append(f"SHA256 after writing:  {original_hash_after}")

    if original_hash_before != original_hash_after:
        lines.append("File status: CHANGED")
    else:
        lines.append("File status: HASH UNCHANGED")

    lines.append("")
    lines.append("Metadata requested")
    lines.append("------------------")
    lines.append(f"Title: {fields.get('title', '')}")
    lines.append(f"Description: {fields.get('description', '')}")
    lines.append(f"Creator: {fields.get('creator', '')}")
    lines.append(f"Rights: {fields.get('rights', '')}")
    lines.append(f"Keywords: {', '.join(fields.get('keywords', []) or [])}")
    lines.append(f"Camera make: {fields.get('camera_make', '')}")
    lines.append(f"Camera / phone model: {fields.get('camera_model', '')}")
    lines.append(f"Lens make: {fields.get('lens_make', '')}")
    lines.append(f"Lens model: {fields.get('lens_model', '')}")
    lines.append(f"GPS latitude: {fields.get('gps_latitude', '')}")
    lines.append(f"GPS longitude: {fields.get('gps_longitude', '')}")
    lines.append(f"GPS altitude: {fields.get('gps_altitude', '')}")
    lines.append(f"Date/time taken: {fields.get('date_taken', '')}")
    lines.append("")
    lines.append("Summary")
    lines.append("-------")
    lines.append(f"Metadata tags after writing: {after_count}")
    lines.append("")
    lines.append("ExifTool Output")
    lines.append("---------------")
    lines.append(exiftool_stdout or "No stdout.")
    lines.append("")
    lines.append("ExifTool Errors")
    lines.append("---------------")
    lines.append(exiftool_stderr or "No stderr.")
    lines.append("")
    lines.append("End of report.")

    return "\n".join(lines)
