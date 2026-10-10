"""Create the README screenshot from deterministic sample data."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw
from PySide6.QtWidgets import QApplication

from kai_metadata_inspector.core.analyzer import build_analysis
from kai_metadata_inspector.ui.main_window import MainWindow


def create_sample_image(path: Path) -> None:
    image = Image.new("RGB", (1100, 760), "#080b12")
    draw = ImageDraw.Draw(image)
    for y in range(image.height):
        ratio = y / image.height
        draw.line((0, y, image.width, y), fill=(int(22 + 32 * ratio), int(13 + 18 * ratio), int(43 + 55 * ratio)))
    draw.rectangle((100, 90, 1000, 670), outline="#8cf7ff", width=5)
    draw.rectangle((145, 135, 955, 625), outline="#7048ff", width=11)
    draw.text((205, 285), "KAI // PRIVACY FIRST", fill="#f1eaff", stroke_fill="#7048ff", stroke_width=1)
    image.save(path, quality=92)


def main() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance() or QApplication([])
    with tempfile.TemporaryDirectory() as temp_dir:
        sample = Path(temp_dir) / "kai-city-night.jpg"
        create_sample_image(sample)
        raw = {
            "File:FileName": sample.name,
            "File:FileType": "JPEG",
            "File:MIMEType": "image/jpeg",
            "File:ImageWidth": 1100,
            "File:ImageHeight": 760,
            "Composite:Megapixels": 0.84,
            "EXIF:Make": "KAI Imaging",
            "EXIF:Model": "K-2",
            "EXIF:SerialNumber": "KAI-2026-001",
            "EXIF:DateTimeOriginal": "2026:10:09 21:42:00",
            "EXIF:OffsetTimeOriginal": "+01:00",
            "EXIF:Software": "Darktable 5.0",
            "GPS:GPSLatitude": 51.5074,
            "GPS:GPSLatitudeRef": "N",
            "GPS:GPSLongitude": 0.1278,
            "GPS:GPSLongitudeRef": "W",
            "XMP:Creator": "Kai Studio",
            "ICC_Profile:ProfileDescription": "Display P3",
        }
        window = MainWindow()
        window.current_path = sample
        window.path_label.setText("~/Pictures/kai-city-night.jpg")
        window._load_preview(sample)
        window._inspection_ready((raw, build_analysis(sample, raw, "13.59")))
        window.resize(1400, 880)
        window.show()
        app.processEvents()
        output = Path(__file__).resolve().parents[1] / "docs/images/kai-metadata-inspector-2.0.png"
        if not window.grab().save(str(output), "PNG"):
            raise RuntimeError(f"Could not write screenshot: {output}")
        window.close()
        print(output)


if __name__ == "__main__":
    main()
