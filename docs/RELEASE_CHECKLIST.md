# Kai Metadata Inspector — Release Checklist

## Version

Target release: v1.0 Linux Alpha

## Core functionality

- [ ] App launches with `python app.py`
- [ ] App launches with `./run.sh`
- [ ] Open Image / File works
- [ ] Image preview works for JPG/PNG/WEBP/BMP/GIF
- [ ] Unsupported preview formats fail gracefully
- [ ] Metadata tabs display correctly
- [ ] Raw metadata search works
- [ ] Export TXT works
- [ ] Export Raw JSON works
- [ ] Open Folder works
- [ ] Folder file list works
- [ ] Clicking files in folder list works
- [ ] Scan Folder Summary works
- [ ] Export Folder Summary TXT works
- [ ] Export Summary CSV works
- [ ] Export All TXT works
- [ ] Export All JSON works
- [ ] Clear button works

## Security and privacy

- [ ] App is read-only
- [ ] App does not modify original files
- [ ] App does not upload anything
- [ ] App does not use internet automatically
- [ ] App does not auto-open map links
- [ ] ExifTool is called without `shell=True`
- [ ] ExifTool timeout exists
- [ ] Metadata is displayed as plain text
- [ ] Reports include privacy warning
- [ ] Reports folder is ignored by Git

## Test files

Test with:

- [ ] JPG with metadata
- [ ] JPG without GPS
- [ ] PNG screenshot
- [ ] WEBP image
- [ ] HEIC/HEIF image if available
- [ ] TIFF if available
- [ ] RAW/DNG if available
- [ ] Folder with multiple images
- [ ] File with unsupported extension
- [ ] Large file warning

## GitHub readiness

- [ ] README.md is updated
- [ ] SECURITY.md exists
- [ ] LICENSE exists
- [ ] ROADMAP.md exists
- [ ] PROJECT_STATUS.md updated
- [ ] requirements.txt updated
- [ ] run.sh works
- [ ] No private reports committed
- [ ] No private images committed
- [ ] Screenshots are redacted before publishing
