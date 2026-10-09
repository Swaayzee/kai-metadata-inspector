# Project status

## Current release candidate

**Kai Metadata Inspector 2.0.0**

The source refactor and local Linux verification are complete. Windows x64, macOS Intel, macOS Apple Silicon, and Linux x86_64 AppImage workflows are ready for native CI validation.

## Verified locally

- Python compilation
- Ruff static checks
- Core and headless GUI tests
- Real ExifTool 13.59 read/write/clean integration
- Correct negative coordinates for south/west GPS metadata
- Original-file SHA-256 preservation during cleaning
- Frozen PyInstaller build and bundled ExifTool diagnostics
- Cancelable folder scan progress and before/after cleaning comparison
- Deterministic documentation screenshot
- AppDir assembly and AppImage workflow definition

## Release gates still requiring native infrastructure

- Windows artifact launch and clean/edit smoke test
- Intel and Apple Silicon macOS artifact launch and clean/edit smoke test
- Linux AppImage launch and clean/edit smoke test on a compatible distribution
- Code-signing certificate for reputation-friendly Windows distribution
- Apple Developer ID signing and notarization for Gatekeeper-friendly macOS distribution

Unsigned CI artifacts are suitable for preview testing, not a polished public-store release.
