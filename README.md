# Kai Metadata Inspector

Kai Metadata Inspector is a Linux desktop application for inspecting, exporting, cleaning, and editing image metadata.

It is designed as an offline-first metadata utility for privacy checks, forensic-style inspection, and general image metadata analysis.

## Current release status

**Version:** v1.0 Linux Alpha  
**Platform:** Linux (developed and tested on Kali Linux)  
**Status:** Pre-release / polishing stage

---

## Main features

### Inspection
- Open a single image/file and inspect its metadata automatically
- Open a folder and browse supported image files
- Preview supported image formats inside the app
- View metadata in a structured table
- Detect useful information such as:
  - camera / phone make and model
  - GPS/location metadata
  - timestamps and date taken
  - software / editing metadata
  - file information and format details

### Export
- Export selected file metadata to TXT
- Export folder summary to TXT
- Export folder summary to CSV
- Export all loaded folder reports to TXT
- Export all loaded folder reports to JSON

### Cleaning
- Create a cleaned copy of an image with metadata removed
- Keep original file untouched during cleaned-copy workflow

### Editing
- Edit selected metadata fields
- Write new metadata directly to the selected original file
- Reload and verify metadata after saving

### Folder workflow
- Open folder of supported files
- Browse file list
- Move through files using Previous / Next
- Inspect metadata file-by-file inside one interface

---

## Supported formats

Metadata extraction is powered by **ExifTool**.

Supported inspection targets include common image and metadata-friendly formats such as:

- JPG / JPEG
- PNG
- WEBP
- HEIC / HEIF
- TIFF
- BMP
- GIF
- AVIF
- DNG
- PSD
- XMP sidecar files
- Many RAW camera formats, including:
  - CR2 / CR3
  - NEF
  - ARW
  - RW2
  - ORF
  - RAF
  - PEF
  - SRW

### Preview support
Preview support depends on format support in the app/runtime environment.

Common preview-tested formats include:
- JPG / JPEG
- PNG
- WEBP
- BMP
- GIF
- HEIC / HEIF (if supported in your environment)

Some file types may extract metadata correctly even if preview is unavailable.

---

## Security and privacy

Kai Metadata Inspector is designed to be:

- offline-first
- local-only
- no telemetry
- no analytics
- no automatic upload
- no automatic internet access
- no automatic URL opening from metadata

### Important privacy note
This app may display or export sensitive information such as:

- GPS coordinates
- timestamps
- device model
- software/editing history
- creator/author fields
- copyright fields
- other embedded metadata

Be careful before sharing:
- screenshots of the app
- exported TXT / CSV / JSON reports
- modified or original files containing metadata

### Important editing note
Kai Metadata Inspector includes a metadata editing feature that can write metadata directly to the selected original file.

If you use **Edit metadata / Save new metadata**, the original file may be changed.

If you want a non-destructive workflow, use:
- **Create cleaned copy**
- or work on copies of your files first

---

## Dependencies

Kai Metadata Inspector depends on:

- Python 3
- PySide6
- Pillow
- ExifTool

Depending on your environment, HEIC/HEIF preview support may require additional image support libraries.

---

## Installation on Kali Linux

### 1. Install system dependencies
```bash
sudo apt update
sudo apt install -y git python3 python3-pip python3-venv libimage-exiftool-perl libxcb-cursor0
