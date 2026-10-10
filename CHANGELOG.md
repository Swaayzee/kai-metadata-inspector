# Changelog

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
