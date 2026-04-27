from pathlib import Path
from datetime import datetime

from kai_metadata_inspector.config import APP_VERSION
from kai_metadata_inspector.core.analyzer import format_section, clean_text


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
