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
from dataclasses import dataclass, field
from typing import Iterable, Iterator, List, Optional, Sequence, Tuple

import cv2
import numpy as np


class Verdict(str, enum.Enum):
    SKIP = "skip"
    REVIEW = "review"
    MANUAL = "manual"


# Defaults derived from the spike. All versioned in output (plan R4).
DEFAULT_ROI = (0.18, 0.82, 0.05, 0.92)   # x0, x1, y0, y1 as fractions of frame
DEFAULT_MIN_AREA = 250                    # px^2; a swift against the wall
DEFAULT_GLARE_MAX_AREA = 6000             # px^2; above this a blob is implausibly
                                          # large for a bird at 640x360 -> glare
DEFAULT_MORPH_KERNEL = (5, 5)
DEFAULT_GLARE_HOURS: Tuple[int, ...] = (11, 12, 13)  # noon shadow window


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
    mask = np.zeros((h, w), np.uint8)
    mask[int(y0 * h):int(y1 * h), int(x0 * w):int(x1 * w)] = 255
    return mask


class Detector:
    """Stateful MOG2 background subtractor over an ROI.

    Feed frames sequentially via :meth:`process_frame`. The background model
    is continuous across the whole clip (not reset per window) so it stays
    stable. Sample decimation is the caller's responsibility.
    """

    def __init__(
        self,
        roi: Sequence[float] = DEFAULT_ROI,
        min_area: int = DEFAULT_MIN_AREA,
        glare_max_area: int = DEFAULT_GLARE_MAX_AREA,
        morph_kernel: Tuple[int, int] = DEFAULT_MORPH_KERNEL,
        history: int = 500,
        var_threshold: int = 16,
    ) -> None:
        self.roi_frac = tuple(roi)
        self.min_area = min_area
        self.glare_max_area = glare_max_area
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
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        fg = self._fgbg.apply(gray)
        roi = self._roi
        roi_px = int(roi.sum()) // 255
        if roi_px == 0:
            return FrameResult(sample_index, ts_sec)

        shadow = (fg == 127) & (roi == 255)
        real = (fg == 255) & (roi == 255)
        real = cv2.morphologyEx(real.astype(np.uint8), cv2.MORPH_OPEN, self._kernel)

        cnts, _ = cv2.findContours(real, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        blobs: List[Tuple[int, int, int, int, int]] = []
        max_area = 0
        for c in cnts:
            a = cv2.contourArea(c)
            if a < self.min_area:
                continue
            x, y, w, hh = cv2.boundingRect(c)
            blobs.append((x, y, w, hh, int(a)))
            max_area = max(max_area, int(a))

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
    glare_hours: Sequence[int] = DEFAULT_GLARE_HOURS,
    glare_max_area: int = DEFAULT_GLARE_MAX_AREA,
    version: str = "detector-v1",
) -> WindowResult:
    """Aggregate per-frame results into a three-bucket verdict for one window."""
    has_bird = False
    first_ts: Optional[float] = None
    max_area = 0
    glare_reason = ""

    if window.hour in set(glare_hours):
        glare_reason = f"configured glare hour {window.hour}"

    for fr in frames:
        max_area = max(max_area, fr.max_blob_area)
        if fr.max_blob_area >= glare_max_area and not glare_reason:
            glare_reason = f"implausible blob area {fr.max_blob_area}px^2"
        if fr.blobs and not has_bird:
            has_bird = True
            if first_ts is None:
                first_ts = fr.ts_sec

    if glare_reason:
        verdict = Verdict.MANUAL
        spot_check = True
    elif has_bird:
        verdict = Verdict.REVIEW
        spot_check = True
    else:
        verdict = Verdict.SKIP
        spot_check = False  # SKIP spot-check handled by caller sampling

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
    ``sample_index`` when ``fps`` is given, else from a monotonic counter.
    """
    idx = 0
    for i, frame in enumerate(source):
        if i % sample_every != 0:
            continue
        ts = (idx / fps) if fps else float(idx)
        yield idx, ts, frame
        idx += 1
