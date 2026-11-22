#!/usr/bin/env python3
"""Evaluate detector accuracy WITH VLM against ground-truth oracle.

Runs the classical detector on each validation NVR window, then applies:
- Phase 0: SKIP→REVIEW promotion when VLM confirms a sparse bird (conf ≥ 0.6)
- Phase 1: REVIEW/MANUAL→SKIP demotion when VLM confidently says no bird (conf ≥ 0.8)

Both phases fail closed: VLM unavailable/error/uncertain keeps the classical verdict.

Compares final verdicts to oracle (review_index_oracle.jsonl) and computes
precision/recall/F1/exact-match metrics, plus per-window detail.

Usage:
    VLM_PROVIDER=ollama python scripts/evaluate_detector_accuracy_vlm.py
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
REPORT_PATH = Path("detector_accuracy_vlm_report.json")

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
VERSION_TO_HOUR = {
    "v1": 8, "v2": 9, "v3": 10, "v4": 11, "v5": 13, "v6": 14, "v7": 15,
    "v8": 16, "v9": 17, "v10": 18, "v11": 19, "v12": 20, "v13": 21,
}
TARGET_MINUTES = (0, 20, 40)
OBSERVATION_SPAN_SEC = 60
WINDOW_CUTOFF_SEC = 1140

# VLM thresholds
VLM_PROMOTE_CONFIDENCE = float(os.environ.get("VLM_CONFIDENCE_THRESHOLD", "0.6"))
VLM_DEMOTION_CONFIDENCE = float(os.environ.get("VLM_DEMOTION_CONFIDENCE", "0.8"))

# Residual-error windows the user wants validated
RESIDUAL_FNS = {"v1/0800", "v1/0820", "v13/2100"}
RESIDUAL_FPS = {"v2/0920", "v7/1500", "v8/1620", "v9/1700", "v9/1720", "v9/1740"}


def _filename_start(name: str):
    for p in name.split("-"):
        if len(p) == 14 and p.isdigit():
            return int(p[8:10]), int(p[10:12]), int(p[12:14])
    return 0, 0, 0


def _run_window(video_path: Path, start_epoch: int, hour: int, minute: int):
    """Run the detector over one 20-min window, mirroring cli.py.

    Returns (fps, collected_frames, bird_first_seen) or None if unreadable.
    """
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


def _vlm_available() -> bool:
    return bool(os.environ.get("VLM_PROVIDER")) and vlm_client_adapter is not None


async def _vlm_detect_bird(frames: List, source_path: Path, fps: float,
                           first_detection_ts: float) -> Optional[Tuple[bool, float]]:
    """Run binary VLM bird check on extracted keyframes.

    Returns (bird_present, confidence) or None if VLM unavailable/failed.
    """
    if not _vlm_available():
        return None
    frames_to_send = agent_payload.extract_motion_frames(
        source_path, frames, fps=fps,
        first_detection_ts=first_detection_ts,
        span_sec=60.0, max_frames=3,
    )
    if not frames_to_send:
        return None
    ctx = {
        "source": "accuracy_eval",
        "max_blob_area": max((fr.max_blob_area for fr in frames), default=0),
    }
    try:
        bird_present, confidence = await vlm_client_adapter.detect_bird(
            frames_to_send, ctx
        )
        return bool(bird_present), float(confidence)
    except Exception as exc:
        print(f"      [VLM ERROR] {exc}")
        return None


async def _apply_phases(collected: List, verdict_str: str, source_path: Path,
                        fps: float, bird_first: Optional[float]) -> Tuple[str, str]:
    """Apply Phase 0 (SKIP→REVIEW) and Phase 1 (REVIEW/MANUAL→SKIP) VLM checks.

    Returns (final_verdict, vlm_action).
    """
    verdict = verdict_str
    has_blobs = any(fr.blobs for fr in collected)
    if not has_blobs:
        return verdict, "none"

    first_ts = bird_first
    if first_ts is None:
        first_ts = min((fr.ts_sec for fr in collected if fr.blobs), default=0.0)

    # Phase 0: SKIP → REVIEW (promotion)
    if verdict == "skip":
        result = await _vlm_detect_bird(collected, source_path, fps, first_ts)
        if result is not None:
            bird_present, confidence = result
            if bird_present and confidence >= VLM_PROMOTE_CONFIDENCE:
                return "review", "promote"
        return verdict, "none"

    # Phase 1: REVIEW/MANUAL → SKIP (demotion)
    if verdict in ("review", "manual"):
        result = await _vlm_detect_bird(collected, source_path, fps, first_ts)
        if result is not None:
            bird_present, confidence = result
            if not bird_present and confidence >= VLM_DEMOTION_CONFIDENCE:
                return "skip", "demote"
        return verdict, "none"

    return verdict, "none"


async def evaluate() -> Dict:
    results = []
    tp = fp = fn = tn = 0
    exact = 0
    evaluated = 0
    vlm_calls = 0
    vlm_promotions = 0
    vlm_demotions = 0

    for version, hour in VERSION_TO_HOUR.items():
        oracle = _load_oracle(version)
        if not oracle:
            continue
        vname = HOUR_TO_VIDEO.get(hour)
        if not vname:
            continue
        vpath = VIDEO_ROOT / vname
        if not vpath.exists():
            print(f"MISSING video for hour {hour}: {vname}")
            continue
        ch, cm, cs = _filename_start(vname)
        start_epoch = ch * 3600 + cm * 60 + cs
        for minute in TARGET_MINUTES:
            ov = oracle.get((hour, minute))
            if ov is None:
                continue
            wid = WindowId(tower=3, date="06/15/2026", hour=hour, minute=minute)

            out = _run_window(vpath, start_epoch, hour, minute)
            if out is None:
                dv_classical = "skip"
                samples = 0
            else:
                fps, collected, bird_first = out
                samples = len(collected)
                res = det_mod.classify_window(
                    collected, wid, min_bird_frames=2,
                    min_persist_frac=0.40, glare_persist_frac=0.30,
                )
                dv_classical = res.verdict.value

            # Apply VLM phases
            dv_final = dv_classical
            vlm_action = "none"
            if out is not None:
                _, collected, bird_first = out
                dv_final, vlm_action = await _apply_phases(
                    collected, dv_classical, vpath, fps, bird_first
                )
                vlm_calls += 1

            ob = ov in ("review", "manual")
            db = dv_final in ("review", "manual")
            if ob and db:
                tp += 1
            elif ov == "skip" and db:
                fp += 1
            elif ob and not db:
                fn += 1
            elif ov == "skip" and dv_final == "skip":
                tn += 1
            evaluated += 1
            if ov == dv_final:
                exact += 1
            if vlm_action == "promote":
                vlm_promotions += 1
            elif vlm_action == "demote":
                vlm_demotions += 1

            results.append({
                "window_id": wid.window_id,
                "version": version,
                "hour": hour,
                "minute": minute,
                "samples": samples,
                "oracle_verdict": ov,
                "classical_verdict": dv_classical,
                "final_verdict": dv_final,
                "vlm_action": vlm_action,
                "tp": ob and db,
                "fp": ov == "skip" and db,
                "fn": ob and not db,
                "tn": ov == "skip" and dv_final == "skip",
            })

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    accuracy = (tp + tn) / evaluated if evaluated else 0.0

    return {
        "evaluated_windows": evaluated,
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "binary_accuracy": round(accuracy, 4),
        "exact_match_rate": round(exact / evaluated, 4) if evaluated else 0.0,
        "bird_windows_total": tp + fn,
        "false_positive_rate": round(fp / evaluated, 4) if evaluated else 0.0,
        "false_negative_rate": round(fn / (tp + fn), 4) if (tp + fn) else 0.0,
        "vlm_calls": vlm_calls,
        "vlm_promotions": vlm_promotions,
        "vlm_demotions": vlm_demotions,
        "results": results,
    }


def main() -> int:
    report = asyncio.run(evaluate())
    REPORT_PATH.write_text(json.dumps(report, indent=2))

    print("=== Detector Accuracy Report (WITH VLM) ===")
    print(f"Windows evaluated: {report['evaluated_windows']}")
    print(f"VLM calls: {report['vlm_calls']}  promotions: {report['vlm_promotions']}  demotions: {report['vlm_demotions']}")
    print(f"TP={report['tp']}  FP={report['fp']}  FN={report['fn']}  TN={report['tn']}")
    print(f"Precision:  {report['precision']:.4f}")
    print(f"Recall:     {report['recall']:.4f}")
    print(f"F1:         {report['f1']:.4f}")
    print(f"Binary accuracy:   {report['binary_accuracy']:.4f}")
    print(f"Exact verdict match: {report['exact_match_rate']:.4f}")
    print(f"Bird windows: {report['bird_windows_total']}  "
          f"FP rate={report['false_positive_rate']:.4f}  "
          f"FN rate={report['false_negative_rate']:.4f}")

    print("\n=== Per-window (only changes shown) ===")
    for r in report["results"]:
        changed = r["classical_verdict"] != r["final_verdict"] or r["oracle_verdict"] != r["final_verdict"]
        if not changed:
            continue
        mark = "OK " if r["oracle_verdict"] == r["final_verdict"] else "MISMATCH"
        print(f"  {mark} {r['vlm_action']:9s} {r['window_id']}: "
              f"oracle={r['oracle_verdict']:6s} classical={r['classical_verdict']:6s} "
              f"final={r['final_verdict']:6s}")

    print(f"\nReport written to {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
