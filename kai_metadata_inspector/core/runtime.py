from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Sequence

from kai_metadata_inspector.config import EXIFTOOL_TIMEOUT_SECONDS


def bundle_root() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).resolve().parents[2]


def find_exiftool() -> Path:
    """Find bundled ExifTool first, then a system installation."""
    candidates: list[Path] = []
    if override := os.environ.get("KAI_EXIFTOOL"):
        candidates.append(Path(override).expanduser())
    root = bundle_root()
    candidates.extend([
        root / "vendor" / "exiftool" / "exiftool.exe",
        root / "vendor" / "exiftool" / "exiftool",
        root / "exiftool" / "exiftool.exe",
        root / "exiftool" / "exiftool",
        root / "exiftool.exe",
        root / "exiftool",
    ])
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    found = shutil.which("exiftool") or shutil.which("exiftool.exe")
    if found:
        return Path(found).resolve()
    raise RuntimeError(
        "ExifTool was not found. Reinstall Kai Metadata Inspector or install ExifTool and restart the app."
    )


def exiftool_command(arguments: Sequence[str]) -> list[str]:
    executable = find_exiftool()
    if executable.suffix.lower() != ".exe" and not os.access(executable, os.X_OK):
        perl = shutil.which("perl")
        if not perl:
            raise RuntimeError("The bundled ExifTool requires Perl, but Perl was not found.")
        return [perl, str(executable), *arguments]
    return [str(executable), *arguments]


def use_argument_file() -> bool:
    """Whether arguments are sent to ExifTool on stdin instead of the command line.

    Windows passes command-line arguments in the ANSI code page, which corrupts
    non-ASCII metadata values and file paths. ExifTool reads an argument file
    as UTF-8, so on Windows arguments always go through "-@ -".
    ``KAI_EXIFTOOL_ARGFILE=1`` forces this elsewhere so it can be tested.
    """
    override = os.environ.get("KAI_EXIFTOOL_ARGFILE")
    if override is not None:
        return override == "1"
    return os.name == "nt"


def build_argument_file(arguments: Sequence[str]) -> str | None:
    """Arguments as ExifTool argument-file text, or None if not representable.

    One argument per line. Paths (everything after "--") are made absolute:
    an argument file ignores lines starting with "#" and strips leading
    spaces, which an absolute path can never trigger.
    """
    if any("\n" in argument or "\r" in argument for argument in arguments):
        return None
    lines = ["-charset", "filename=UTF8"]
    paths = False
    for argument in arguments:
        if paths:
            argument = os.path.abspath(argument)
        elif argument == "--":
            paths = True
        lines.append(argument)
    return "\n".join(lines) + "\n"


def run_exiftool(arguments: Sequence[str], *, timeout: int = EXIFTOOL_TIMEOUT_SECONDS) -> subprocess.CompletedProcess[str]:
    argument_file = build_argument_file(arguments) if use_argument_file() else None
    command = exiftool_command(["-@", "-"] if argument_file is not None else arguments)
    try:
        return subprocess.run(
            command, input=argument_file, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout, check=False,
            stdin=None if argument_file is not None else subprocess.DEVNULL,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"ExifTool timed out after {timeout} seconds.") from exc


def runtime_diagnostics() -> dict[str, str]:
    try:
        path = find_exiftool()
        result = run_exiftool(["-ver"], timeout=10)
        version = result.stdout.strip() if result.returncode == 0 else "unavailable"
        return {"exiftool_path": str(path), "exiftool_version": version, "status": "ok"}
    except Exception as exc:
        return {"exiftool_path": "not found", "exiftool_version": "unavailable", "status": str(exc)}
