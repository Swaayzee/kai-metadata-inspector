from __future__ import annotations

import os
import platform
from pathlib import Path

APP_NAME = "Kai Metadata Inspector"
APP_VERSION = "2.0.0"
APP_ID = "com.kai.metadata-inspector"
MAX_FILE_SIZE_MB_WARNING = 250
MAX_PREVIEW_FILE_SIZE_MB = 80
MAX_FOLDER_FILES_WARNING = 500
EXIFTOOL_TIMEOUT_SECONDS = 45


def user_data_dir() -> Path:
    """Return a writable, platform-native application data directory."""
    override = os.environ.get("KAI_METADATA_HOME")
    if override:
        return Path(override).expanduser().resolve()
    system = platform.system()
    if system == "Windows":
        root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        return root / "Kai Metadata Inspector"
    if system == "Darwin":
        return Path.home() / "Library" / "Application Support" / "Kai Metadata Inspector"
    root = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return root / "kai-metadata-inspector"


def outputs_dir() -> Path:
    path = user_data_dir() / "outputs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def backups_dir() -> Path:
    path = user_data_dir() / "backups"
    path.mkdir(parents=True, exist_ok=True)
    return path


SUPPORTED_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif",
    ".tif", ".tiff", ".bmp", ".gif", ".avif", ".dng",
    ".cr2", ".cr3", ".nef", ".arw", ".rw2", ".orf",
    ".raf", ".pef", ".srw", ".psd", ".xmp",
}

PREVIEW_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".heic", ".heif", ".tif", ".tiff",
}
