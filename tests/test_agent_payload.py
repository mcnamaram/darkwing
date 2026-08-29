"""Tests for MVP3 Phase 1 payload extraction (agent_payload.py)."""
from __future__ import annotations

import tempfile
from pathlib import Path

import cv2
import numpy as np
import pytest

from darkwing.agent_payload import (
    DEFAULT_MAX_FRAMES,
    _candidate_ts,
    _downsample,
    _first_motion_ts,
    _merge_intervals,
    extract_motion_frames,
)
from darkwing.detector import FrameResult


# ── pure helper tests ────────────────────────────────────────────────────────

def test_first_motion_ts_picks_earliest_blob():
    frs = [
        FrameResult(0, 0.0, blobs=[]),
        FrameResult(5, 5.0, blobs=[(1, 1, 2, 2, 300)]),
        FrameResult(3, 3.0, blobs=[(1, 1, 2, 2, 300)]),
    ]
    assert _first_motion_ts(frs) == 3.0


def test_first_motion_ts_none_when_empty():
    assert _first_motion_ts([FrameResult(0, 0.0)]) is None


def test_merge_intervals_overlap_and_gap():
    assert _merge_intervals([(0, 2), (1, 3)]) == [(0.0, 3.0)]
    assert _merge_intervals([(0, 2), (4, 6)]) == [(0.0, 2.0), (4.0, 6.0)]


def test_merge_intervals_contiguous():
    # c <= b joins (touching boundary)
    assert _merge_intervals([(0, 2), (2, 4)]) == [(0.0, 4.0)]


def test_candidate_ts_one_fps_inclusive():
    assert _candidate_ts([(1.0, 3.0)]) == [1.0, 2.0, 3.0]


def test_candidate_ts_clamps_negative_start():
    assert _candidate_ts([(-1.5, 1.5)]) == [0.0, 1.0]


def test_downsample_keeps_all_under_cap():
    ts = [float(i) for i in range(10)]
    assert _downsample(ts, 15) == ts


def test_downsample_spreads_across_range():
    ts = [float(i) for i in range(30)]
    sel = _downsample(ts, 3)
    assert len(sel) == 3
    # first and last picked are spread across the list (stride ~10)
    assert sel[0] == 0.0
    assert sel[1] > 9.0 and sel[1] < 11.0
    assert sel[-1] > 19.0 and sel[-1] < 21.0


# ── end-to-end extraction against a synthetic clip ──────────────────────────

def _write_clip(path: Path, w=320, h=180, n=300, fps=25.0, blob_frames=()) -> float:
    """Write an avi (MJPG) of a grey wall with a black dot on blob_frames.

    mp4v cannot encode on this OpenCV build; MJPG/avi is portable for tests.
    """
    fourcc = cv2.VideoWriter_fourcc(*"MJPG")  # type: ignore[attr-defined]
    vw = cv2.VideoWriter(str(path), fourcc, fps, (w, h))
    base = np.full((h, w, 3), 60, np.uint8)
    for i in range(n):
        frame = base.copy()
        if i in blob_frames:
            cv2.circle(frame, (w // 2, h // 2), 8, (0, 0, 0), -1)
        vw.write(frame)
    vw.release()
    return fps


def _frame_results(n=300, fps=25.0, motion_idx=()):
    out = []
    for i in range(n):
        blobs = [(10, 10, 16, 16, 300)] if i in motion_idx else []
        out.append(FrameResult(i, i / fps, blobs=blobs))
    return out


def test_extract_returns_frames_within_span():
    with tempfile.TemporaryDirectory() as d:
        clip = Path(d) / "c.avi"
        fps = _write_clip(clip, n=300, fps=25.0, blob_frames=range(25, 40))
        # motion at frames 25..39 -> ts 1.0..1.56
        frs = _frame_results(n=300, fps=25.0, motion_idx=range(25, 40))
        payload = extract_motion_frames(
            clip, frs, fps=fps, first_detection_ts=1.0, max_frames=DEFAULT_MAX_FRAMES
        )
        # span is [1.0, 61.0]; only 1s of frames exist near ts 1.0..1.56
        assert 1 <= len(payload) <= DEFAULT_MAX_FRAMES
        for buf in payload:
            assert buf[:2] == b"\xff\xd8"  # JPEG SOI marker


def test_extract_ignores_motion_outside_span():
    with tempfile.TemporaryDirectory() as d:
        clip = Path(d) / "c.avi"
        fps = _write_clip(clip, n=3000, fps=25.0, blob_frames=range(2000, 2010))
        # only later motion (ts 80+); span starts at first_detection_ts=1.0
        frs = _frame_results(n=3000, fps=25.0, motion_idx=range(2000, 2010))
        payload = extract_motion_frames(
            clip, frs, fps=fps, first_detection_ts=1.0, max_frames=DEFAULT_MAX_FRAMES
        )
        # no motion within [1.0, 61.0] -> empty
        assert payload == []


def test_extract_empty_when_no_motion():
    with tempfile.TemporaryDirectory() as d:
        clip = Path(d) / "c.avi"
        fps = _write_clip(clip, n=300, fps=25.0)
        frs = _frame_results(n=300, fps=25.0)  # no blobs
        assert extract_motion_frames(clip, frs, fps=fps) == []


def test_extract_downscales_width():
    with tempfile.TemporaryDirectory() as d:
        clip = Path(d) / "c.avi"
        fps = _write_clip(clip, w=1280, h=720, n=300, fps=25.0, blob_frames=range(25, 40))
        frs = _frame_results(n=300, fps=25.0, motion_idx=range(25, 40))
        payload = extract_motion_frames(
            clip, frs, fps=fps, first_detection_ts=1.0, target_width=320
        )
        assert payload
        arr = np.frombuffer(payload[0], np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        assert img is not None
        assert img.shape[1] == 320
        assert img.shape[0] == 180  # aspect preserved (720/1280*320)
