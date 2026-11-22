#!/usr/bin/env python3
"""Evaluate VLM on the 9 residual-error windows (3 FNs + 6 FPs).

Runs the classical detector on each residual window, then applies VLM:
- Phase 0: SKIP→REVIEW promotion (for the 3 FN windows)
- Phase 1: REVIEW/MANUAL→SKIP demotion (for the 6 FP windows)

Compares VLM-assisted verdicts to oracle for each residual window.

Usage:
    VLM_PROVIDER=ollama python scripts/evaluate_vlm_residuals.py
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2

from darkwing import detector as det_mod
from darkwing.detector import Detector, classify_window
from darkwing.windows import WindowId
from darkwing import agent_payload
from darkwing.agent import vlm_client_adapter

VALIDATION_ROOT = Path("footage/validation")
VIDEO_ROOT = Path(".hermes/nvr-videos")

HOUR_TO_VIDEO = {
    8:  "NVR-2-Stormy Oaks Chimney Swift T3-1-20260615075956-20260615090000.mp4",
    9:  "NVR-2-Stormy Oaks Chimney Swift T3-1-20260615090000-20260615095959.mp4",
    10: "NVR-2-Stormy Oaks Chimney Swift T3-1-20260615095959-20260615105459.mp4",
    11: "NVR-2-Stormy Oaks Chimney Swift T3-1-20260615105959-20260615115957.mp4",
    13: "NVR-2-Stormy Oaks Chimney Swift T3-1-20260615125957-20260615135957.mp4",
    14: "NVR-2-Stormy Oaks Chimney Swift T3-1-20260615135957-20260615150000.mp4",
    15: "NVR-2-Stormy Oaks Chimney Swift T3-1-20260615150000-20260615160001.mp4",
    16: "NVR-2-Stormy Oaks Chimney Swift T3-1-20260615160001-20260615165957.mp4",
    17: "NVR-2-Stormy Oaks Chimney Swift T3-1-20260615165957-20260615175959.mp4",
    18: "NVR-2-Stormy Oaks Chimney Swift T3-1-20260615175959-20260615185957.mp4",
    19: "NVR-2-Stormy Oaks Chimney Swift T3-1-20260615185957-20260615195957.mp4",
    20: "NVR-2-Stormy Oaks Chimney Swift T3-1-20260615195957-20260615205956.mp4",
    21: "NVR-2-Stormy Oaks Chimney Swift T3-1-20260615205956-20260615215959.mp4",
}

# Residual-error windows from the classical baseline
RESIDUAL_WINDOWS = [
    # False Negatives (oracle=REVIEW, classical=SKIP)
    ("v1", 8, 0, "FN"),
    ("v1", 8, 20, "FN"),
    ("v13", 21, 0, "FN"),
    # False Positives (oracle=SKIP, classical=REVIEW/MANUAL)
    ("v2", 9, 20, "FP"),
    ("v7", 15, 0, "FP"),
    ("v8", 16, 20, "FP"),
    ("v9", 17, 0, "FP"),
    ("v9", 17, 20, "FP"),
    ("v9", 17, 40, "FP"),
]

OBSERVATION_SPAN_SEC = 60
WINDOW_CUTOFF_SEC = 1140
VLM_PROMOTE_CONFIDENCE = float(os.environ.get("VLM_CONFIDENCE_THRESHOLD", "0.6"))
VLM_DEMOTION_CONFIDENCE = float(os.environ.get("VLM_DEMOTION_CONFIDENCE", "0.8"))


def _filename_start(name: str):
    for p in name.split("-"):
        if len(p) == 14 and p.isdigit():
            return int(p[8:10]), int(p[10:12]), int(p[12:14])
    return 0, 0, 0


def _run_window(video_path: Path, start_epoch: int, hour: int, minute: int):
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return None
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    sample_every = max(1, int(round(fps / 2)))
    d = Detector()
    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
    for _ in range(int(fps * 30)):
        ok, f = cap.read()
        if not ok:
            break
        d._ensure_roi(f)
        d._fgbg.apply(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY))

    window_start_epoch = hour * 3600 + minute * 60
    target_ts = window_start_epoch - start_epoch
    seek = max(0, int(target_ts * fps) - int(30 * fps))
    cap.set(cv2.CAP_PROP_POS_FRAMES, seek)
    frame_idx = seek
    sample_idx = 0
    collected: List = []
    bird_first = None
    span_end = None

    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if frame_idx % sample_every != 0:
            frame_idx += 1
            continue
        ts = frame_idx / fps
        wall = start_epoch + ts
        wh = int(wall // 3600)
        mm = int(((wall % 3600) // 60 // 20) * 20)
        if wh != hour or mm != minute:
            frame_idx += 1
            continue
        siw = wall - window_start_epoch
        if siw > WINDOW_CUTOFF_SEC:
            break
        if bird_first is None:
            fr = d.process_frame(frame, sample_idx, siw)
            if fr.blobs and fr.max_blob_area >= 400:
                bird_first = siw
                span_end = siw + OBSERVATION_SPAN_SEC
                collected.append(fr)
        else:
            if siw < span_end:
                collected.append(d.process_frame(frame, sample_idx, siw))
            else:
                break
        sample_idx += 1
        frame_idx += 1
    cap.release()
    return fps, collected, bird_first


def _load_oracle(version: str) -> Dict[tuple, str]:
    path = VALIDATION_ROOT / version / "06" / "15" / "2026" / "tower3" / "review_index_oracle.jsonl"
    out: Dict[tuple, str] = {}
    if not path.exists():
        return out
    for line in path.read_text().splitlines():
        if line.strip():
            r = json.loads(line)
            out[(r["hour"], r["minute"])] = r["verdict"].lower()
    return out


async def _vlm_detect_bird(frames: List, source_path: Path, fps: float,
                           first_detection_ts: float) -> Optional[Tuple[bool, float]]:
    frames_to_send = agent_payload.extract_motion_frames(
        source_path, frames, fps=fps,
        first_detection_ts=first_detection_ts,
        span_sec=60.0, max_frames=3,
    )
    if not frames_to_send:
        return None
    ctx = {"source": "residual_eval", "max_blob_area": max((fr.max_blob_area for fr in frames), default=0)}
    try:
        bird_present, confidence = await vlm_client_adapter.detect_bird(frames_to_send, ctx)
        return bool(bird_present), float(confidence)
    except Exception as exc:
        print(f"      [VLM ERROR] {exc}")
        return None


async def _apply_phases(collected: List, verdict_str: str, source_path: Path,
                        fps: float, bird_first: Optional[float]) -> Tuple[str, str]:
    verdict = verdict_str
    has_blobs = any(fr.blobs for fr in collected)
    if not has_blobs:
        return verdict, "none(no blobs)"

    first_ts = bird_first
    if first_ts is None:
        first_ts = min((fr.ts_sec for fr in collected if fr.blobs), default=0.0)

    if verdict == "skip":
        result = await _vlm_detect_bird(collected, source_path, fps, first_ts)
        if result is not None:
            bird_present, confidence = result
            if bird_present and confidence >= VLM_PROMOTE_CONFIDENCE:
                return "review", f"promote({confidence:.2f})"
            return verdict, f"none(bird_present={bird_present}, conf={confidence:.2f})"
        return verdict, "none(error)"

    if verdict in ("review", "manual"):
        result = await _vlm_detect_bird(collected, source_path, fps, first_ts)
        if result is not None:
            bird_present, confidence = result
            if not bird_present and confidence >= VLM_DEMOTION_CONFIDENCE:
                return "skip", f"demote({confidence:.2f})"
            return verdict, f"none(bird_present={bird_present}, conf={confidence:.2f})"
        return verdict, "none(error)"

    return verdict, "none"


async def main() -> None:
    for version, hour, minute, error_type in RESIDUAL_WINDOWS:
        oracle_file = VALIDATION_ROOT / version / "06" / "15" / "2026" / "tower3" / "review_index_oracle.jsonl"
        oracle = {}
        if oracle_file.exists():
            for line in oracle_file.read_text().splitlines():
                if line.strip():
                    r = json.loads(line)
                    oracle[(r["hour"], r["minute"])] = r["verdict"].lower()
        ov = oracle.get((hour, minute), "unknown")

        vname = HOUR_TO_VIDEO.get(hour)
        vpath = VIDEO_ROOT / vname if vname else None
        ch, cm, cs = _filename_start(vname) if vname else (0, 0, 0)
        start_epoch = ch * 3600 + cm * 60 + cs if vname else 0

        print(f"\n=== {version}/{hour:02d}{minute:02d} ({error_type}) ===")
        print(f"  Oracle: {ov}")

        if vpath is None or not vpath.exists():
            print(f"  Video not found: {vname}")
            continue

        out = _run_window(vpath, start_epoch, hour, minute)
        if out is None:
            print("  Detector: SKIP (no video)")
            continue

        fps, collected, bird_first = out
        wid = WindowId(tower=3, date="06/15/2026", hour=hour, minute=minute)
        res = det_mod.classify_window(
            collected, wid, min_bird_frames=2,
            min_persist_frac=0.40, glare_persist_frac=0.30,
        )
        dv_classical = res.verdict.value
        print(f"  Classical: {dv_classical} (max_area={res.max_blob_area}, samples={res.sample_count})")

        dv_final, vlm_action = await _apply_phases(
            collected, dv_classical, vpath, fps, bird_first
        )
        print(f"  VLM: {vlm_action} → final={dv_final}")

        # Determine result
        ob = ov in ("review", "manual")
        db = dv_final in ("review", "manual")
        correct = ob == db
        if error_type == "FN":
            status = "FIXED ✓" if db else "STILL FN ✗"
        else:
            status = "FIXED ✓" if not db else "STILL FP ✗"
        print(f"  Result: {status} (oracle={ov}, final={dv_final}, correct={correct})")


if __name__ == "__main__":
    asyncio.run(main())
