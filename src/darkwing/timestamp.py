"""Video timestamp extraction for NVR footage.

Provides automatic extraction of the video start time from:
1. OCR on burned-in timestamp overlay (primary — most reliable for NVR footage)
2. User-provided override (last resort)

Note: file metadata (``creation_time``) is intentionally NOT used because it
records when the file was written to disk, not the wall-clock time encoded in
the video's burned-in overlay. For NVR footage the overlay is the source of
truth.
"""
from __future__ import annotations

import datetime
import re
from pathlib import Path
from typing import Optional

import cv2


def extract_video_start_time(video_path: Path) -> Optional[datetime.datetime]:
    """Extract the true video start time via OCR on the burned-in timestamp.

    Returns:
        datetime object representing the start time, or None if extraction fails.
    """
    return _extract_from_ocr(video_path)


def _extract_from_ocr(video_path: Path) -> Optional[datetime.datetime]:
    """Extract timestamp from burned-in overlay using OCR."""
    try:
        import pytesseract
    except ImportError:
        return None

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return None

    ok, frame = cap.read()
    cap.release()

    if not ok or frame is None:
        return None

    h, w = frame.shape[:2]

    # Crop the timestamp overlay area (top portion of frame)
    # Based on testing: region (0:28, 0:448) works well for this NVR format
    # Crop a bit wider to be safe across different resolutions
    crop_h = max(int(h * 0.08), 30)
    crop_w = max(int(w * 0.7), 400)
    overlay = frame[0:crop_h, 0:crop_w]

    # Upscale for better OCR
    scale = 4
    overlay = cv2.resize(
        overlay, (overlay.shape[1] * scale, overlay.shape[0] * scale), interpolation=cv2.INTER_CUBIC
    )

    # Convert to grayscale
    gray = cv2.cvtColor(overlay, cv2.COLOR_BGR2GRAY)

    # Threshold for better OCR
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # Try OCR with single-line mode
    text = pytesseract.image_to_string(thresh, config="--psm 7")
    text = text.strip()

    # Parse the timestamp: "MM/DD/YYYY HH:MM:SS am/pm DAY"
    # Example: "06/15/2026 06:59:56 am MON"
    match = re.match(
        r"(\d{1,2})/(\d{1,2})/(\d{4})\s+(\d{1,2}):(\d{2}):(\d{2})\s+(am|pm)\s*(\w+)?",
        text,
        re.IGNORECASE,
    )
    if not match:
        # Try grayscale without threshold as fallback
        text2 = pytesseract.image_to_string(gray, config="--psm 7").strip()
        match = re.match(
            r"(\d{1,2})/(\d{1,2})/(\d{4})\s+(\d{1,2}):(\d{2}):(\d{2})\s+(am|pm)\s*(\w+)?",
            text2,
            re.IGNORECASE,
        )
        if not match:
            return None
        text = text2

    month, day, year, hour, minute, second, ampm, _ = match.groups()
    hour = int(hour)
    minute = int(minute)
    second = int(second)

    # Convert 12-hour to 24-hour
    if ampm.lower() == "pm" and hour != 12:
        hour += 12
    elif ampm.lower() == "am" and hour == 12:
        hour = 0

    return datetime.datetime(int(year), int(month), int(day), hour, minute, second)


def parse_user_start_time(time_str: str) -> datetime.datetime:
    """Parse user-provided --video-start-time string.

    Accepts formats:
    - "HH:MM:SS"
    - "HH:MM"
    """
    parts = time_str.split(":")
    if len(parts) == 3:
        return datetime.datetime(1970, 1, 1, int(parts[0]), int(parts[1]), int(parts[2]))
    elif len(parts) == 2:
        return datetime.datetime(1970, 1, 1, int(parts[0]), int(parts[1]), 0)
    else:
        raise ValueError(f"Invalid time format: {time_str}. Use HH:MM:SS or HH:MM")


def compute_time_offset(video_start: datetime.datetime, clip_start_hour: int) -> int:
    """Compute the offset in seconds between video start and clip start hour.

    Args:
        video_start: The actual video start datetime (from OCR/metadata)
        clip_start_hour: The hour that frame 0 should map to (e.g., 7 for 7 AM)

    Returns:
        Offset in seconds to SUBTRACT from raw frame timestamps to align
        with clip_start_hour. Positive = video starts before clip_start_hour.
    """
    video_hour = video_start.hour
    video_minute = video_start.minute
    video_second = video_start.second

    video_total_seconds = video_hour * 3600 + video_minute * 60 + video_second
    clip_total_seconds = clip_start_hour * 3600

    # If video starts at 06:59:54 and clip_start_hour=7:
    # video_total_seconds = 6*3600 + 59*60 + 54 = 25194
    # clip_total_seconds = 7*3600 = 25200
    # offset = 25200 - 25194 = 6 seconds
    # So we add 6 seconds to raw timestamps to align
    return clip_total_seconds - video_total_seconds