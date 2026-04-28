from pathlib import Path


APP_NAME = "Kai Metadata Inspector"
APP_VERSION = "v1.0 Clean Copy Alpha"

REPORTS_DIR = Path("reports")

MAX_FILE_SIZE_MB_WARNING = 250
MAX_PREVIEW_FILE_SIZE_MB = 50
MAX_FOLDER_FILES_WARNING = 300
MAX_FOLDER_SUMMARY_WARNING = 100
EXIFTOOL_TIMEOUT_SECONDS = 30


SUPPORTED_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif",
    ".tif", ".tiff", ".bmp", ".gif", ".avif", ".dng",
    ".cr2", ".cr3", ".nef", ".arw", ".rw2", ".orf",
    ".raf", ".pef", ".srw", ".psd", ".xmp"
}


PREVIEW_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"
}
