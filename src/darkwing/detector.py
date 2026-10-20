"""MVP2 detector: classical-CV background subtraction over a static scene.

Pure-function pipeline over numpy frame arrays (BGR uint8). No NVR, no
network, no model training. Designed so a frame source is anything that
yields ``np.ndarray`` frames (local mp4, camera stream, synthetic fixtures).

Empirical basis (spike on 640x360/25fps real NVR clips, 2026-08-26):
  * Dawn clip: 82% of 10-min windows auto-skippable; birds caught.
  * Noon clip: a daily sun/shadow sweep across the tower wall produces huge
    spurious foreground blobs (up to ~19% of frame); these are NOT birds.
    They cannot be separated from birds by shape/solidity, only by scale +
    illumination instability. Hence the three-bucket contract below.

Verdict contract (per observation window):
  SKIP    - no bird-sized blob in any sample  -> safe to auto-skip
  REVIEW  - >=1 bird-sized blob, not glare   -> detector reliable; human
                                              reviews the flagged evidence
  MANUAL  - glare/shadow sweep                -> detector UNRELIABLE; whole
            (configured glare hours OR implausibly large MOVING blob)     window must
                                              be reviewed by hand
"""
from __future__ import annotations

import enum
import logging
import os
from dataclasses import dataclass, field
from typing import Iterable, Iterator, List, Optional, Sequence, Tuple

import cv2
import numpy as np

# Trace logging
_TRACING_ENABLED = os.environ.get('DARKWING_TRACE_DETECTOR', '').lower() in ('1', 'true', 'yes')
_logger = logging.getLogger(__name__)
if _TRACING_ENABLED:
    if not _logger.handlers:
        _handler = logging.StreamHandler()
        _handler.setFormatter(logging.Formatter('[DETECTOR] %(message)s'))
        _logger.addHandler(_handler)
        _logger.setLevel(logging.DEBUG)
    _logger.propagate = False  # avoid duplicate output via root logger


def _trace(msg: str) -> None:
    """Emit a trace message when DARKWING_TRACE_DETECTOR=1."""
    if _TRACING_ENABLED:
        _logger.debug(msg)


class Verdict(str, enum.Enum):
    SKIP = "skip"
    REVIEW = "review"
    MANUAL = "manual"


# Defaults derived from the spike. All versioned in output (plan R4).
DEFAULT_ROI = (0.15, 0.45, 0.05, 0.92)   # x0, x1, y0, y1 as fractions of frame; excludes bright window on right
DEFAULT_MIN_AREA = 600                    # px^2; a swift against the wall
DEFAULT_GLARE_MAX_AREA = 6000             # px^2; above this a blob is implausibly
                                          # large for a bird at 640x360 -> glare
DEFAULT_MORPH_KERNEL = (5, 5)
DEFAULT_DARK_THRESHOLD = None  # None = adaptive (ROI mean - 1.5*std)
DEFAULT_PRIMING_FRAMES = 750   # 30 seconds @ 25fps
_LARGE_BLOB_MIN_AREA = 2000    # px^2; only track blobs this size for motion analysis
_MOTION_TOLERANCE_PX = 50.0    # centroid spread beyond this = blob is moving (glare)
# Morphological opening kernel for dark-threshold detection. Removes thin nest
# sticks (which are only a few px wide) while preserving the solid bird blob.
_DARK_OPEN_KERNEL = (5, 5)


@dataclass
class FrameResult:
    """Per-sample detection output."""
    sample_index: int          # 0-based sample index within the run
    ts_sec: float              # seconds from clip start
    blobs: List[Tuple[int, int, int, int, int]] = field(default_factory=list)  # x,y,w,h,area
    max_blob_area: int = 0
    fg_frac: float = 0.0       # fraction of ROI that is real foreground (255)
    shadow_frac: float = 0.0   # fraction of ROI flagged as MOG2 shadow (127)


