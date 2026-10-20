"""CLI for DarkWing: submit or validate observation CSVs."""
from __future__ import annotations

import argparse
import cv2
import datetime
import logging
import os
import sys
from pathlib import Path
from typing import List, Optional

from darkwing.csv_io import (
    load_completed_keys,
    read_csv,
    write_submission_log,
)
from darkwing.form_submit import submit_csv_records
from darkwing import detector as det
from darkwing import windows as win
from darkwing.frames import open_source
from darkwing import agent as ai_agent
from darkwing import agent_payload
from darkwing import timestamp as ts_mod
import asyncio

DEFAULT_LOG_PATH = Path("submitted_log.jsonl")
DETECTOR_VERSION = "detector-v1"
OBSERVATION_SPAN_SEC = agent_payload.OBSERVATION_SPAN_SEC  # 60 s

# Trace logging
_TRACING_ENABLED = os.environ.get('DARKWING_TRACE_CLI', '').lower() in ('1', 'true', 'yes')
_logger = logging.getLogger(__name__)
if _TRACING_ENABLED:
    if not _logger.handlers:
        _handler = logging.StreamHandler()
        _handler.setFormatter(logging.Formatter('[TRACE] %(message)s'))
        _logger.addHandler(_handler)
        _logger.setLevel(logging.DEBUG)
    _logger.propagate = False  # avoid duplicate output via root logger


def _trace(msg: str) -> None:
    """Emit a trace message when DARKWING_TRACE_CLI=1."""
    if _TRACING_ENABLED:
        _logger.debug(msg)


def cmd_validate(args: argparse.Namespace) -> int:
    """Validate a CSV file and print results. Exit 0 if clean, 1 if errors."""
    try:
        records = read_csv(Path(args.csv_path))
        print(f"✓ {len(records)} record(s) validated successfully.")
        if records:
            print("Tower  Date       Time   Adults      Nesting Stage")
            for r in records:
                print(f"  - {r.tower}  {r.date_str} {r.time_of_day}  "
                    f"{r.num_adults} adult(s)  {r.nesting_stage}")
        return 0
    except Exception as exc:
        print(f"✗ Validation failed: {exc}", file=sys.stderr)
        return 1


def cmd_submit(args: argparse.Namespace) -> int:
    """Submit a CSV file, one record at a time, to the Google Form."""
    try:
        records = read_csv(Path(args.csv_path))
    except Exception as exc:
        print(f"✗ Failed to read CSV: {exc}", file=sys.stderr)
        return 1

    if not records:
        print("No records to submit.")
        return 0

    # Resume: skip records already logged as successfully submitted.
    log_path = DEFAULT_LOG_PATH
    if args.dry_run or not args.resume:
        pending = records
    else:
        done = load_completed_keys(log_path)
        pending = [r for r in records
                   if f"{r.tower}|{r.date_str}|{r.time_of_day}" not in done]
        skipped = len(records) - len(pending)
        if skipped:
            print(f"Skipping {skipped} record(s) already submitted (per {log_path}).")

    if not pending:
        print("All record(s) were already submitted. Nothing to do.")
        return 0

    print(f"Submitting {len(pending)} record(s) to the form...")
    try:
        results = asyncio.run(submit_csv_records(
            pending,
            dry_run=args.dry_run,
        ))
    except Exception as exc:
        print(f"✗ Submission failed: {exc}", file=sys.stderr)
        return 1

    succeeded = sum(1 for r in results if r.get("status") == "success"
                    or r.get("status") == "dry-run")
    failed = len(results) - succeeded

    if not args.dry_run:
        try:
            write_submission_log(results, log_path)
        except Exception as exc:
            print(f"⚠ Failed to write submission log: {exc}", file=sys.stderr)

    if args.dry_run:
        print(f"✓ {succeeded}/{len(records)} record(s) would be submitted (dry run).")
    elif failed:
        print(f"✗ {succeeded}/{len(records)} record(s) submitted; "
              f"{failed} failed. Re-run to retry the failed rows.")
        return 1
    else:
        print(f"✓ {succeeded}/{len(records)} record(s) submitted.")
    return 0


