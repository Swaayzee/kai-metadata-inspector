# Kai Metadata Inspector 2.0

Kai 2.0 is a safety-focused rebuild of the offline image-metadata workflow.

## Highlights

- One ExifTool-backed inspection path for files and folders
- Searchable metadata table with explainable privacy-risk labels
- Responsive folder scans with progress and cancellation
- Verified clean-copy workflow with a before/after tag comparison
- Recovery backups before metadata editing
- Reproducible Windows x64, macOS Intel/Apple Silicon, and Linux x86_64 AppImage builds
- Pinned dependencies, automated tests, diagnostics, and packaged smoke checks

## Distribution notes

Preview artifacts are unsigned. Windows and macOS may show reputation or Gatekeeper warnings. The Linux AppImage is portable and can use `APPIMAGE_EXTRACT_AND_RUN=1` when FUSE is unavailable.

## Safety notes

Inspection is read-only. Cleaning writes to a new destination and verifies that the original SHA-256 hash did not change. Editing is the only operation that changes the selected file, and it creates a recovery copy first. Reinspect cleaned files before publishing because no metadata tool can guarantee removal of every proprietary field in every format.
