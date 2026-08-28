"""Pure detector tests — synthetic frames, zero hardware (plan R7)."""
from __future__ import annotations

import numpy as np
import pytest

from darkwing.detector import (
    Detector,
    Verdict,
    classify_window,
    iter_frames,
)
from darkwing.windows import WindowId


def _frame(h=180, w=320, val=60):
    return np.full((h, w, 3), val, np.uint8)


def test_skip_on_static_scene():
    d = Detector()
    frames = [d.process_frame(_frame(), i) for i in range(60)]
    w = WindowId(tower=3, date="06/15/2026", hour=6, minute=0)
    res = classify_window(frames, w, glare_hours=())
    assert res.verdict is Verdict.SKIP
    assert res.first_detection_ts is None
    assert res.spot_check_due is False


def test_review_on_moving_blob():
    d = Detector()
    frames = []
    for i in range(60):
        f = _frame()
        if i >= 10:  # let background settle, then introduce a bird-sized blob
            cx = int(60 + (i - 10) * 3)
            cv2_circle(f, cx, 90, 12, 0)  # r=12 -> ~452px^2 > min_area
        frames.append(d.process_frame(f, i, float(i)))
    w = WindowId(tower=3, date="06/15/2026", hour=7, minute=0)
    res = classify_window(frames, w, glare_hours=())
    assert res.verdict is Verdict.REVIEW
    assert res.first_detection_ts is not None
    assert res.spot_check_due is True


def test_manual_on_glare_hour():
    d = Detector()
    frames = [d.process_frame(_frame(), i) for i in range(60)]  # static, no birds
    w = WindowId(tower=3, date="06/15/2026", hour=12, minute=0)
    res = classify_window(frames, w)  # default glare hours include 12
    assert res.verdict is Verdict.MANUAL
    assert "glare hour" in res.glare_reason
    assert res.spot_check_due is True


def test_manual_on_implausible_blob():
    d = Detector()
    frames = []
    for i in range(60):
        f = _frame()
        if i == 10:
            # huge white rectangle -> max_blob_area > glare_max_area
            f[10:170, 10:310] = 220
        frames.append(d.process_frame(f, i, float(i)))
    w = WindowId(tower=3, date="06/15/2026", hour=7, minute=0)
    res = classify_window(frames, w, glare_hours=())  # not a configured glare hour
    assert res.verdict is Verdict.MANUAL
    assert "implausible" in res.glare_reason


def test_iter_frames_decimates_and_timestamps():
    fake = (_frame() for _ in range(100))
    out = list(iter_frames(fake, sample_every=10, fps=25.0))
    assert len(out) == 10
    idx, ts, fr = out[1]
    assert idx == 1
    assert abs(ts - (1 / 25.0)) < 1e-6  # 1 sample @ 25fps = 0.04s


def test_roi_excludes_border_blob():
    """A blob only in the excluded ROI border should not count as foreground."""
    d = Detector()
    f = _frame()
    f[5:15, 5:15] = 0  # top-left corner, outside ROI (x0=0.18)
    fr = d.process_frame(f, 0)
    assert fr.max_blob_area == 0  # MOG2 may flag edge but ROI crops it


def cv2_circle(frame, cx, cy, r, color):
    import cv2
    cv2.circle(frame, (cx, cy), r, color, -1)
