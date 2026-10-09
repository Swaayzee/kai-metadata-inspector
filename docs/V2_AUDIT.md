# Version 2.0 audit and design record

## 1.0 findings

The 1.0 repository had good safety intent but several release blockers:

1. `main_window.py` was 1,925 lines and duplicated inspection, cleaning, hashing, GPS, reporting, and output-path logic already present in `core/`.
2. Single files were inspected with Pillow while folder summaries used ExifTool, so results could disagree.
3. The clean button was connected twice and could start two cleaning operations from one click.
4. Folder JSON export attempted to serialize a `Path`, causing a runtime error.
5. Folder scans and exports ran on the GUI thread and could make the app appear frozen.
6. Outputs were written relative to the source/application bundle, which is commonly read-only after packaging.
7. ExifTool was resolved only as the Linux command `exiftool`; packaged Windows/macOS builds could not find it.
8. GPS handling could lose south/west signs when the editor preferred unsigned values.
9. Editing overwrote the original without an application-managed recovery copy.
10. Dependencies were unpinned, and no automated tests or native packaging workflow existed.

## 2.0 decisions

- ExifTool is the only authoritative metadata engine; Pillow is preview-only.
- ExifTool receives `-n` numeric output and GPS signs are normalized explicitly.
- Every subprocess uses a sequence of arguments and `shell=False` behavior.
- Long folder scans run in Qt's thread pool.
- Folder scans report progress, can be cancelled between files, and do not corrupt overlapping job state.
- Runtime outputs and backups use platform-native per-user application data directories.
- Cleaning always targets a new path and verifies the source hash before/after.
- Cleaning presents removed and remaining tag names before the user optionally inspects the copy.
- Editing creates a timestamped recovery copy and restores it automatically if ExifTool fails.
- JSON values are normalized before serialization.
- Native builds use PyInstaller `onedir`, which is easier to diagnose and more reliable for Qt than hiding everything in a self-extracting executable.
- Linux CI turns the same `onedir` output into a standard AppDir and then an x86_64 AppImage.
- ExifTool 13.59 is downloaded from its official SourceForge distribution during native builds.

## Research basis

- ExifTool's official documentation describes it as a platform-independent reader/writer for many metadata families and documents the `-all=` removal workflow: <https://exiftool.org/exiftool_pod.html>
- PyInstaller documents platform-specific native builds, `--add-data`, macOS architecture selection, bundle identifiers, and code-signing options: <https://pyinstaller.org/en/stable/usage.html>
- AppImage documents AppDir layout and its required `AppRun` entry point: <https://docs.appimage.org/reference/appdir.html>
- Apple requires Developer ID signing and notarization for smooth distribution outside the Mac App Store: <https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution>
- Microsoft documents signed application requirements for Smart App Control: <https://learn.microsoft.com/en-us/windows/apps/develop/smart-app-control/code-signing-for-smart-app-control>

## Deliberately deferred

AI explanations, maps, reverse geocoding, cloud storage, and decorative dashboards were rejected for 2.0. They add network/privacy surface or visual noise without making the core privacy workflow safer.
