from pathlib import Path
from datetime import datetime

from kai_metadata_inspector.config import APP_VERSION, SUPPORTED_EXTENSIONS
from kai_metadata_inspector.core.exiftool_runner import safe_run_exiftool
from kai_metadata_inspector.core.analyzer import build_analysis


def find_supported_files(folder_path: Path) -> list[Path]:
    """
    Folder scan.

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


def build_folder_summary(
    folder_path: Path,
    files: list[Path],
    exiftool_version: str,
) -> tuple[dict, str]:
    """
    Scans metadata for each supported file in the selected folder.

    Security/scope:
    - read-only
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

    for file_path in files:
        try:
            raw = safe_run_exiftool(file_path)
            analysis = build_analysis(file_path, raw, exiftool_version)
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
            else:
                device_name = "Not found"

            summary["file_rows"].append({
                "file": file_path.name,
                "risk": risk_level,
                "risk_points": flags["risk_points"],
                "gps": "Yes" if flags["gps_found"] else "No",
                "timestamp": "Yes" if flags["time_found"] else "No",
                "timezone": "Yes" if flags["timezone_found"] else "No",
                "device": device_name,
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
