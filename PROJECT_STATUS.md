# Kai Metadata Inspector — Project Status

## Current version
v0.1 Linux Alpha

## Working features
- Opens image/file through GUI
- Extracts metadata using ExifTool
- Displays metadata in tabs
- Shows overview
- Shows device information
- Shows time information
- Shows location information
- Shows camera information
- Shows software/editing information
- Shows privacy risk
- Shows raw metadata
- Exports TXT report

## Security rules currently implemented
- Read-only
- No metadata editing
- No internet access
- No AI calls
- No shell=True
- ExifTool runs with argument list
- Timeout added
- TXT report includes privacy warning

## Next planned version
v0.2 Linux Alpha

Planned improvements:
- Add image preview panel
- Improve UI layout
- Add raw metadata search/filter
- Improve GPS display
- Improve timezone notes
- Improve TXT report formatting


-----------------------------------------------


## v0.2 Linux Alpha completed

Added:
- Image preview panel
- Improved left/right layout
- Raw metadata search
- Better quick file information panel

## Next version
v0.3 Linux Alpha

Planned:
- Better GPS detection
- Better timezone detection
- Better privacy-risk explanations
- Safer exported report structure
- Prepare code for future folder scanning


## v0.4 Linux Alpha planned

Goal:
- Add folder scanning
- Show supported files in a selectable list
- Load metadata when user clicks a file
- Keep export TXT and raw JSON for selected file
- Keep app offline and read-only

Not included yet:
- Export all reports
- Folder summary report
- CSV export
- Metadata cleaning
- AI explanation



Open Folder
Folder file list
Click file from list to inspect it
Single image/file mode still works
Export TXT for selected file
Export Raw JSON for selected file
Same offline/read-only security rules



## v0.5 Linux Alpha planned

Goal:
- Add folder summary analysis
- Count files with GPS metadata
- Count files with timestamps
- Count files with camera/phone model
- Count high-risk files
- Show summary in app
- Export folder summary TXT

Not included yet:
- Export all individual reports
- CSV export
- Metadata cleaning
- AI explanation
- Windows support
