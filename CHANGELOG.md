# Changelog

## 2.1.0 — unreleased

A correctness and data-safety release found by a full audit of 2.0. Every fix below has
a regression test; the suite grew from 10 to 87 tests.

### Fixed — privacy and data safety

- **TIFF "clean copies" still contained camera make/model, artist, software, copyright
  and dates.** ExifTool's `-all=` cannot delete IFD0 in TIFF-based files; those tags are
  now removed explicitly.
- **Cleaning removed the orientation tag and the colour profile**, so cleaned phone photos
  displayed rotated and colours shifted. Both are now kept (neither identifies a person
  or device). Image data is still never re-encoded.
- **Editing one field rewrote every pre-filled field.** A title-only edit overwrote
  `ModifyDate` and the XMP dates with the capture date and re-wrote GPS. Only fields the
  user changes are written now.
- **XMP GPS was written without its sign**, so after any save on a southern/western photo
  XMP said one hemisphere and EXIF the other.
- **`nan`/`inf` coordinates passed validation.** ExifTool rejected the number but still
  rewrote the hemisphere reference, silently moving the photo (S → N).
- **Impossible dates** (`2024:13:45 …`) passed validation.
- **Keywords were appended on every save**, producing duplicates.
- **Files whose only date is an XMP date with a time zone could not be edited at all**:
  the editor pre-filled a value its own validation rejected.
- **An uncleaned copy could exist under the cleaned file's name while cleaning ran.**
  Cleaning now works on a hidden temporary file that is moved into place only on success.
- Editing wrote a `*_write_metadata_report.txt` (containing the metadata) next to the
  photo. It is no longer created; the result is verified by re-reading the file instead.

### Fixed — accuracy

- GPS date/time stamps were never detected and GPS speed/direction never shown, because
  the analyzer looked for a `GPS:` group that ExifTool's `-G` output reports as `EXIF:`.
  Privacy-risk scores for such files were one point too low.
- IPTC by-line/copyright, XMP make/model/software and `XMP:DateCreated` now count toward
  owner, device, software and timestamp detection.

### Fixed — application

- Closing the window during a folder scan left the scan running until it finished; it is
  now cancelled.
- Export to an unwritable location raised inside a Qt slot instead of showing an error.
- Clicking a folder item could start the same inspection twice.

### Added

- The editor pre-fills title, description, creator, copyright, keywords and altitude.
- Clearing a field in the editor removes it from the file.
- After saving, fields that did not read back as entered are reported.
- The cleaning comparison warns when sensitive metadata is still present.

### Changed

- Folder scans read files in batches with one ExifTool process per 25 files
  (50 small files: 5.5 s → 0.3 s with a system ExifTool on Linux).
- Preview decoding of a 24 MP JPEG: 1.3 s → 0.4 s (decoder-side downscaling, no PNG
  round-trip).

### Known limitations

- BMP cannot be cleaned or edited (ExifTool cannot write BMP); the app reports this and
  leaves the file untouched.
- AVIF, DNG, PSD, XMP sidecars and camera RAW files are not covered by automated tests,
  and RAW files have no preview.
- Recovery backups in the app data `backups/` folder are never deleted automatically and
  contain the original metadata.
- Automated tests ran on Linux only. The Windows and macOS build jobs run the suite
  without ExifTool, so ExifTool-dependent tests are skipped there.

## 2.0.0 — release candidate

### Added

- Windows x64 and macOS Intel/Apple Silicon native build workflows
- Bundled ExifTool discovery and runtime diagnostics
- Searchable metadata table and privacy-risk badge
- Background folder scanning
- Visible folder progress with cooperative cancellation
- Before/after cleaning comparison with removed and remaining tag lists
- Linux x86_64 AppImage build and packaged smoke test
- Recovery backups before in-place metadata editing
- Platform-native output directories
- Automated core, GUI, integration, lint, and packaged smoke checks

### Fixed

- South/west GPS coordinates retaining an incorrect positive sign
- Inconsistent single-file and folder metadata results
- Duplicate clean-button invocation
- Non-serializable JSON exports
- Source-tree output paths in packaged applications
- Mixed PyQt/PySide imports and dead UI placeholders
- Overlapping background jobs re-enabling controls and resetting the cursor too early

### Changed

- ExifTool is the single metadata source of truth
- Pillow is used only for local image previews
- The UI uses the KAI black/charcoal, sharp rectangular, purple/cyan visual system
- UI workers, dialogs, styling, and display helpers are separated into focused modules
