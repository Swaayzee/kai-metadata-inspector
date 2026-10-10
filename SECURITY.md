# Security policy

Kai Metadata Inspector processes files and metadata as untrusted input. It is local-only by design: no telemetry, analytics, uploads, reverse geocoding, or automatic URL opening.

## File behavior

- Inspection, folder scanning, preview, and export do not change source files.
- Cleaning operates on a new copy and verifies the original SHA-256 before and after.
- Metadata editing intentionally modifies the selected file, but creates a recovery backup first and restores it if ExifTool fails.
- Exported reports may contain file paths, GPS, serial numbers, ownership data, or other private information.

## Process safety

ExifTool is invoked with an argument array, a timeout, and no shell. Metadata is rendered as plain text and is never executed. The bundled ExifTool version is fixed in the build workflow.

## Reporting a vulnerability

Please use GitHub's private security advisory feature. Do not attach private images or unredacted metadata reports to a public issue.