async def cmd_detect(args: argparse.Namespace, agent=None) -> int:
    """Run detection over local footage and emit a review index (JSONL).

    Offline-first: reads from local mp4 via --source-path. A camera/RTSP
    source (plan R1) plugs into the same open_source() factory later.

    If ``--agent`` is set (and ``agent`` is provided or a key is configured),
    REVIEW windows are sent to the VLM agent, which appends an
    ``ai_observation`` proposal to the review index for human audit.
    """
    date = args.date
    tower = args.tower
    fps = args.fps
    sample_every = args.sample_every
    out_dir = Path(args.out_dir) / date / f"tower{tower}"
    manifest = out_dir / "review_index.jsonl"

    vlm_provider = os.environ.get('VLM_PROVIDER')
    # Ensure agent is typed for awaitable member access
    vlm_agent: ai_agent.AIObservationAgent = agent  # type: ignore

    # 1. enumerate windows, skip done (resume)
    hours = range(args.hours[0], args.hours[1] + 1) if args.hours else win.OBSERVATION_HOURS
    all_w = win.iter_windows(tower, date, hours)
    if args.hours and args.hours[0] != args.hours[1]:
        # Multi-hour range: the end hour only includes the window starting at
        # minute 0 (not 20 or 40), so a 60-s observation span fits before the
        # next hour's windows begin.
        end_hour = args.hours[1]
        all_w = [w for w in all_w if w.hour != end_hour or w.minute == 0]
    done = win.resume_keys(manifest)
    pending = win.pending_windows(all_w, done)
    print(f"Windows: {len(all_w)} total, {len(pending)} pending (done={len(done)}).")

    if not pending:
        print("Nothing to do — all windows already processed.")
        return 0

    src = open_source(args.source, path=Path(args.source_path), fps=fps)
    d = det.Detector()

    # Prime the MOG2 background model by feeding it the first ~30 seconds of
    # footage. An unprimed model flags the entire wall as shadow
    # (shadow_frac ≈ 1.0) and misses birds that haven't changed against a
    # model it hasn't learned yet. We prime only for local video sources;
    # the synthetic source starts with a known background.
    if args.source == "local" and args.source_path and Path(args.source_path).exists():
        prime_n = int((src.fps or 25.0) * 30)  # 30 s at source fps
        _cap = cv2.VideoCapture(str(Path(args.source_path)))
        if _cap.isOpened():
            # Create a simple generator for priming
            def _prime_gen():
                for i in range(prime_n):
                    ok, frame = _cap.read()
                    if not ok:
                        break
                    yield frame
            primed = d.prime(_prime_gen(), prime_n)
            _trace(f"Primed MOG2 with {primed} frames")
        _cap.release()

    # Determine sample_every from actual video fps for 1 fps sampling.
    # This ensures we check one frame per real wall-clock second.
    if src.fps:
        sample_every = max(1, int(round(src.fps)))
    else:
        sample_every = args.sample_every

    # 2. Determine the true video start time via OCR/metadata, falling back to
    #    the user-provided flag. This aligns video wall-clock time with window
    #    boundaries.
    if args.video_start_time:
        video_start = ts_mod.parse_user_start_time(args.video_start_time)
        source_label = "user-provided flag"
    elif args.source_path and Path(args.source_path).exists():
        video_start = ts_mod.extract_video_start_time(Path(args.source_path))
        if video_start:
            source_label = "automatically (OCR)"
        else:
            video_start = None
            source_label = None
    else:
        video_start = None
        source_label = None

    # clip_start_hour: the hour the first window starts in. The raw timestamps
    # from the source are elapsed-seconds from clip start.
    clip_start_hour = args.hours[0] if args.hours else 6

    # Compute the offset in seconds to align raw timestamps with wall-clock time.
    # Uses time-of-day arithmetic only (not full datetime subtraction) so the
    # dates don't matter. E.g., video_start=06:59:54, clip_start_hour=7 → +6s.
    if video_start:
        offset_seconds = ts_mod.compute_time_offset(video_start, clip_start_hour)
    else:
        offset_seconds = 0

    if source_label:
        print(f"Video start time extracted: {video_start.strftime('%H:%M:%S')} "
              f"(via {source_label}); clip_start_hour={clip_start_hour}; "
              f"offset_seconds={offset_seconds:+.1f} (subtracted; frames before "
              f"{clip_start_hour:02d}:00:00 are skipped)")

    frame_window_map = {w.window_id: w for w in pending}
    collected: dict = {wid: [] for wid in frame_window_map}
    # Track per-window first-bird-detection time and span end.
    bird_first_seen: dict = {}
    span_end_ts: dict = {}  # window_id -> exclusive end time of span
    windows_reached: set = set()
    _window_reached_logged: set = set()  # windows we already logged for reaching

    # Cutoff: if no bird detected by the cutoff (19:00 / 39:00 / 59:00 within
    # the hour = 1140 s into the 20-min window), skip that window. This ensures
    # a full 60-second observation span can fit before the next window starts.
    cutoff_seconds = win.WINDOW_CUTOFF_SEC  # 1140 s = 19 * 60

    _trace(f"Starting frame loop: sample_every={sample_every}, offset={offset_seconds}, "
           f"clip_start_hour={clip_start_hour}, cutoff={cutoff_seconds}s")

    for idx, ts, frame in det.iter_frames(src.frames(), sample_every, src.fps):
        # Convert raw elapsed seconds to seconds since clip_start_hour.
        # Video starts offset_seconds early; skip those frames and subtract
        # the offset so detection starts cleanly at the reported start time.
        real_ts = ts - offset_seconds
        if real_ts < 0:
            continue  # frame is before clip_start (e.g. 06:59:xx for a 07:xx window)
        sec = int(real_ts)
        wh = sec // 3600 + clip_start_hour
        minute = (sec % 3600) // 60
        minute = (minute // win.WINDOW_MIN) * win.WINDOW_MIN
        wid_key = f"T{tower}_{date.replace('/', '')}_{wh:02d}{minute:02d}"
        w = frame_window_map.get(wid_key)
        if w is None:
            continue

        windows_reached.add(w.window_id)

        # Seconds into the current 20-minute window.
        seconds_into_window = real_ts - ((w.hour - clip_start_hour) * 3600 + w.minute * 60)

        # If we haven't detected a bird yet in this window:
        if w.window_id not in bird_first_seen:
            # If we're past the cutoff and still no bird, skip this window entirely.
            if seconds_into_window > cutoff_seconds:
                _trace(f"[CUTOFF] Window {w.window_id}: no bird by "
                       f"{seconds_into_window:.1f}s (cutoff={cutoff_seconds}s), "
                       f"skipping remaining frames")
                continue  # stop sampling this window; no bird by cutoff
            # Log window reached once
            if w.window_id not in _window_reached_logged:
                _window_reached_logged.add(w.window_id)
                _trace(f"[WINDOW REACHED] {w.window_id} "
                       f"frame={idx} real_ts={real_ts:.1f}s "
                       f"seconds_into_window={seconds_into_window:.1f}s")

            # Process frame for detection.
            fr = d.process_frame(frame, idx, real_ts)
            if fr.blobs:
                # First detection! Record it and set up the 60-second observation span.
                bird_first_seen[w.window_id] = real_ts
                span_end_ts[w.window_id] = real_ts + OBSERVATION_SPAN_SEC
                collected[w.window_id].append(fr)
                _trace(f"[FIRST BIRD DETECTED] Window {w.window_id}: "
                       f"ts={real_ts:.1f}s, blobs={len(fr.blobs)}, max_area={fr.max_blob_area}, "
                       f"span_end={span_end_ts[w.window_id]:.1f}s")
            # Else: no bird yet, don't collect the frame.
        else:
            # We already detected a bird and are collecting the observation span.
            # Only collect frames that fall within [first_detection_ts, first_detection_ts + 60].
            if real_ts < span_end_ts[w.window_id]:
                fr = d.process_frame(frame, idx, real_ts)
                collected[w.window_id].append(fr)
            # Else: we're past the observation span, skip this frame.

    # 3. classify + append
    n_skip = n_review = n_manual = 0
    for w in pending:
        first_det = bird_first_seen.get(w.window_id)
        frs = collected.get(w.window_id, [])

        if first_det is None:
            # No bird detected in this window.
            if w.window_id not in windows_reached:
                # Window doesn't exist in the video — emit a warning.
                print(f"⚠️  No frames collected for window {w.window_id} "
                      f"({w.hour:02d}:{w.minute:02d}) — video may not cover this window")
                continue
            # Window exists but no bird → SKIP. Pass empty frames to classifier.
            frs = []

        res = det.classify_window(frs, w, version=DETECTOR_VERSION)

        # Phase 2: Backfill to refine first-detection timestamp (hybrid approach)
        if (
            res.verdict is det.Verdict.REVIEW
            and res.first_detection_ts is not None
            and args.source == "local"
            and args.source_path
            and Path(args.source_path).exists()
        ):
            refined_ts = d.backfill_first_detection(
                Path(args.source_path),
                res.first_detection_ts,
                clip_start_hour=clip_start_hour,
                fps=src.fps,
                max_search_sec=30.0,
            )
            if refined_ts is not None and refined_ts < res.first_detection_ts:
                res.first_detection_ts = refined_ts
                # Recompute wall-clock with refined timestamp
                total_sec = int(refined_ts)
                wh = (total_sec // 3600) + clip_start_hour
                mm = (total_sec % 3600) // 60
                ss = total_sec % 60
                first_wallclock = f"{wh:02d}:{mm:02d}:{ss:02d}"
                print(
                    f"[BACKFILL] Window {w.window_id}: refined first detection "
                    f"{total_sec // 3600:02d}:{(total_sec % 3600) // 60:02d}:{total_sec % 60:02d}"
                )
            else:
                # Fall back to original if backfill didn't refine
                total_sec = int(res.first_detection_ts)
                wh = (total_sec // 3600) + clip_start_hour
                mm = (total_sec % 3600) // 60
                ss = total_sec % 60
                first_wallclock = f"{wh:02d}:{mm:02d}:{ss:02d}"
        else:
            # Wall-clock timestamp of the first detection (HH:MM:SS) so the report
            # shows the actual time the bird was seen, not just seconds from clip start.
            first_wallclock = None
            if res.first_detection_ts is not None:
                total_sec = int(res.first_detection_ts)
                wh = (total_sec // 3600) + clip_start_hour
                mm = (total_sec % 3600) // 60
                ss = total_sec % 60
                first_wallclock = f"{wh:02d}:{mm:02d}:{ss:02d}"

        rec = {
            "window_id": res.window_id,
            "tower": res.tower,
            "date": res.date,
            "hour": res.hour,
            "minute": res.minute,
            "verdict": res.verdict.value,
            "first_detection_ts": res.first_detection_ts,
            "first_detection_wallclock": first_wallclock,
            "max_blob_area": res.max_blob_area,
            "sample_count": res.sample_count,
            "spot_check_due": res.spot_check_due,
            "detector_version": res.detector_version,
            "glare_reason": res.glare_reason,
        }

        # Phase 3: AI Agent Integration (REQ-7)
        if vlm_provider and res.verdict is det.Verdict.REVIEW:
            # 1. Payload Extraction (Phase 1) — use the possibly-refined first_detection_ts
            # and a 2-minute span so the model can see the bird's arrival.
            frames_to_send = agent_payload.extract_motion_frames(
                Path(args.source_path), frs, fps=src.fps,
                first_detection_ts=res.first_detection_ts,
                span_sec=120.0,  # 2 minutes: 1 min before + 1 min after detection
            )
            if frames_to_send:
                # 2. Agent Proposal (Phase 2)
                if agent is None:
                    try:
                        agent = ai_agent.AIObservationAgent()
                    except ValueError as exc:
                        print(f"✗ Failed to initialize VLM agent: {exc}", file=sys.stderr)
                        return 1
                    vlm_agent = agent
                # context_metadata maps to agent.propose_observation's context_metadata arg
                ctx = {
                    "tower": res.tower,
                    "date": res.date,
                    "hour": res.hour,
                    "minute": res.minute,
                    "detector_version": res.detector_version
                }
                try:
                    proposal = await vlm_agent.propose_observation(frames_to_send, context_metadata=ctx)
                    rec["ai_observation"] = proposal.model_dump()
                    print(f"[AI PROPOSAL] Window {w.window_id}: AI observation generated")
                except Exception as exc:
                    print(f"⚠️  VLM analysis failed for window {w.window_id}: {exc}")
                    # Continue without AI observation for this window
        win.append_result(manifest, rec)
        _trace(
            f"[RESULT] Window {w.window_id}: verdict={res.verdict.value}, "
            f"first_detection_ts={res.first_detection_ts}, max_blob_area={res.max_blob_area}, "
            f"sample_count={res.sample_count}, glare_reason={res.glare_reason!r}"
        )
        if res.verdict is det.Verdict.SKIP:
            n_skip += 1
        elif res.verdict is det.Verdict.REVIEW:
            n_review += 1
        else:
            n_manual += 1

    src.close()
    print(f"Review index -> {manifest}")
    print(f"  SKIP={n_skip}  REVIEW={n_review}  MANUAL={n_manual}")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="darkwing",
        description="Submit chimney swift observations to a Google Form.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # validate subcommand
    p_val = sub.add_parser("validate", help="Validate a CSV without submitting")
    p_val.add_argument("csv_path", help="Path to the observation CSV")
    p_val.set_defaults(func=cmd_validate)

    # submit subcommand
    p_sub = sub.add_parser("submit", help="Submit a CSV to the form")
    p_sub.add_argument("csv_path", help="Path to the observation CSV")
    p_sub.add_argument("--dry-run", action="store_true",
                       help="Print what would be submitted without submitting")
    p_sub.add_argument("--no-resume", dest="resume", action="store_false",
                       help="Submit all rows even if already logged as submitted")
    p_sub.set_defaults(func=cmd_submit, resume=True)

    # detect subcommand (MVP2)
    p_det = sub.add_parser(
        "detect", help="Run detection over footage and emit a review index")
    p_det.add_argument("--date", required=True,
                       help="Observation date in MM/DD/YYYY")
    p_det.add_argument("--tower", type=int, required=True,
                       help="Tower identifier (1-4)")
    p_det.add_argument("--source", default="local",
                       choices=["local", "synthetic"],
                       help="Frame source kind (local mp4 now; camera later)")
    p_det.add_argument("--source-path", default="",
                       help="Path to local mp4 when --source=local")
    p_det.add_argument("--fps", type=float, default=None,
                       help="Override clip fps for timestamp derivation")
    p_det.add_argument("--video-start-time", default=None,
                       help="Video start time in HH:MM:SS or HH:MM format (e.g. '06:59:54'). "
                            "If not provided, Claude Code will attempt automatic extraction via OCR/metadata.")
    p_det.add_argument("--sample-every", type=int, default=25,
                       help="Process every Nth frame (25 ≈ 1fps @25fps)")
    p_det.add_argument("--hours", type=int, nargs=2, default=None,
                       metavar=("H1", "H2"),
                       help="Hour range to process, e.g. 6 21 (default all)")
    p_det.add_argument("--out-dir", default="footage",
                       help="Output root for review_index.jsonl")

    p_det.set_defaults(func=cmd_detect)

    args = parser.parse_args(argv)
    result = args.func(args)
    if hasattr(args, "func") and args.func.__name__ == "cmd_detect":
        return asyncio.run(result)
    return result


if __name__ == "__main__":
    sys.exit(main())
