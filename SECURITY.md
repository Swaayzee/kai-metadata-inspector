Copyright (c) 2026 Patryk Klimczyk

# Security Policy

Kai Metadata Inspector handles files that may be private, sensitive, malformed, or maliciously crafted.

The app is designed to work locally and offline-first, but users should still treat all image files and metadata as untrusted input.

---

## Security principles

Kai Metadata Inspector is designed to be:

- Offline-first
- Local-only
- No telemetry
- No analytics
- No automatic upload
- No automatic internet access
- No automatic URL opening from metadata

---

## Important security model note

Kai Metadata Inspector supports two different workflows:

### Inspection / export / folder analysis

These workflows are intended to be non-destructive.

### Metadata editing

The app also includes a metadata editing feature that can write metadata directly to the selected original file.

This means the application is not strictly read-only anymore.

Users should understand:

- Inspecting does not modify files
- Creating a cleaned copy creates a new output file
- Editing metadata may modify the selected original file

If you want a safer workflow, use copies of your images first.

---

## Metadata safety

Metadata is treated as untrusted text.

The application should never:

- Execute metadata
- Interpret metadata as code
- Automatically open URLs found in metadata
- Upload files automatically
- Use `shell=True` when invoking ExifTool

---

## ExifTool execution

ExifTool should be executed using a safe subprocess argument list.

Recommended pattern:

```python
subprocess.run(
    ["exiftool", "-json", "-G", "-a", "-s", "-c", "%.8f", str(file_path)],
    capture_output=True,
    text=True,
    timeout=30,
    check=False,
)
