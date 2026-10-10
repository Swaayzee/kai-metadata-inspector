# Testing guide

## Automated

```bash
python -m pip install -r requirements-dev.txt
python -m ruff check .
QT_QPA_PLATFORM=offscreen python -m pytest -q
python app.py --diagnostics
python -m PyInstaller --clean --noconfirm packaging/kai_metadata_inspector.spec
APPIMAGETOOL=/path/to/appimagetool packaging/linux/build_appimage.sh
```

Run every frozen executable with `--diagnostics` after packaging. On Linux, use
`APPIMAGE_EXTRACT_AND_RUN=1` in environments where FUSE is unavailable.

## Manual native matrix

On Windows x64, macOS Intel, macOS Apple Silicon, and the Linux x86_64 AppImage verify:

- launch and diagnostics
- JPG, PNG, WebP, HEIC/HEIF, TIFF, and one RAW file
- a GPS sample with N/E and another with S/W coordinates
- text and JSON export
- background folder progress, cancellation, restart, and CSV export
- clean-copy output, original hash preservation, and before/after comparison
- edit, recovery-backup creation, and reinspection
- drag and drop, resizing, metadata filtering, and output-folder opening
- Unicode and long paths
- malformed and read-only files fail without data loss
