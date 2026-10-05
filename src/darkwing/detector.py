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
  MANUAL  - glare/unstable lighting           -> detector UNRELIABLE; whole
            (configured glare hours OR implausibly large blob)     window must
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
DEFAULT_MIN_AREA = 250                    # px^2; a swift against the wall
DEFAULT_GLARE_MAX_AREA = 6000             # px^2; above this a blob is implausibly
                                          # large for a bird at 640x360 -> glare
DEFAULT_MORPH_KERNEL = (5, 5)


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
        dark_threshold: int = 85,
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
                   f"trying dark-threshold detection (threshold={self.dark_threshold})")
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
    min_sample_count: int = 20,
    version: str = "detector-v1",
) -> WindowResult:
    """Aggregate per-frame results into a three-bucket verdict for one window.

    The detector uses simple area thresholds:

    * max_blob_area < BIRD_MAX_AREA (≈400px²) → REVIEW (bird-sized blob)
    * max_blob_area >= glare_max_area (≥6000px²) → MANUAL (implausible blob = glare/shadow)
    * 400px² ≤ max_blob_area < 6000px² → MANUAL (ambiguous, could be noise or tiny bird)
    * no blobs → SKIP

    A minimum sample count is required before a window can be REVIEW. With
    only a few frames (e.g. the tail end of a clip), noise can masquerade as
    a bird detection — so those windows are SKIP.

    These thresholds work for both glare and non-glare conditions because
    glare produces reliably large blobs that exceed the MANUAL threshold.
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

    # Three-bucket logic based on max blob area observed
    if max_area >= glare_max_area:
        verdict = Verdict.MANUAL  # Implausibly large = glare/shadow, needs human review
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
    dark_threshold: int = 50,
    min_area: int = 250,
    max_lighting_blob_area: int = 10000,
) -> Tuple[List[Tuple[int, int, int, int, int]], int]:
    """Detect foreground using simple dark-threshold on grayscale.

    Birds against a chimney wall are typically darker than the background.
    This is a complementary approach to MOG2 when birds blend into the scene.

    Returns (blobs, max_blob_area) where each blob is (x, y, w, h, area).
    """
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    # Pixels darker than the threshold are considered foreground
    dark_mask = (gray < dark_threshold) & (roi == 255)

    # Find contours in the dark mask
    dark_uint8 = dark_mask.astype(np.uint8) * 255
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

    # If any single blob is implausibly large (> max_lighting_blob_area),
    # it's likely a lighting change (shadow/sun on wall), not birds.
    # Reject all blobs for this frame to avoid false positive glare/MANUAL.
    if any(b[4] > max_lighting_blob_area for b in blobs):
        _trace(
            f"threshold_foreground: rejecting frame due to implausibly large "
            f"blob(s), max_area={max(b[4] for b in blobs)}, "
            f"threshold={max_lighting_blob_area}"
        )
        return [], 0

    return blobs, max_area
