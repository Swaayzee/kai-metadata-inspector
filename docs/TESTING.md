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

All test images are generated at run time; never commit real photos. Tests that need
ExifTool are skipped when it is not available.

| File | Covers |
|---|---|
| `tests/test_reading.py` | Real-file analysis, batch reads, folder summary, editor pre-fill |
| `tests/test_cleaner.py` | Metadata really removed per format, pixels identical, orientation/ICC kept, TIFF, failures leave nothing behind |
| `tests/test_writer.py` | Validation, write-then-reopen per format, only-changed-fields, removal, backup and restore |
| `tests/test_preview.py` | Preview decoding, HEIC, orientation, large and broken images |
| `tests/test_workflows.py` | Headless GUI workflows: open, filter, edit, clean, folder scan, exports, close during scan |
| `tests/test_core.py`, `test_gui.py`, `test_exiftool_integration.py` | Original 2.0 checks |

When you fix a bug, add a test that fails without the fix.

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
