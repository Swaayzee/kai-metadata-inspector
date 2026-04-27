# Security Policy

Kai Metadata Inspector handles files that may be private, sensitive or maliciously crafted.

## Security principles

The app is designed to be:

- Offline-first
- Read-only by default
- No automatic upload
- No telemetry
- No analytics
- No automatic map opening
- No original-file modification

## Metadata safety

Metadata is treated as untrusted text.

The app should never:

- Execute metadata
- Parse metadata as code
- Automatically open URLs from metadata
- Upload image files
- Modify original files
- Use `shell=True` when calling ExifTool

## ExifTool execution

ExifTool is called safely using a subprocess argument list.

Safe pattern:

```python
subprocess.run(
    ["exiftool", "-json", "-G", "-a", "-s", "-c", "%.8f", str(file_path)],
    capture_output=True,
    text=True,
    timeout=30,
    check=False,
)
