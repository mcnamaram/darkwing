#!/usr/bin/env python3
"""Evaluate detector accuracy against the ground-truth oracle.

This re-runs the detector FRESH on the validation NVR videos (mirroring the
real ``darkwing detect`` pipeline: 30 s MOG2 priming, 2 fps sampling, bird-gated
60 s observation span, cutoff) and compares the resulting verdicts to the
hand-labelled oracle files. The oracle is ground truth; it is never modified.

Binary metric (does the window contain bird activity?):
- TP: oracle ∈ {review, manual}, detector ∈ {review, manual}
- FP: oracle = skip,               detector ∈ {review, manual}
- FN: oracle ∈ {review, manual},   detector = skip
- TN: oracle = skip,               detector = skip

Also reports exact 3-class verdict agreement (skip/review/manual).

Usage:
    python scripts/evaluate_detector_accuracy.py
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, List, Optional

import cv2

from darkwing import detector as det_mod
from darkwing.windows import WindowId

VALIDATION_ROOT = Path("footage/validation")
VIDEO_ROOT = Path(".hermes/nvr-videos")
REPORT_PATH = Path("detector_accuracy_report.json")

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

# Same sampling / span constants as cli.py
OBSERVATION_SPAN_SEC = 60
WINDOW_CUTOFF_SEC = 1140

# Persistence thresholds (env-overridable for sweeping).
MIN_BIRD_FRAMES = int(os.environ.get("DARKWING_MIN_BIRD_FRAMES", "2"))
MIN_PERSIST_FRAC = float(os.environ.get("DARKWING_MIN_PERSIST_FRAC", "0.40"))
GLARE_PERSIST_FRAC = float(os.environ.get("DARKWING_GLARE_PERSIST_FRAC", "0.30"))


def _filename_start(name: str):
    for p in name.split("-"):
        if len(p) == 14 and p.isdigit():
            return int(p[8:10]), int(p[10:12]), int(p[12:14])
    return 0, 0, 0


def _run_window(video_path: Path, start_epoch: int, hour: int, minute: int):
    """Run the detector over one 20-min window, mirroring cli.py.

    Returns (fps, collected_frames, bird_first_seen) or None if video unreadable.
    """
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return None
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    sample_every = max(1, int(round(fps / 2)))
    d = det_mod.Detector()

    # Prime MOG2 with first 30 s
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


def evaluate() -> Dict:
    results = []
    tp = fp = fn = tn = 0
    exact = 0
    evaluated = 0

    for version, hour in VERSION_TO_HOUR.items():
        oracle = _load_oracle(version)
        if not oracle:
            continue
        vname = HOUR_TO_VIDEO.get(hour)
        if not vname:
            continue
        vpath = VIDEO_ROOT / vname
        readable = vpath.exists()
        ch, cm, cs = _filename_start(vname)
        start_epoch = ch * 3600 + cm * 60 + cs

        for minute in TARGET_MINUTES:
            ov = oracle.get((hour, minute))
            if ov is None:
                continue
            wid = WindowId(tower=3, date="06/15/2026", hour=hour, minute=minute)

            if not readable:
                dv = "skip"  # no coverage -> detector emits SKIP
                samples = 0
            else:
                out = _run_window(vpath, start_epoch, hour, minute)
                if out is None:
                    dv = "skip"
                    samples = 0
                else:
                    _, collected, _ = out
                    samples = len(collected)
                    res = det_mod.classify_window(
                        collected, wid, min_bird_frames=MIN_BIRD_FRAMES,
                        min_persist_frac=MIN_PERSIST_FRAC,
                        glare_persist_frac=GLARE_PERSIST_FRAC,
                    )
                    dv = res.verdict.value

            ob = ov in ("review", "manual")
            db = dv in ("review", "manual")
            if ob and db:
                tp += 1
            elif ov == "skip" and db:
                fp += 1
            elif ob and dv == "skip":
                fn += 1
            elif ov == "skip" and dv == "skip":
                tn += 1
            evaluated += 1
            if ov == dv:
                exact += 1

            results.append({
                "window_id": wid.window_id, "version": version,
                "hour": hour, "minute": minute, "samples": samples,
                "oracle_verdict": ov, "detector_verdict": dv,
                "tp": ob and db, "fp": ov == "skip" and db,
                "fn": ob and dv == "skip",
                "tn": ov == "skip" and dv == "skip",
            })

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    accuracy = (tp + tn) / evaluated if evaluated else 0.0
    bird_total = tp + fn

    return {
        "evaluated_windows": evaluated,
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "binary_accuracy": round(accuracy, 4),
        "exact_match_rate": round(exact / evaluated, 4) if evaluated else 0.0,
        "bird_windows_total": bird_total,
        "false_positive_rate": round(fp / evaluated, 4) if evaluated else 0.0,
        "false_negative_rate": round(fn / bird_total, 4) if bird_total else 0.0,
        "results": results,
    }


def main() -> int:
    report = evaluate()
    REPORT_PATH.write_text(json.dumps(report, indent=2))

    print("=== Detector Accuracy Report (fresh re-run) ===")
    print(f"Windows evaluated: {report['evaluated_windows']}")
    print(f"TP={report['tp']}  FP={report['fp']}  FN={report['fn']}  TN={report['tn']}")
    print(f"Precision:  {report['precision']:.4f}")
    print(f"Recall:     {report['recall']:.4f}")
    print(f"F1:         {report['f1']:.4f}")
    print(f"Binary accuracy:   {report['binary_accuracy']:.4f}")
    print(f"Exact verdict match: {report['exact_match_rate']:.4f}")
    print(f"Bird windows: {report['bird_windows_total']}  "
          f"FP rate={report['false_positive_rate']:.4f}  "
          f"FN rate={report['false_negative_rate']:.4f}")

    print("\n=== Per-window ===")
    for r in report["results"]:
        tag = "TP" if r["tp"] else "FP" if r["fp"] else "FN" if r["fn"] else "TN"
        mark = "OK " if r["oracle_verdict"] == r["detector_verdict"] else "MISMATCH"
        print(f"  {mark} {tag} {r['window_id']}: oracle={r['oracle_verdict']:6s} "
              f"detector={r['detector_verdict']:6s} samples={r['samples']}")

    print(f"\nReport written to {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
