#!/bin/sh
set -eu

PROJECT_ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)"
DIST_DIR="$PROJECT_ROOT/dist/Kai Metadata Inspector"
APPDIR="${1:-$PROJECT_ROOT/build/KaiMetadataInspector.AppDir}"
OUTPUT="${2:-$PROJECT_ROOT/dist/Kai-Metadata-Inspector-2.0.0-x86_64.AppImage}"
APPIMAGETOOL="${APPIMAGETOOL:-appimagetool}"

if [ ! -x "$DIST_DIR/Kai Metadata Inspector" ]; then
    echo "PyInstaller output not found: $DIST_DIR" >&2
    exit 1
fi

rm -rf "$APPDIR"
mkdir -p \
    "$APPDIR/usr/bin" \
    "$APPDIR/usr/lib/kai-metadata-inspector" \
    "$APPDIR/usr/share/applications" \
    "$APPDIR/usr/share/icons/hicolor/scalable/apps"

cp -a "$DIST_DIR/." "$APPDIR/usr/lib/kai-metadata-inspector/"
cp "$PROJECT_ROOT/packaging/linux/AppRun" "$APPDIR/AppRun"
cp "$PROJECT_ROOT/packaging/linux/kai-metadata-inspector" "$APPDIR/usr/bin/kai-metadata-inspector"
cp "$PROJECT_ROOT/packaging/linux/kai-metadata-inspector.desktop" "$APPDIR/kai-metadata-inspector.desktop"
cp "$PROJECT_ROOT/packaging/linux/kai-metadata-inspector.desktop" "$APPDIR/usr/share/applications/"
cp "$PROJECT_ROOT/packaging/linux/kai-metadata-inspector.svg" "$APPDIR/kai-metadata-inspector.svg"
cp "$PROJECT_ROOT/packaging/linux/kai-metadata-inspector.svg" "$APPDIR/usr/share/icons/hicolor/scalable/apps/"
chmod +x "$APPDIR/AppRun" "$APPDIR/usr/bin/kai-metadata-inspector"

mkdir -p "$(dirname -- "$OUTPUT")"
ARCH=x86_64 APPIMAGE_EXTRACT_AND_RUN=1 "$APPIMAGETOOL" "$APPDIR" "$OUTPUT"
[ -f "$OUTPUT" ] || {
    echo "appimagetool completed without creating $OUTPUT" >&2
    exit 1
}
echo "Created $OUTPUT"