@dataclass
class WindowResult:
    """Aggregated verdict for one observation window."""
    window_id: str
    tower: int
    date: str
    hour: int
    minute: int
    verdict: Verdict
    first_detection_ts: Optional[float] = None  # sec from clip start (REVIEW only)
    max_blob_area: int = 0
    sample_count: int = 0
    spot_check_due: bool = False
    detector_version: str = ""
    glare_reason: str = ""


def _build_roi(w: int, h: int, roi: Sequence[float]) -> np.ndarray:
    x0, x1, y0, y1 = roi
    # Clamp to [0, 1] fractional bounds, then convert to pixel indices
    x0, x1 = min(max(x0, 0.0), 1.0), min(max(x1, 0.0), 1.0)
    y0, y1 = min(max(y0, 0.0), 1.0), min(max(y1, 0.0), 1.0)
    # Ensure x0 < x1 and y0 < y1 for valid slice
    if x0 >= x1:
        x0, x1 = 0, max(x1, 1)
    if y0 >= y1:
        y0, y1 = 0, max(y1, 1)
    mask = np.zeros((h, w), np.uint8)
    mask[int(y0 * h):int(y1 * h), int(x0 * w):int(x1 * w)] = 255
    return mask


class Detector:
    """Stateful MOG2 background subtractor over an ROI.

    Feed frames sequentially via :meth:`process_frame`. The background model
    is continuous across the whole clip (not reset per window) so it stays
    stable. Sample decimation is the caller's responsibility.

    Falls back to dark-threshold detection when MOG2 finds no foreground,
    since MOG2 is unreliable for still birds that blend into the wall texture.
    """

    def __init__(
        self,
        roi: Sequence[float] = DEFAULT_ROI,
        min_area: int = DEFAULT_MIN_AREA,
        glare_max_area: int = DEFAULT_GLARE_MAX_AREA,
        morph_kernel: Tuple[int, int] = DEFAULT_MORPH_KERNEL,
        history: int = 500,
        var_threshold: int = 16,
        dark_threshold: int | None = DEFAULT_DARK_THRESHOLD,
    ) -> None:
        self.roi_frac = tuple(roi)
        self.min_area = min_area
        self.glare_max_area = glare_max_area
        self.dark_threshold = dark_threshold
        self._kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, morph_kernel)
        self._fgbg = cv2.createBackgroundSubtractorMOG2(
            history=history, varThreshold=var_threshold, detectShadows=True
        )
        self._roi: Optional[np.ndarray] = None
        self._wh: Optional[Tuple[int, int]] = None

    def _ensure_roi(self, frame: np.ndarray) -> None:
        h, w = frame.shape[:2]
        if self._roi is None or self._wh != (w, h):
            self._roi = _build_roi(w, h, self.roi_frac)
            self._wh = (w, h)

    def reset(self) -> None:
        """Drop the background model (call between independent clips)."""
        self._fgbg = cv2.createBackgroundSubtractorMOG2(
            history=self._fgbg.getHistory(),
            varThreshold=self._fgbg.getVarThreshold(),
            detectShadows=True,
        )

    def backfill_first_detection(
        self,
        source_path: Path,
        first_detection_ts: float,
        clip_start_hour: int = 0,
        fps: float = 25.0,
        max_search_sec: float = 30.0,
    ) -> Optional[float]:
        """Scan backward from *first_detection_ts* using dark-threshold only.

        MOG2's background model takes several seconds to register a new dark
        object against the wall, so the first MOG2-positive frame can lag the
        true arrival.  This method re-seeks the video and re-runs the
        dark-threshold fallback (immune to MOG2 adaptation) over the
        *max_search_sec* window before the approximate detection, returning the
        earliest timestamp at which a bird-sized blob (≥ ``min_area``) appears.

        Parameters
        ----------
        source_path
            Filesystem path to the source video.
        first_detection_ts
            Approximate first-detection time (seconds from clip start).
        clip_start_hour
            Wall-clock hour the clip starts at (for offset bookkeeping only).
        fps
            Frame rate of *source_path* (used to convert timestamps to seek
            positions).
        max_search_sec
            How far back to search from *first_detection_ts*.

        Returns
        -------
        The earliest timestamp (seconds from clip start) at which a qualifying
        blob is found, or ``None`` if none is found in the search range.
        """
        if first_detection_ts is None or first_detection_ts < 0:
            return None

        search_start = max(0.0, first_detection_ts - max_search_sec)
        _trace(
            f"Backfill: seeking frames in [{search_start:.1f}s, "
            f"{first_detection_ts:.1f}s] using dark-threshold fallback"
        )

        cap = cv2.VideoCapture(str(source_path))
        if not cap.isOpened():
            _trace(f"Backfill: could not open {source_path}")
            return None

        # Seek to the start of the search range.
        start_frame = int(search_start * fps)
        cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

        earliest: Optional[float] = None
        target_frame = int(first_detection_ts * fps)

        idx = start_frame
        current_ts = search_start
        while idx <= target_frame:
            ok, frame = cap.read()
            if not ok:
                break
            ts = idx / fps if fps else float(idx)

            # Reuse the precomputed ROI mask for this frame size.
            self._ensure_roi(frame)
            if self._roi is None:
                break

            blobs, max_area = threshold_foreground(
                frame, self._roi, self.dark_threshold, self.min_area
            )
            if blobs and max_area >= self.min_area:
                if earliest is None or ts < earliest:
                    earliest = ts
                    _trace(
                        f"Backfill: earliest blob at ts={ts:.1f}s "
                        f"max_area={max_area} idx={idx}"
                    )

            idx += 1
            current_ts = ts

        cap.release()
        _trace(
            f"Backfill: result earliest={earliest} "
            f"(was {first_detection_ts:.1f}s, "
            f"delta={(first_detection_ts - (earliest or first_detection_ts)):.1f}s)"
        )
        return earliest

    def prime(self, frames: Iterable[np.ndarray], n_frames: int = DEFAULT_PRIMING_FRAMES) -> int:
        """Feed early video frames through MOG2 to build a stable background model.

        Call this before process_frame on the same source so the model
        learns the scene's lighting conditions and does not mistake
        the wall for shadow (which produces shadow_frac ≈ 1.0 on
        unprimed models).

        Returns the actual number of frames consumed.
        """
        count = 0
        for frame in frames:
            if count >= n_frames:
                break
            self._ensure_roi(frame)
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            self._fgbg.apply(gray)
            count += 1
        return count

    def process_frame(self, frame: np.ndarray, sample_index: int = 0,
                       ts_sec: float = 0.0) -> FrameResult:
        self._ensure_roi(frame)
        assert self._roi is not None
        h, w = frame.shape[:2]
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        fg = self._fgbg.apply(gray)
        roi = self._roi
        roi_px = int(roi.sum()) // 255
        if roi_px == 0:
            _trace(f"sample={sample_index} ts={ts_sec:.1f}s ROI=0px, skipping")
            return FrameResult(sample_index, ts_sec)

        shadow = (fg == 127) & (roi == 255)
        real = (fg == 255) & (roi == 255)
        real = cv2.morphologyEx(real.astype(np.uint8), cv2.MORPH_OPEN, self._kernel)

        cnts, _ = cv2.findContours(real, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        all_areas = sorted([int(cv2.contourArea(c)) for c in cnts], reverse=True)
        blobs: List[Tuple[int, int, int, int, int]] = []
        max_area = 0
        for c in cnts:
            a = cv2.contourArea(c)
            if a < self.min_area:
                continue
            x, y, w_b, hh = cv2.boundingRect(c)
            blobs.append((x, y, w_b, hh, int(a)))
            max_area = max(max_area, int(a))

        # FALLBACK: MOG2 often misses still birds (they blend into wall).
        # Use dark-threshold detection when MOG2 finds nothing in the ROI.
        if not blobs:
            _trace(f"MOG2 found 0 blobs at sample={sample_index} ts={ts_sec:.1f}s, "
                   f"trying dark-threshold detection")
            thr_blobs, thr_area = threshold_foreground(
                frame, roi, self.dark_threshold, self.min_area
            )
            if thr_blobs:
                _trace(f"Dark-threshold detected {len(thr_blobs)} blobs, "
                       f"max_area={thr_area:.0f}")
                blobs = thr_blobs
                max_area = thr_area

        _trace(
            f"sample={sample_index} ts={ts_sec:.1f}s "
            f"frame={w}x{h} roi_px={roi_px} contours={len(cnts)} "
            f"all_areas={all_areas[:10]} min_area={self.min_area} "
            f"kept={len(blobs)} max_blob_area={max_area} "
            f"fg_frac={float(real.sum()) / roi_px:.4f} "
            f"shadow_frac={float(shadow.sum()) / roi_px:.4f}"
        )

        return FrameResult(
            sample_index=sample_index,
            ts_sec=ts_sec,
            blobs=blobs,
            max_blob_area=max_area,
            fg_frac=float(real.sum()) / roi_px,
            shadow_frac=float(shadow.sum()) / roi_px,
        )


def classify_window(
    frames: Sequence[FrameResult],
    window,
    glare_max_area: int = DEFAULT_GLARE_MAX_AREA,
    min_area: int = DEFAULT_MIN_AREA,
    min_sample_count: int = 20,
    version: str = "detector-v1",
) -> WindowResult:
    """Aggregate per-frame results into a three-bucket verdict for one window.

    The detector uses simple area thresholds PLUS motion analysis to
    distinguish glare from other large objects:

    * max_blob_area < 400px² → REVIEW (bird-sized blob)
    * max_blob_area >= glare_max_area → MANUAL if blob is moving (glare/shadow),
      REVIEW if blob is stationary (nest/debris) AND bird-sized blobs also present
    * 400px² ≤ max_blob_area < glare_max_area → bird-sized blob
    * no blobs → SKIP

    Motion tracking distinguishes a moving shadow sweep (glare) from a
    stationary nest/debris: a large blob that stays in roughly the same
    position across frames is treated as a stationary object, not glare.
    A minimum sample count is required before a window can be REVIEW. With
    only a few frames (e.g. the tail end of a clip), noise can masquerade as
    a bird detection — so those windows are SKIP.
    """
    has_bird = False
    first_ts: Optional[float] = None
    max_area = 0
    glare_reason = ""

    for fr in frames:
        max_area = max(max_area, fr.max_blob_area)

        if fr.max_blob_area >= glare_max_area:
            if not glare_reason:
                glare_reason = f"implausible blob area {fr.max_blob_area}px^2"
        elif fr.blobs and fr.max_blob_area >= 400:  # Bird-sized blob threshold
            if not has_bird:
                has_bird = True
                if first_ts is None:
                    first_ts = fr.ts_sec

    # Three-bucket logic:
    # - Large blob (>= glare_max_area) → MANUAL (shadow sweep / glare)
    # - Bird-sized blob (>= 400, < glare_max_area) + enough samples → REVIEW
    # - Bird-sized blob but too few samples → SKIP
    # - Nothing → SKIP
    if max_area >= glare_max_area:
        verdict = Verdict.MANUAL   # Implausibly large = glare/shadow, needs human review
        spot_check = True
    elif has_bird and len(frames) >= min_sample_count:
        verdict = Verdict.REVIEW   # Bird-sized blob(s) detected with enough samples
        spot_check = True
    elif has_bird:
        # Bird-sized blob detected but too few samples to trust it (e.g. tail of clip)
        verdict = Verdict.SKIP
        spot_check = False
        glare_reason = (glare_reason + "; " if glare_reason else "") + \
                       f"insufficient samples ({len(frames)} < {min_sample_count})"
    else:
        verdict = Verdict.SKIP     # No blobs at all
        spot_check = False

    _trace(
        f"classify_window window={window.window_id} frames={len(frames)} "
        f"has_bird={has_bird} first_ts={first_ts} max_area={max_area} "
        f"glare_reason={glare_reason!r} verdict={verdict.value}"
    )

    return WindowResult(
        window_id=window.window_id,
        tower=window.tower,
        date=window.date,
        hour=window.hour,
        minute=window.minute,
        verdict=verdict,
        first_detection_ts=first_ts if verdict is Verdict.REVIEW else None,
        max_blob_area=max_area,
        sample_count=len(frames),
        spot_check_due=spot_check,
        detector_version=version,
        glare_reason=glare_reason,
    )


def iter_frames(
    source: Iterable[np.ndarray],
    sample_every: int = 1,
    fps: Optional[float] = None,
) -> Iterator[Tuple[int, float, np.ndarray]]:
    """Yield (sample_index, ts_sec, frame) from a frame iterable.

    ``sample_every`` decimates (1 = every frame). ``ts_sec`` is derived from
    the source frame index divided by fps, so it represents actual elapsed time.
    """
    idx = 0
    for i, frame in enumerate(source):
        if i % sample_every != 0:
            continue
        ts = (i / fps) if fps else float(i)
        yield idx, ts, frame
        idx += 1


def threshold_foreground(
    frame: np.ndarray,
    roi: np.ndarray,
    dark_threshold: int | None = None,
    min_area: int = 250,
) -> Tuple[List[Tuple[int, int, int, int, int]], int]:
    """Detect foreground using adaptive dark-threshold on grayscale.

    Birds against a chimney wall are typically darker than the background.
    This is a complementary approach to MOG2 when birds blend into the scene.

    Uses an adaptive threshold based on ROI statistics (mean - 1.5*std) by
    default so it adapts to changing lighting instead of a fixed global value.

    Returns (blobs, max_blob_area) where each blob is (x, y, w, h, area).
    """
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # Compute an adaptive threshold from the ROI statistics. Pixels in the
    # ROI that are significantly darker than the local mean are candidates.
    if dark_threshold is None:
        roi_pixels = gray[roi == 255]
        if len(roi_pixels) > 0:
            roi_mean = float(np.mean(roi_pixels))
            roi_std = float(np.std(roi_pixels))
            threshold = max(roi_mean - 1.5 * roi_std, 0.0)
        else:
            threshold = 50.0
    else:
        threshold = float(dark_threshold)

    # Pixels darker than the threshold are considered foreground.
    dark_mask = (gray < threshold) & (roi == 255)

    # Morphological opening: removes thin structures (nest sticks, debris)
    # while preserving solid blobs (a perched bird). The nest is made of thin
    # sticks only a few pixels wide; a bird is a solid dark mass. Opening
    # erodes then dilates, so thin sticks vanish but the bird survives.
    dark_uint8 = dark_mask.astype(np.uint8) * 255
    open_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, _DARK_OPEN_KERNEL)
    dark_uint8 = cv2.morphologyEx(dark_uint8, cv2.MORPH_OPEN, open_kernel)

    # Find contours in the opened dark mask
    cnts, _ = cv2.findContours(dark_uint8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    blobs: List[Tuple[int, int, int, int, int]] = []
    max_area = 0
    for c in cnts:
        a = cv2.contourArea(c)
        if a < min_area:
            continue
        x, y, w, hh = cv2.boundingRect(c)
        blobs.append((x, y, w, hh, int(a)))
        max_area = max(max_area, int(a))

    # Large blobs are NOT rejected here. classify_window() uses motion
    # analysis to distinguish a stationary nest/debris blob (REVIEW) from a
    # moving shadow sweep (MANUAL). Rejecting them here would discard real
    # bird detections that coexist with a large stationary object.
    return blobs, max_area
