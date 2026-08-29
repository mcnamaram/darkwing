"""MVP3 Phase 1: extract keyframe payloads from REVIEW windows for the VLM agent.

Given the per-frame detection results for one observation window, pull a
frugal set of JPEG keyframes from the source video covering the observation
span, so the agent has visual evidence without paying to upload whole clips.

Requirements satisfied (see canonical-ai-agent-integration.md):
  REQ-2 frame budget cap (max_frames)
  REQ-3 +/-2s temporal padding around motion
  REQ-4 downscale to target_width, aspect preserved
  REQ-7 60-second observation span starting at first_detection_ts
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import List, Optional, Tuple

import cv2
import numpy as np

from darkwing.detector import FrameResult
from darkwing.frames import LocalVideoSource

OBSERVATION_SPAN_SEC = 60.0   # REQ-7: 1-minute observation from first detection
PAD_SEC = 2.0                 # REQ-3: padding before/after each motion frame
DEFAULT_MAX_FRAMES = 15       # REQ-2: payload frame cap per window
DEFAULT_TARGET_WIDTH = 640    # REQ-4: downscale width
JPEG_QUALITY = 80


def _first_motion_ts(frame_results: List[FrameResult]) -> Optional[float]:
    """Earliest ts_sec carrying a non-empty blob list, else None."""
    ts = [fr.ts_sec for fr in frame_results if fr.blobs]
    return min(ts) if ts else None


def _merge_intervals(intervals: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
    """Union-merge sorted (start,end) intervals; contiguous/overlapping join."""
    if not intervals:
        return []
    merged: List[List[float]] = [list(sorted(intervals)[0])]
    for a, b in sorted(intervals)[1:]:
        if a <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    return [(float(a), float(b)) for a, b in merged]


def _candidate_ts(episodes: List[Tuple[float, float]]) -> List[float]:
    """1 FPS timestamps inside each episode, clamped to >= 0, sorted."""
    out: List[float] = []
    for start, end in episodes:
        t = max(0.0, math.ceil(start))
        while t <= end:
            out.append(t)
            t += 1.0
    return sorted(out)


def _downsample(ts_list: List[float], max_frames: int) -> List[float]:
    """Spread-select at most ``max_frames`` timestamps across ``ts_list``."""
    if len(ts_list) <= max_frames:
        return ts_list
    step = len(ts_list) / max_frames
    return [ts_list[int(i * step)] for i in range(max_frames)]


def extract_motion_frames(
    source_path: Path,
    frame_results: List[FrameResult],
    fps: float,
    first_detection_ts: Optional[float] = None,
    max_frames: int = DEFAULT_MAX_FRAMES,
    target_width: int = DEFAULT_TARGET_WIDTH,
) -> List[bytes]:
    """Extract JPEG keyframe payload for a REVIEW window's observation span.

    Returns JPEG-encoded frame buffers (bytes), downscaled to ``target_width``
    preserving aspect ratio, ordered by timestamp. Empty list when there is no
    motion to extract.
    """
    if fps is None or fps <= 0:
        return []

    start_ts = (
        first_detection_ts
        if first_detection_ts is not None
        else _first_motion_ts(frame_results)
    )
    if start_ts is None:
        return []

    span_end = start_ts + OBSERVATION_SPAN_SEC

    # Step A: motion episodes inside the 60s span, padded +/-2s, union-merged.
    intervals: List[Tuple[float, float]] = []
    for fr in frame_results:
        if not fr.blobs:
            continue
        if not (start_ts <= fr.ts_sec <= span_end):
            continue
        intervals.append((fr.ts_sec - PAD_SEC, fr.ts_sec + PAD_SEC))
    episodes = _merge_intervals(intervals)
    if not episodes:
        return []

    # Step B/C: 1 FPS candidates, downsampled to the frame budget.
    candidates = _candidate_ts(episodes)
    targets = _downsample(candidates, max_frames)
    target_indices = {int(round(t * fps)) for t in targets}
    if not target_indices:
        return []

    # Step D: single sequential read pass; extract + downscale + encode.
    src = LocalVideoSource(source_path)
    out: List[bytes] = []
    try:
        for idx, frame in enumerate(src.frames()):
            if idx in target_indices:
                h, w = frame.shape[:2]
                scale = target_width / w
                new_size = (target_width, max(1, int(round(h * scale))))
                small = cv2.resize(frame, new_size, interpolation=cv2.INTER_AREA)
                ok_enc, buf = cv2.imencode(
                    ".jpg", small, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY]
                )
                if ok_enc:
                    out.append(buf.tobytes())
                target_indices.discard(idx)
                if not target_indices:
                    break
    finally:
        src.close()
    return out
