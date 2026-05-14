# Kai Metadata Inspector — Project Status

## Project

Kai Metadata Inspector

## Author

Patryk Klimczyk

## Current version

**v1.0 Linux Alpha**

## Current platform

- Linux
- Developed and tested primarily on Kali Linux

---

## Current release state

Kai Metadata Inspector is now in a v1.0 Linux Alpha polishing stage.

The core feature set is in place and working.

Current priority:

- final cleanup
- release documentation
- testing
- repository hygiene
- public release preparation

---

## Core working features

### Inspection

- Open a single image/file
- Automatically inspect metadata on load
- Display metadata in a structured table
- Preview supported files in the UI
- Detect useful metadata such as:
  - device make/model
  - GPS/location fields
  - timestamps
  - software/editing metadata
  - file/format details

### Folder tools

- Open folder of supported image files
- Show folder file list
- Load metadata when user selects a file
- Navigate using Previous / Next
- Generate folder summary

### Export

- Export selected file report to TXT
- Export folder summary to TXT
- Export folder summary to CSV
- Export all loaded folder reports to TXT
- Export all loaded folder reports to JSON

### Cleaning

- Create cleaned copies with metadata removed
- Preserve original file during cleaned-copy workflow

### Editing

- Edit selected metadata fields
- Write metadata directly to the selected original file
- Reload file after save for verification

### UI

- Dark desktop UI
- Clean final layout
- Centered compact action buttons
- Folder list integrated into main workflow
- Metadata table used as primary information display

---

## Security / privacy behavior

### Current behavior

- Offline-first
- Local-only
- No telemetry
- No analytics
- No automatic upload
- No automatic internet access
- No automatic URL opening from metadata
- ExifTool called without `shell=True`

### Important note

The project is not strictly read-only anymore because it now supports:

- cleaned-copy creation
- direct metadata editing to the selected original file

That behavior is intentional and must be documented clearly.

Users should understand:

- inspection does not modify files
- clean copy mode creates a new output file
- edit metadata mode writes changes directly to the selected original file

---

## Known limitations

- Metadata support varies by file format
- Metadata writing support depends on ExifTool and format capability
- Some formats may extract metadata even when preview is unavailable
- HEIC/HEIF behavior may vary depending on environment and metadata structure
- Some MakerNotes/vendor-specific metadata may not be fully editable
- Windows version is not implemented yet

---

## Final pre-release checklist

- [x] README updated and accurate
- [x] SECURITY.md updated and accurate
- [x] LICENSE updated with final author name
- [x] PROJECT_STATUS.md cleaned
- [x] .gitignore checked
- [ ] remove outputs / backups / cache files from repo
- [ ] remove personal test files from repo
- [ ] verify install steps from clean environment
- [ ] verify all export workflows
- [ ] verify cleaned copy workflow
- [ ] verify metadata editing workflow
- [ ] add release screenshots using safe sample images
- [ ] final GitHub prep

---

## Not planned for this release

These are intentionally out of scope for v1.0 Linux Alpha:

- AI explanations
- online services
- cloud upload
- automatic map integration
- excessive UI panels
- feature bloat
- Windows release

---

## Planned after release

Possible future work:

- Windows version
- packaging improvements
- broader format testing
- additional UI polish
- workflow refinements only where useful

---

## Release direction

Current recommendation:

- stop adding major features
- focus on documentation accuracy
- perform final testing
- prepare GitHub/public release
