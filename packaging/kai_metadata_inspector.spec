# -*- mode: python ; coding: utf-8 -*-
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all

root = Path(SPECPATH).parent
datas = []
binaries = []
hiddenimports = []

for package in ("pillow_heif",):
    package_datas, package_binaries, package_hidden = collect_all(package)
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_hidden

vendor = root / "vendor" / "exiftool"
if vendor.exists():
    for path in vendor.rglob("*"):
        if path.is_file():
            destination = str(Path("vendor/exiftool") / path.relative_to(vendor).parent)
            datas.append((str(path), destination))

a = Analysis(
    [str(root / "app.py")],
    pathex=[str(root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["PyQt6", "tkinter"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True,
    name="Kai Metadata Inspector", console=False, debug=False,
    strip=False, upx=False, argv_emulation=False,
    target_arch=None,
)
coll = COLLECT(
    exe, a.binaries, a.datas, strip=False, upx=False,
    name="Kai Metadata Inspector",
)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="Kai Metadata Inspector.app",
        bundle_identifier="com.kai.metadata-inspector",
        info_plist={
            "CFBundleShortVersionString": "2.0.0",
            "CFBundleVersion": "2.0.0",
            "NSHighResolutionCapable": True,
            "CFBundleDocumentTypes": [{
                "CFBundleTypeName": "Image",
                "CFBundleTypeRole": "Viewer",
                "LSHandlerRank": "Alternate",
                "LSItemContentTypes": ["public.image"],
            }],
        },
    )
