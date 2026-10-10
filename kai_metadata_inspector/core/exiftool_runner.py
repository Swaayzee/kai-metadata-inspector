from __future__ import annotations

import json
from pathlib import Path

from kai_metadata_inspector.core.runtime import run_exiftool, runtime_diagnostics


def safe_run_exiftool(file_path: Path) -> dict:
    """Read one file as grouped JSON without invoking a shell."""
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"Selected file does not exist: {path}")
    result = run_exiftool([
        "-json", "-G", "-a", "-s", "-n", "-charset", "filename=UTF8", "--", str(path)
    ])
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "ExifTool could not inspect this file.")
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("ExifTool returned invalid JSON.") from exc
    if not payload or not isinstance(payload[0], dict):
        raise RuntimeError("ExifTool returned no metadata.")
    return payload[0]


def get_exiftool_version() -> str:
    return runtime_diagnostics()["exiftool_version"]
