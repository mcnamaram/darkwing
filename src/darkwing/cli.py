"""CLI for DarkWing: submit or validate observation CSVs."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional

from darkwing.csv_io import read_csv
from darkwing.form_submit import submit_csv_records
from darkwing.schema import ObservationRecord


def cmd_validate(args: argparse.Namespace) -> int:
    """Validate a CSV file and print results. Exit 0 if clean, 1 if errors."""
    try:
        records = read_csv(Path(args.csv_path))
        print(f"✓ {len(records)} record(s) validated successfully.")
        for r in records:
            print(f"  - {r.tower}  {r.date_str} {r.time_of_day}  "
                  f"{r.num_adults} adult(s)  {r.nesting_stage}")
        return 0
    except Exception as exc:
        print(f"✗ Validation failed: {exc}", file=sys.stderr)
        return 1


def cmd_submit(args: argparse.Namespace) -> int:
    """Submit a CSV file, one record at a time, to the Apps Script webhook."""
    try:
        records = read_csv(Path(args.csv_path))
    except Exception as exc:
        print(f"✗ Failed to read CSV: {exc}", file=sys.stderr)
        return 1

    if not records:
        print("No records to submit.")
        return 0

    print(f"Submitting {len(records)} record(s) to the form...")
    try:
        results = submit_csv_records(
            records,
            dry_run=args.dry_run,
        )
    except Exception as exc:
        print(f"✗ Submission failed: {exc}", file=sys.stderr)
        return 1

    succeeded = sum(1 for r in results if r.get("status") == "success"
                    or r.get("status") == "dry-run")
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
                       help="Print what would be submitted without POSTing")
    p_sub.set_defaults(func=cmd_submit)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
