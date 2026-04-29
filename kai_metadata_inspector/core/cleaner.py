import hashlib
import shutil
import subprocess
from pathlib import Path
from datetime import datetime

from kai_metadata_inspector.config import EXIFTOOL_TIMEOUT_SECONDS
from kai_metadata_inspector.core.exiftool_runner import safe_run_exiftool


def sha256_file(file_path: Path) -> str:
    """
    Creates SHA256 hash of a file.

    Used to prove:
    - original file stayed unchanged
    - cleaned copy is a separate file
    """

    hasher = hashlib.sha256()

    with file_path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            hasher.update(chunk)

    return hasher.hexdigest()


def clean_metadata_copy(source_path: Path, output_path: Path) -> dict:
    """
    Creates a cleaned copy of a file.

    Safety rules:
    - Original file is never modified.
    - Output file must not already exist.
    - Output path cannot be the same as source path.
    - ExifTool is run only against the output copy.
    - No shell=True.
    - No internet access.
    """

    if not source_path.exists():
        raise FileNotFoundError("Source file does not exist.")

    if not source_path.is_file():
        raise RuntimeError("Source path is not a file.")

    if output_path.exists():
        raise RuntimeError("Output file already exists. Choose a different name.")

    if source_path.resolve() == output_path.resolve():
        raise RuntimeError("Output path cannot be the same as the original file.")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    original_hash_before = sha256_file(source_path)

    # Copy bytes only. Do not preserve original filesystem timestamps.
    shutil.copyfile(source_path, output_path)

    cmd = [
        "exiftool",
        "-all=",
        "-overwrite_original",
        str(output_path),
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
        try:
            output_path.unlink(missing_ok=True)
        except Exception:
            pass

        raise RuntimeError(
            f"ExifTool cleaning timed out after {EXIFTOOL_TIMEOUT_SECONDS} seconds."
        )

    if result.returncode != 0:
        try:
            output_path.unlink(missing_ok=True)
        except Exception:
            pass

        error_text = result.stderr.strip() or "Unknown ExifTool cleaning error."
        raise RuntimeError(error_text)

    original_hash_after = sha256_file(source_path)
    cleaned_hash = sha256_file(output_path)

    if original_hash_before != original_hash_after:
        raise RuntimeError(
            "Safety check failed: original file hash changed. "
            "This should never happen. Stop using this cleaned output and review manually."
        )

    before_raw = safe_run_exiftool(source_path)
    after_raw = safe_run_exiftool(output_path)

    before_keys = set(before_raw.keys())
    after_keys = set(after_raw.keys())

    removed_keys = sorted(before_keys - after_keys)
    remaining_keys = sorted(after_keys)

    report = build_cleaning_report(
        source_path=source_path,
        output_path=output_path,
        original_hash_before=original_hash_before,
        original_hash_after=original_hash_after,
        cleaned_hash=cleaned_hash,
        before_count=len(before_keys),
        after_count=len(after_keys),
        removed_keys=removed_keys,
        remaining_keys=remaining_keys,
        exiftool_stdout=result.stdout.strip(),
        exiftool_stderr=result.stderr.strip(),
    )

    report_path = output_path.with_name(f"{output_path.stem}_cleaning_report.txt")
    report_path.write_text(report, encoding="utf-8")

    return {
        "source_path": str(source_path),
        "output_path": str(output_path),
        "report_path": str(report_path),
        "before_tag_count": len(before_keys),
        "after_tag_count": len(after_keys),
        "removed_tag_count": len(removed_keys),
        "original_hash_before": original_hash_before,
        "original_hash_after": original_hash_after,
        "cleaned_hash": cleaned_hash,
        "original_unchanged": original_hash_before == original_hash_after,
    }


def build_cleaning_report(
    source_path: Path,
    output_path: Path,
    original_hash_before: str,
    original_hash_after: str,
    cleaned_hash: str,
    before_count: int,
    after_count: int,
    removed_keys: list[str],
    remaining_keys: list[str],
    exiftool_stdout: str,
    exiftool_stderr: str,
) -> str:
    lines = []

    lines.append("KAI METADATA INSPECTOR — CLEANING REPORT")
    lines.append("========================================")
    lines.append("")
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"Original file: {source_path}")
    lines.append(f"Cleaned copy: {output_path}")
    lines.append("")
    lines.append("SAFETY NOTE")
    lines.append("-----------")
    lines.append("The original file was not modified.")
    lines.append("ExifTool was run only against the cleaned copy.")
    lines.append("A SHA256 check was used to confirm the original file hash did not change.")
    lines.append("")
    lines.append("HASH CHECK")
    lines.append("----------")
    lines.append(f"Original SHA256 before cleaning: {original_hash_before}")
    lines.append(f"Original SHA256 after cleaning:  {original_hash_after}")
    lines.append(f"Cleaned copy SHA256:             {cleaned_hash}")

    if original_hash_before == original_hash_after:
        lines.append("Original file status: UNCHANGED")
    else:
        lines.append("Original file status: WARNING — HASH CHANGED")

    lines.append("")
    lines.append("IMPORTANT LIMITATION")
    lines.append("--------------------")
    lines.append(
        "No metadata cleaner can guarantee that every possible hidden or proprietary "
        "data field has been removed from every file format. Re-scan the cleaned copy "
        "and review the remaining metadata before sharing."
    )
    lines.append("")
    lines.append("Summary")
    lines.append("-------")
    lines.append(f"Metadata tags before cleaning: {before_count}")
    lines.append(f"Metadata tags after cleaning: {after_count}")
    lines.append(f"Removed tag count: {len(removed_keys)}")
    lines.append("")
    lines.append("Removed Tags")
    lines.append("------------")

    if removed_keys:
        for key in removed_keys:
            lines.append(key)
    else:
        lines.append("No removable metadata tags were detected as removed.")

    lines.append("")
    lines.append("Remaining Tags After Cleaning")
    lines.append("-----------------------------")

    if remaining_keys:
        for key in remaining_keys:
            lines.append(key)
    else:
        lines.append("No metadata tags were returned by ExifTool.")

    lines.append("")
    lines.append("ExifTool Output")
    lines.append("---------------")
    lines.append(exiftool_stdout or "No stdout.")
    lines.append("")
    lines.append("ExifTool Errors")
    lines.append("---------------")
    lines.append(exiftool_stderr or "No stderr.")
    lines.append("")
    lines.append("End of cleaning report.")

    return "\n".join(lines)