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
import asyncio

DEFAULT_LOG_PATH = Path("submitted_log.jsonl")


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

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
