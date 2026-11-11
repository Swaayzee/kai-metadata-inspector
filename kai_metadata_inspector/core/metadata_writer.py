"""Validated in-place metadata editing with a recovery backup."""

from __future__ import annotations

import hashlib
import math
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from kai_metadata_inspector.config import backups_dir
from kai_metadata_inspector.core.analyzer import signed_coordinate
from kai_metadata_inspector.core.exiftool_runner import safe_run_exiftool
from kai_metadata_inspector.core.runtime import run_exiftool

# Editor field -> ExifTool tags that store it.
TEXT_TAGS = {
    "title": ["XMP-dc:Title"],
    "description": ["XMP-dc:Description", "EXIF:ImageDescription"],
    "creator": ["XMP-dc:Creator", "EXIF:Artist"],
    "rights": ["XMP-dc:Rights", "EXIF:Copyright"],
    "camera_make": ["EXIF:Make", "XMP-tiff:Make"],
    "camera_model": ["EXIF:Model", "XMP-tiff:Model"],
    "lens_make": ["EXIF:LensMake", "XMP-exifEX:LensMake"],
    "lens_model": ["EXIF:LensModel", "XMP-exifEX:LensModel"],
}

DATE_TAGS = [
    "EXIF:DateTimeOriginal",
    "EXIF:CreateDate",
    "EXIF:ModifyDate",
    "XMP-xmp:CreateDate",
    "XMP-xmp:ModifyDate",
    "XMP-photoshop:DateCreated",
]

NUMERIC_FIELDS = {"gps_latitude", "gps_longitude", "gps_altitude"}
EDITABLE_FIELDS = [*TEXT_TAGS, "keywords", "gps_latitude", "gps_longitude", "gps_altitude", "date_taken"]


def sha256_file(file_path: Path) -> str:
    hasher = hashlib.sha256()

    with file_path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            hasher.update(chunk)

    return hasher.hexdigest()


def _clean_text(value: Any) -> str:
    return str(value if value is not None else "").strip()


def _parse_decimal(value: Any, label: str) -> float | None:
    text = _clean_text(value)

    if not text:
        return None

    try:
        number = float(text)
    except ValueError:
        raise RuntimeError(f"{label} must be a decimal number, not: {text}") from None

    # float() accepts "nan" and "inf", which ExifTool rejects only after the
    # hemisphere reference has already been rewritten.
    if not math.isfinite(number):
        raise RuntimeError(f"{label} must be a finite number.")

    return number


def _validate_exif_datetime(value: Any) -> str:
    text = _clean_text(value)

    if not text:
        return ""

    try:
        datetime.strptime(text, "%Y:%m:%d %H:%M:%S")
    except ValueError:
        raise RuntimeError("Invalid date/time. Use a real date in the form YYYY:MM:DD HH:MM:SS") from None

    return text


def split_keywords(value: Any) -> list[str]:
    items = value.split(",") if isinstance(value, str) else (value or [])
    return [str(item).strip() for item in items if str(item).strip()]


def _text(value: Any) -> str:
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    return "" if value is None else str(value)


def _first(raw: dict, keys: list[str]) -> str:
    for key in keys:
        if raw.get(key) not in (None, ""):
            return _text(raw[key]).strip()
    return ""


def _trim_number(number: float) -> str:
    return f"{number:.8f}".rstrip("0").rstrip(".")


def current_field_values(raw: dict) -> dict[str, str]:
    """Values of the editable fields as stored in the file (``-n`` output)."""

    def coordinate(axis: str) -> str:
        value = signed_coordinate(raw, axis)
        return "" if value == "Not found" else value

    altitude = ""
    try:
        if raw.get("Composite:GPSAltitude") not in (None, ""):
            altitude = _trim_number(float(raw["Composite:GPSAltitude"]))
        elif raw.get("EXIF:GPSAltitude") not in (None, ""):
            below = str(raw.get("EXIF:GPSAltitudeRef", "0")).strip() == "1"
            altitude = _trim_number(abs(float(raw["EXIF:GPSAltitude"])) * (-1 if below else 1))
    except (TypeError, ValueError):
        altitude = ""

    # Sub-seconds and time zones are stored in separate tags; the editor
    # works with the plain EXIF form only.
    date = re.match(
        r"\d{4}:\d{2}:\d{2} \d{2}:\d{2}:\d{2}",
        _first(raw, ["EXIF:DateTimeOriginal", "EXIF:CreateDate", "XMP:DateCreated"]),
    )

    return {
        "title": _first(raw, ["XMP:Title"]),
        "description": _first(raw, ["XMP:Description", "EXIF:ImageDescription"]),
        "creator": _first(raw, ["XMP:Creator", "EXIF:Artist"]),
        "rights": _first(raw, ["XMP:Rights", "EXIF:Copyright"]),
        "keywords": _first(raw, ["XMP:Subject"]),
        "camera_make": _first(raw, ["EXIF:Make", "XMP:Make"]),
        "camera_model": _first(raw, ["EXIF:Model", "XMP:Model"]),
        "lens_make": _first(raw, ["EXIF:LensMake", "XMP:LensMake"]),
        "lens_model": _first(raw, ["EXIF:LensModel", "XMP:LensModel"]),
        "gps_latitude": coordinate("lat"),
        "gps_longitude": coordinate("lon"),
        "gps_altitude": altitude,
        "date_taken": date.group(0) if date else "",
    }


