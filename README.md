# Kai Metadata Inspector

Kai Metadata Inspector is a Linux desktop app for inspecting image metadata, privacy risks, GPS data, timestamps, camera/phone information, editing software, and exporting reports.

Current version: **v0.5 Linux Alpha**

## Features

- Open one image/file and inspect metadata
- Open a folder and inspect supported files
- Show metadata in clean sections
- Show raw metadata
- Search raw metadata
- Show privacy-risk score
- Detect GPS metadata
- Detect timestamps
- Detect timezone offset when present
- Detect device make/model
- Detect software/editing metadata
- Export TXT report
- Export raw JSON metadata
- Export folder summary report
- Offline-first
- Read-only by default

## Supported formats

Metadata extraction is powered by ExifTool.

Target formats include:

- JPG / JPEG
- PNG
- WEBP
- HEIC / HEIF
- TIFF
- BMP
- GIF
- AVIF
- DNG
- RAW camera files: CR2, CR3, NEF, ARW, RW2, ORF, RAF, PEF, SRW
- PSD
- XMP sidecar files

Preview support in Alpha is limited to:

- JPG
- JPEG
- PNG
- WEBP
- BMP
- GIF

Some formats may extract metadata correctly even if preview is unavailable.

## Security and privacy

Kai Metadata Inspector is designed to be:

- Offline-first
- Read-only
- No telemetry
- No analytics
- No automatic internet access
- No automatic map opening
- No original-file modification

Important: exported reports may contain sensitive information such as GPS coordinates, timestamps, device model, serial numbers, owner data or editing history. Be careful before sharing reports or screenshots.

## Install on Kali Linux

```bash
sudo apt update
sudo apt install -y git python3 python3-pip python3-venv libimage-exiftool-perl libxcb-cursor0
