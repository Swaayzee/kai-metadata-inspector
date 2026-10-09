from pathlib import Path

from kai_metadata_inspector.config import APP_VERSION, MAX_FILE_SIZE_MB_WARNING


def get_any(metadata: dict, possible_keys: list[str], default: str = "Not found") -> str:
    for key in possible_keys:
        value = metadata.get(key)
        if value not in [None, ""]:
            return str(value)
    return default


def has_any(metadata: dict, possible_keys: list[str]) -> bool:
    for key in possible_keys:
        value = metadata.get(key)
        if value not in [None, "", "Not found"]:
            return True
    return False


def clean_text(value: object, max_length: int = 5000) -> str:
    text = str(value)

    if len(text) > max_length:
        return text[:max_length] + "\n...[truncated for safe display]"

    return text


def format_section(title: str, data: dict) -> str:
    lines = [title, "=" * len(title), ""]

    for key, value in data.items():
        lines.append(f"{key}: {clean_text(value)}")

    return "\n".join(lines)


def signed_coordinate(raw: dict, axis: str) -> str:
    """Return signed decimal GPS, honoring south/west references."""
    key = "GPSLatitude" if axis == "lat" else "GPSLongitude"
    ref_key = f"{key}Ref"
    composite = raw.get(f"Composite:{key}")
    value = composite if composite not in (None, "") else raw.get(f"GPS:{key}")
    if value in (None, ""):
        return "Not found"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    ref = str(raw.get(f"GPS:{ref_key}", "")).upper()
    if ref in {"S", "W"} and number > 0:
        number = -number
    return f"{number:.8f}".rstrip("0").rstrip(".")


def gps_map_text(latitude: str, longitude: str) -> str:
    if latitude == "Not found" or longitude == "Not found":
        return "Not available"

    return f"https://maps.google.com/?q={latitude},{longitude}"


def timezone_status(raw: dict) -> tuple[str, str]:
    offset_original = get_any(raw, ["EXIF:OffsetTimeOriginal"])
    offset_digitized = get_any(raw, ["EXIF:OffsetTimeDigitized"])
    offset_general = get_any(raw, ["EXIF:OffsetTime"])

    gps_date = get_any(raw, ["GPS:GPSDateStamp"])
    gps_time = get_any(raw, ["GPS:GPSTimeStamp"])

    if offset_original != "Not found":
        return "Stored timezone offset found", f"OffsetTimeOriginal: {offset_original}"

    if offset_digitized != "Not found":
        return "Stored timezone offset found", f"OffsetTimeDigitized: {offset_digitized}"

    if offset_general != "Not found":
        return "Stored timezone offset found", f"OffsetTime: {offset_general}"

    if gps_date != "Not found" or gps_time != "Not found":
        return (
            "Timezone not directly stored",
            "GPS date/time exists and is usually UTC/GPS time. Local timezone may need manual interpretation."
        )

    return (
        "Timezone not found",
        "No timezone offset fields or GPS time fields were found."
    )


