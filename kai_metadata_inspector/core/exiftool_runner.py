from __future__ import annotations

import json
import os
from pathlib import Path

from kai_metadata_inspector.config import EXIFTOOL_TIMEOUT_SECONDS
from kai_metadata_inspector.core.runtime import run_exiftool, runtime_diagnostics

READ_ARGUMENTS = ["-json", "-G", "-a", "-s", "-n", "-charset", "filename=UTF8"]


def _parse_json(stdout: str) -> list[dict]:
    try:
        payload = json.loads(stdout) if stdout.strip() else []
    except json.JSONDecodeError as exc:
        raise RuntimeError("ExifTool returned invalid JSON.") from exc
    return [entry for entry in payload if isinstance(entry, dict)]


def safe_run_exiftool(file_path: Path) -> dict:
    """Read one file as grouped JSON without invoking a shell."""
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"Selected file does not exist: {path}")
    result = run_exiftool([*READ_ARGUMENTS, "--", str(path)])
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "ExifTool could not inspect this file.")
    payload = _parse_json(result.stdout)
    if not payload:
        raise RuntimeError("ExifTool returned no metadata.")
    return payload[0]


def source_key(name: str, *, windows: bool | None = None) -> str:
    """Comparable form of a path as given to, or reported by, ExifTool.

    On Windows ExifTool reports ``SourceFile`` with forward slashes whatever
    was passed in, and paths are case-insensitive.
    """
    if os.name == "nt" if windows is None else windows:
        return name.replace("\\", "/").casefold()
    return name


def read_metadata_batch(file_paths: list[Path]) -> dict[Path, dict | str]:
    """Read several files with a single ExifTool process.

    Starting ExifTool is far more expensive than reading one more file, so
    folder scans use this instead of one process per file. Every input path
    is present in the result: its tags on success, or an error message.
    """
    paths = [Path(path) for path in file_paths]
    if not paths:
        return {}
    absolute = {path: os.path.abspath(path) for path in paths}
    timeout = EXIFTOOL_TIMEOUT_SECONDS + 2 * len(paths)
    try:
        result = run_exiftool([*READ_ARGUMENTS, "--", *absolute.values()], timeout=timeout)
        entries = {source_key(str(entry.get("SourceFile"))): entry for entry in _parse_json(result.stdout)}
    except RuntimeError as exc:
        return {path: str(exc) for path in paths}

    found: dict[Path, dict | str] = {}
    for path, name in absolute.items():
        entry = entries.get(source_key(name))
        if entry is None:
            found[path] = "ExifTool could not read this file."
        elif entry.get("ExifTool:Error"):
            found[path] = str(entry["ExifTool:Error"])
        else:
            found[path] = entry
    return found


def get_exiftool_version() -> str:
    return runtime_diagnostics()["exiftool_version"]
