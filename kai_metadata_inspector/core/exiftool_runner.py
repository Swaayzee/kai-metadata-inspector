import json
import shutil
import subprocess
from pathlib import Path

from kai_metadata_inspector.config import EXIFTOOL_TIMEOUT_SECONDS


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
