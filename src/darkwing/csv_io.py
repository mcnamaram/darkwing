"""CSV read/write for observation records."""
from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, Iterator, List

from darkwing.schema import ObservationRecord, parse_observation_row


def read_csv(path: Path) -> List[ObservationRecord]:
    """Read a curated CSV into a list of validated ObservationRecords.

    Expected columns (order-independent):
        tower, date_str, hour, minutes_past_hour, num_adults,
        nesting_stage, bill_use, flights, num_near_nest, awake, notes

    ``flights`` is expected as semicolon-delimited short codes (e.g. ``in`` or ``in;out``).
    Legacy JSON array strings (e.g. ``["in"]``) are also accepted for backwards compatibility.
    Rows that fail validation are collected and raised as a single
    ``ValidationError`` with per-row details.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"CSV not found: {path}")

    records: List[ObservationRecord] = []
    errors: List[dict] = []

    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row_num, row in enumerate(reader, start=2):  # row 1 = header
            try:
                rec = parse_observation_row(row)
                records.append(rec)
            except Exception as exc:
                errors.append({
                    "row": row_num,
                    "raw": dict(row),
                    "error": str(exc),
                })

    if errors:
        parts = [f"{e['row']}: {e['error']}" for e in errors]
        raise ValueError(
            f"{len(errors)} row(s) failed validation:\n"
            + "\n".join(parts)
        )

    return records


def read_csv_iter(path: Path) -> Iterator[ObservationRecord]:
    """Lazy iterator version of ``read_csv`` — yields one record at a time."""
    for rec in read_csv(path):
        yield rec


def _submission_key(rec: ObservationRecord) -> str:
    """Stable identity key for a record: tower|date|time-of-day."""
    return f"{rec.tower}|{rec.date_str}|{rec.time_of_day}"


def load_completed_keys(log_path: Path) -> set[str]:
    """Return identity keys of records successfully submitted per the log."""
    keys: set[str] = set()
    for entry in get_submission_log(log_path):
        if entry.get("status") != "success":
            continue
        rec = entry.get("record", {})
        try:
            parsed = ObservationRecord.model_validate(rec)
        except Exception:
            continue  # malformed log line — treat as not-submitted
        keys.add(_submission_key(parsed))
    return keys


def write_submission_log(
    results: Iterable[Dict],
    log_path: Path,
) -> None:
    """Append submission results to a JSON-Lines log file.

    Each result is a dict ``{'record': ObservationRecord, 'status': str,
    'error': str | None}`` as returned by ``submit_csv_records()``.
    Each line written is
    ``{'record': ..., 'status': ..., 'error': ..., 'timestamp': iso8601}``.
    Creates the file if it doesn't exist; appends if it does.
    """
    log_path = Path(log_path)
    with log_path.open("a", encoding="utf-8") as f:
        for result in results:
            entry = {
                "record": json.loads(result["record"].model_dump_json()),
                "status": result["status"],
                "error": result.get("error"),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            f.write(json.dumps(entry) + "\n")


def get_submission_log(log_path: Path) -> List[Dict]:
    """Read the submission log back into a list of dicts."""
    log_path = Path(log_path)
    if not log_path.exists():
        return []
    records: List[Dict] = []
    with log_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records
