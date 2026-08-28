"""CLI for DarkWing: submit or validate observation CSVs."""
from __future__ import annotations

import argparse
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
import asyncio

DEFAULT_LOG_PATH = Path("submitted_log.jsonl")
DETECTOR_VERSION = "detector-v1"


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
    if args.dry_run:
        pending = records
    elif args.resume:
        done = load_completed_keys(log_path)
        pending = [r for r in records
                   if f"{r.tower}|{r.date_str}|{r.time_of_day}" not in done]
        skipped = len(records) - len(pending)
        if skipped:
            print(f"Skipping {skipped} record(s) already submitted (per {log_path}).")
    else:
        pending = records

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


def cmd_detect(args: argparse.Namespace) -> int:
    """Run detection over local footage and emit a review index (JSONL).

    Offline-first: reads from local mp4 via --source-path. A camera/RTSP
    source (plan R1) plugs into the same open_source() factory later.
    """
    import json
    from pathlib import Path as _P

    date = args.date
    tower = args.tower
    fps = args.fps
    sample_every = args.sample_every
    out_dir = _P(args.out_dir) / date / f"tower{tower}"
    manifest = out_dir / "review_index.jsonl"

    # 1. enumerate windows, skip done (resume)
    hours = range(args.hours[0], args.hours[1] + 1) if args.hours else win.OBSERVATION_HOURS
    all_w = win.iter_windows(tower, date, hours)
    done = win.resume_keys(manifest)
    pending = win.pending_windows(all_w, done)
    print(f"Windows: {len(all_w)} total, {len(pending)} pending (done={len(done)}).")

    if not pending:
        print("Nothing to do — all windows already processed.")
        return 0

    src = open_source(args.source, path=_P(args.source_path), fps=fps)
    d = det.Detector()
    glare_hours = args.glare_hours or list(det.DEFAULT_GLARE_HOURS)

    # 2. group frames by window (assumes clip starts at 06:00 for hour alignment)
    clip_start_hour = 6
    frame_window_map = {w.window_id: w for w in pending}
    collected: dict = {wid: [] for wid in frame_window_map}

    for idx, ts, frame in det.iter_frames(src.frames(), sample_every, src.fps):
        sec = int(ts)
        wh = sec // 3600 + clip_start_hour
        minute = (sec % 3600) // 60
        minute = (minute // win.WINDOW_MIN) * win.WINDOW_MIN
        wid_key = f"T{tower}_{date.replace('/', '')}_{wh:02d}{minute:02d}"
        w = frame_window_map.get(wid_key)
        if w is None:
            continue
        fr = d.process_frame(frame, idx, ts)
        collected[w.window_id].append(fr)

    # 3. classify + append
    n_skip = n_review = n_manual = 0
    for w in pending:
        frs = collected.get(w.window_id, [])
        res = det.classify_window(frs, w, glare_hours, version=DETECTOR_VERSION)
        rec = {
            "window_id": res.window_id,
            "tower": res.tower,
            "date": res.date,
            "hour": res.hour,
            "minute": res.minute,
            "verdict": res.verdict.value,
            "first_detection_ts": res.first_detection_ts,
            "max_blob_area": res.max_blob_area,
            "sample_count": res.sample_count,
            "spot_check_due": res.spot_check_due,
            "detector_version": res.detector_version,
            "glare_reason": res.glare_reason,
        }
        win.append_result(manifest, rec)
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
    p_det.add_argument("--sample-every", type=int, default=25,
                       help="Process every Nth frame (25 ≈ 1fps @25fps)")
    p_det.add_argument("--hours", type=int, nargs=2, default=None,
                       metavar=("H1", "H2"),
                       help="Hour range to process, e.g. 6 21 (default all)")
    p_det.add_argument("--glare-hours", type=int, nargs="+", default=None,
                       help="Hours forced to MANUAL verdict (default 11 12 13)")
    p_det.add_argument("--out-dir", default="footage",
                       help="Output root for review_index.jsonl")
    p_det.set_defaults(func=cmd_detect)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