def field_matches(field: str, wanted: Any, actual: Any) -> bool:
    """True when two editor values mean the same thing for ``field``."""
    if field == "keywords":
        return split_keywords(wanted) == split_keywords(actual)

    wanted_text, actual_text = _clean_text(wanted), _clean_text(actual)

    if field in NUMERIC_FIELDS and wanted_text and actual_text:
        try:
            return abs(float(wanted_text) - float(actual_text)) < 1e-5
        except ValueError:
            return False

    return wanted_text == actual_text


def changed_fields(original: dict[str, Any], edited: dict[str, Any]) -> dict[str, Any]:
    """Only the fields whose value differs from what the file contains."""
    return {
        field: value for field, value in edited.items()
        if not field_matches(field, value, original.get(field, ""))
    }


def build_write_arguments(fields: dict[str, Any]) -> list[str]:
    """Translate editor fields into ExifTool arguments.

    Only keys present in ``fields`` are touched; an empty value removes the
    field. Raises RuntimeError for invalid values before anything is written.
    """
    unknown = sorted(set(fields) - set(EDITABLE_FIELDS))
    if unknown:
        raise RuntimeError(f"Unknown metadata field(s): {', '.join(unknown)}")

    arguments: list[str] = []

    for field, tags in TEXT_TAGS.items():
        if field in fields:
            value = _clean_text(fields[field])
            arguments.extend(f"-{tag}={value}" for tag in tags)

    if "keywords" in fields:
        keywords = split_keywords(fields["keywords"])
        if keywords:
            # Repeating "=" replaces the whole list instead of appending to it.
            arguments.extend(f"-XMP-dc:Subject={keyword}" for keyword in keywords)
        else:
            arguments.append("-XMP-dc:Subject=")

    for field, axis, limit, negative_ref, positive_ref in (
        ("gps_latitude", "Latitude", 90, "S", "N"),
        ("gps_longitude", "Longitude", 180, "W", "E"),
    ):
        if field not in fields:
            continue

        number = _parse_decimal(fields[field], f"GPS {axis.lower()}")

        if number is None:
            arguments += [f"-EXIF:GPS{axis}=", f"-EXIF:GPS{axis}Ref=", f"-XMP-exif:GPS{axis}="]
            continue

        if abs(number) > limit:
            raise RuntimeError(f"GPS {axis.lower()} must be between -{limit} and {limit}.")

        arguments += [
            f"-EXIF:GPS{axis}={abs(number)}",
            f"-EXIF:GPS{axis}Ref={negative_ref if number < 0 else positive_ref}",
            # XMP has no separate reference tag: the sign carries the hemisphere.
            f"-XMP-exif:GPS{axis}={number}",
        ]

    if "gps_altitude" in fields:
        altitude = _parse_decimal(fields["gps_altitude"], "GPS altitude")

        if altitude is None:
            arguments += [
                "-EXIF:GPSAltitude=", "-EXIF:GPSAltitudeRef=",
                "-XMP-exif:GPSAltitude=", "-XMP-exif:GPSAltitudeRef=",
            ]
        else:
            ref = 1 if altitude < 0 else 0
            arguments += [
                f"-EXIF:GPSAltitude={abs(altitude)}", f"-EXIF:GPSAltitudeRef#={ref}",
                f"-XMP-exif:GPSAltitude={abs(altitude)}", f"-XMP-exif:GPSAltitudeRef#={ref}",
            ]

    if "date_taken" in fields:
        date_taken = _validate_exif_datetime(fields["date_taken"])
        if date_taken:
            arguments.extend(f"-{tag}={date_taken}" for tag in DATE_TAGS)
        else:
            # Clearing the capture date leaves the modification date alone.
            arguments.extend(f"-{tag}=" for tag in DATE_TAGS if "ModifyDate" not in tag)

    return arguments


def write_metadata_to_original(file_path: Path, fields: dict[str, Any]) -> dict:
    """
    Writes the given fields directly into the selected file.

    - Only keys present in ``fields`` are written; an empty value removes
      that field. Pass only what the user changed.
    - Values are validated before the file is touched.
    - A recovery copy is stored in the backups folder first and is restored
      automatically if ExifTool fails or the result cannot be read back.
    """

    if not file_path.exists():
        raise FileNotFoundError("File does not exist.")

    if not file_path.is_file():
        raise RuntimeError("Selected path is not a file.")

    arguments = build_write_arguments(fields)

    if not arguments:
        raise RuntimeError("No metadata changes were provided.")

    original_hash_before = sha256_file(file_path)

    backup_path = backups_dir() / f"{file_path.stem}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}{file_path.suffix}"
    shutil.copy2(file_path, backup_path)

    try:
        # -m ignores minor warnings such as maker-note warnings.
        result = run_exiftool(["-m", "-overwrite_original", *arguments, "--", str(file_path)])

        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "Unknown ExifTool metadata writing error.")

        after_raw = safe_run_exiftool(file_path)
    except Exception:
        if not file_path.exists() or sha256_file(file_path) != original_hash_before:
            shutil.copy2(backup_path, file_path)
        raise

    after_values = current_field_values(after_raw)
    original_hash_after = sha256_file(file_path)

    return {
        "file_path": str(file_path),
        "after_tag_count": len(after_raw.keys()),
        "original_hash_before": original_hash_before,
        "original_hash_after": original_hash_after,
        "file_changed": original_hash_before != original_hash_after,
        "backup_path": str(backup_path),
        "changed_fields": sorted(fields),
        # Fields that did not read back as requested (unsupported by this file type).
        "unverified_fields": sorted(
            field for field, value in fields.items()
            if not field_matches(field, value, after_values.get(field, ""))
        ),
    }