def build_analysis(file_path: Path, raw: dict, exiftool_version: str) -> dict:
    file_size_mb = file_path.stat().st_size / (1024 * 1024)

    gps_lat = signed_coordinate(raw, "lat")
    gps_lon = signed_coordinate(raw, "lon")
    tz_status, tz_explanation = timezone_status(raw)

    file_info = {
        "File name": file_path.name,
        "File path": str(file_path.resolve()),
        "File extension": file_path.suffix.lower(),
        "File size": f"{file_size_mb:.2f} MB",
        "ExifTool version": exiftool_version,
        "File type": get_any(raw, ["File:FileType", "File:FileTypeExtension"]),
        "MIME type": get_any(raw, ["File:MIMEType"]),
        "Image width": get_any(raw, ["File:ImageWidth", "EXIF:ExifImageWidth", "PNG:ImageWidth"]),
        "Image height": get_any(raw, ["File:ImageHeight", "EXIF:ExifImageHeight", "PNG:ImageHeight"]),
        "Megapixels": get_any(raw, ["Composite:Megapixels"]),
        "Color profile": get_any(raw, ["ICC_Profile:ProfileDescription", "ICC_Profile:ColorSpaceData"]),
    }

    device_info = {
        "Make": get_any(raw, ["EXIF:Make", "IFD0:Make", "QuickTime:Make"]),
        "Model": get_any(raw, ["EXIF:Model", "IFD0:Model", "QuickTime:Model"]),
        "Lens model": get_any(raw, ["EXIF:LensModel", "Composite:LensID", "MakerNotes:LensModel"]),
        "Lens make": get_any(raw, ["EXIF:LensMake"]),
        "Serial number": get_any(raw, [
            "EXIF:SerialNumber",
            "MakerNotes:SerialNumber",
            "MakerNotes:CameraSerialNumber",
            "Composite:SerialNumber",
        ]),
        "Firmware": get_any(raw, ["MakerNotes:FirmwareVersion", "EXIF:FirmwareVersion"]),
    }

    time_info = {
        "Date/time original": get_any(raw, ["EXIF:DateTimeOriginal", "XMP:DateCreated"]),
        "Create date": get_any(raw, ["EXIF:CreateDate", "QuickTime:CreateDate", "XMP:CreateDate"]),
        "Modify date": get_any(raw, ["EXIF:ModifyDate", "File:FileModifyDate", "XMP:ModifyDate"]),
        "Offset time original": get_any(raw, ["EXIF:OffsetTimeOriginal"]),
        "Offset time digitized": get_any(raw, ["EXIF:OffsetTimeDigitized"]),
        "Offset time": get_any(raw, ["EXIF:OffsetTime"]),
        "GPS date stamp": get_any(raw, ["GPS:GPSDateStamp"]),
        "GPS time stamp": get_any(raw, ["GPS:GPSTimeStamp"]),
        "Timezone status": tz_status,
        "Timezone explanation": tz_explanation,
    }

    location_info = {
        "GPS latitude": gps_lat,
        "GPS longitude": gps_lon,
        "GPS altitude": get_any(raw, ["GPS:GPSAltitude", "Composite:GPSAltitude"]),
        "GPS speed": get_any(raw, ["GPS:GPSSpeed"]),
        "GPS direction": get_any(raw, ["GPS:GPSImgDirection", "Composite:GPSImgDirection"]),
        "Map link text": gps_map_text(gps_lat, gps_lon),
        "Location note": "No online lookup is performed. Coordinates are displayed locally only.",
    }

    camera_info = {
        "ISO": get_any(raw, ["EXIF:ISO", "MakerNotes:ISO"]),
        "Aperture": get_any(raw, ["EXIF:FNumber", "Composite:Aperture"]),
        "Exposure time": get_any(raw, ["EXIF:ExposureTime"]),
        "Shutter speed": get_any(raw, ["Composite:ShutterSpeed"]),
        "Focal length": get_any(raw, ["EXIF:FocalLength", "Composite:FocalLength"]),
        "35mm equivalent focal length": get_any(raw, ["EXIF:FocalLengthIn35mmFormat"]),
        "Flash": get_any(raw, ["EXIF:Flash"]),
        "White balance": get_any(raw, ["EXIF:WhiteBalance"]),
        "Exposure mode": get_any(raw, ["EXIF:ExposureMode"]),
        "Metering mode": get_any(raw, ["EXIF:MeteringMode"]),
    }

    software_info = {
        "Software": get_any(raw, ["EXIF:Software", "IFD0:Software"]),
        "Creator tool": get_any(raw, ["XMP:CreatorTool"]),
        "Processing software": get_any(raw, ["EXIF:ProcessingSoftware"]),
        "History": get_any(raw, ["XMP:HistoryAction", "XMP:HistorySoftwareAgent"]),
        "Artist": get_any(raw, ["EXIF:Artist", "IFD0:Artist", "XMP:Creator"]),
        "Copyright": get_any(raw, ["EXIF:Copyright", "IFD0:Copyright", "XMP:Rights"]),
    }

    gps_found = gps_lat != "Not found" or gps_lon != "Not found"
    time_found = has_any(raw, ["EXIF:DateTimeOriginal", "EXIF:CreateDate", "QuickTime:CreateDate", "XMP:CreateDate"])
    timezone_found = has_any(raw, ["EXIF:OffsetTimeOriginal", "EXIF:OffsetTimeDigitized", "EXIF:OffsetTime"])
    gps_time_found = has_any(raw, ["GPS:GPSDateStamp", "GPS:GPSTimeStamp"])
    device_found = has_any(raw, ["EXIF:Make", "EXIF:Model", "IFD0:Make", "IFD0:Model", "QuickTime:Model"])
    serial_found = has_any(raw, [
        "EXIF:SerialNumber",
        "MakerNotes:SerialNumber",
        "MakerNotes:CameraSerialNumber",
        "Composite:SerialNumber",
    ])
    owner_found = has_any(raw, ["EXIF:Artist", "IFD0:Artist", "XMP:Creator", "XMP:Rights", "EXIF:Copyright"])
    software_found = has_any(raw, ["EXIF:Software", "IFD0:Software", "XMP:CreatorTool"])

    risk_points = 0
    reasons = []

    if gps_found:
        risk_points += 4
        reasons.append("GPS coordinates found. This may reveal where the image was taken.")

    if time_found:
        risk_points += 2
        reasons.append("Capture or creation timestamp found. This may reveal when the image was taken.")

    if timezone_found:
        risk_points += 1
        reasons.append("Timezone offset found. This can make timestamps more precise.")

    if gps_time_found:
        risk_points += 1
        reasons.append("GPS timestamp found. This may help reconstruct the exact capture timeline.")

    if device_found:
        risk_points += 1
        reasons.append("Camera or phone model found.")

    if serial_found:
        risk_points += 3
        reasons.append("Device serial number found. This can be sensitive.")

    if owner_found:
        risk_points += 3
        reasons.append("Owner, creator, artist or copyright information found.")

    if software_found:
        risk_points += 1
        reasons.append("Software or editing tool information found.")

    if not reasons:
        reasons.append("No obvious sensitive metadata found. Metadata may also have been stripped.")

    if risk_points >= 9:
        risk_level = "CRITICAL"
    elif risk_points >= 6:
        risk_level = "HIGH"
    elif risk_points >= 3:
        risk_level = "MEDIUM"
    else:
        risk_level = "LOW"

    privacy_info = {
        "Privacy risk": risk_level,
        "Risk score": f"{risk_points} point(s)",
        "Reasons": "\n- " + "\n- ".join(reasons),
        "Important warning": (
            "Exported reports may contain sensitive information. "
            "Be careful before sharing reports or screenshots."
        ),
    }

    interesting = []

    if gps_found:
        interesting.append("GPS/location metadata is present.")
    else:
        interesting.append("No GPS coordinates found.")

    if time_found:
        interesting.append("Timestamp metadata is present.")
    else:
        interesting.append("No obvious original timestamp found.")

    if timezone_found:
        interesting.append("Timezone offset is stored in the image metadata.")
    elif gps_time_found:
        interesting.append("GPS time exists, but local timezone offset was not directly found.")
    else:
        interesting.append("No timezone information found.")

    if device_found:
        interesting.append("Device make/model metadata is present.")

    if serial_found:
        interesting.append("Serial number metadata is present. This can be sensitive.")

    if owner_found:
        interesting.append("Creator/owner/copyright metadata is present.")

    if software_found:
        interesting.append("Software/editing metadata is present.")

    if file_size_mb > MAX_FILE_SIZE_MB_WARNING:
        interesting.append(f"Large file warning: file is {file_size_mb:.2f} MB.")

    overview = {
        "App version": APP_VERSION,
        "File": file_path.name,
        "Format": file_info["File type"],
        "Device": f"{device_info['Make']} {device_info['Model']}",
        "Capture time": time_info["Date/time original"],
        "Timezone": tz_status,
        "GPS": "Found" if gps_found else "Not found",
        "Privacy risk": risk_level,
        "Risk score": f"{risk_points} point(s)",
        "Interesting findings": "\n- " + "\n- ".join(interesting),
    }

    return {
        "overview": overview,
        "file": file_info,
        "device": device_info,
        "time": time_info,
        "location": location_info,
        "camera": camera_info,
        "software": software_info,
        "privacy": privacy_info,
        "interesting": interesting,
        "raw": raw,
        "flags": {
            "gps_found": gps_found,
            "time_found": time_found,
            "timezone_found": timezone_found,
            "gps_time_found": gps_time_found,
            "device_found": device_found,
            "serial_found": serial_found,
            "owner_found": owner_found,
            "software_found": software_found,
            "risk_points": risk_points,
            "risk_level": risk_level,
            "gps_latitude": gps_lat,
            "gps_longitude": gps_lon,
        }
    }
