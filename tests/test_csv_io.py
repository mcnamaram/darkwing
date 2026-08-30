from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
FIXTURES_ROOT = PROJECT_ROOT / "tests" / "fixtures"

sys.path.insert(0, str(SRC_ROOT))

from darkwing.csv_io import (  # noqa: E402
    load_completed_keys,
    read_csv,
    read_csv_iter,
    write_submission_log,
    get_submission_log,
)
from darkwing.schema import ObservationRecord  # noqa: E402


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def valid_csv_path() -> Path:
    return FIXTURES_ROOT / "sample_observation.csv"


@pytest.fixture
def valid_records(valid_csv_path) -> list:
    return read_csv(valid_csv_path)


# ── read_csv: success cases ───────────────────────────────────────────────────

def test_read_csv_returns_list_of_records(valid_records: list):
    assert isinstance(valid_records, list)
    assert len(valid_records) > 0
    assert isinstance(valid_records[0], ObservationRecord)


def test_read_csv_parses_all_rows(valid_records: list):
    # sample has 4 rows (header excluded)
    assert len(valid_records) == 4


def test_read_csv_first_row(valid_records: list):
    r = valid_records[0]
    assert r.tower == 3
    assert r.num_adults == 2
    assert r.flights == ["in"]
    assert r.date_str == "06/15/2026"
    assert r.time_of_day == "06:00"


def test_read_csv_last_row(valid_records):
    r = valid_records[-1]
    assert r.tower == 2
    assert r.hour == 18
    assert r.minutes_past_hour == 20
    assert r.time_of_day == "18:20"
    assert r.awake == "n"


def test_read_csv_empty_flights(valid_records: list):
    """Row with no flight activity still parses with default 'non'."""
    r = valid_records[2]  # the "0 adults, no flight" row
    assert r.flights == ["non"]
    assert r.num_adults == 0


def test_read_csv_iter_yields_same_records(valid_records: list, valid_csv_path):
    records = list(read_csv_iter(valid_csv_path))
    assert len(records) == len(valid_records)
    for a, b in zip(records, valid_records):
        assert a.model_dump() == b.model_dump()


# ── read_csv: error cases ─────────────────────────────────────────────────────

def test_read_csv_file_not_found():
    with pytest.raises(FileNotFoundError, match="CSV not found"):
        read_csv(Path("/nonexistent/path.csv"))


def test_read_csv_invalid_date():
    """Row with bad date format raises ValueError."""
    bad_csv = FIXTURES_ROOT / "bad_date.csv"
    bad_csv.write_text(
        "tower,date_str,hour,minutes_past_hour,num_adults,"
        "nesting_stage,bill_use,flights,num_near_nest,awake,notes\n"
        "1,2026-06-15,6,0,0,No nest,N/A or No,[],0,Yes,\n",
        encoding="utf-8",
    )
    try:
        with pytest.raises(ValueError, match="date_str"):
            read_csv(bad_csv)
    finally:
        bad_csv.unlink()


def test_read_csv_invalid_nesting_stage():
    bad_csv = FIXTURES_ROOT / "bad_stage.csv"
    bad_csv.write_text(
        "tower,date_str,hour,minutes_past_hour,num_adults,"
        "nesting_stage,bill_use,flights,num_near_nest,awake,notes\n"
        "1,6/15/2026,6,0,0,Invalid stage,N/A or No,[],0,Yes,\n",
        encoding="utf-8",
    )
    try:
        with pytest.raises(ValueError, match="nesting_stage"):
            read_csv(bad_csv)
    finally:
        bad_csv.unlink()


# ── write_submission_log / get_submission_log ─────────────────────────────────

def _result(rec: ObservationRecord, status: str = "success",
            error: str | None = None) -> dict:
    return {"record": rec, "status": status, "error": error}


def test_write_and_read_submission_log(tmp_path: Path, valid_records: list):
    log_path = tmp_path / "submitted_log.jsonl"
    results = [_result(r) for r in valid_records]
    write_submission_log(results, log_path)
    assert log_path.exists()
    lines = log_path.read_text().splitlines()
    assert len(lines) == len(valid_records)
    # each line is valid JSON with the documented entry shape
    for line in lines:
        obj = json.loads(line)
        assert set(obj) == {"record", "status", "error", "timestamp"}
        assert obj["status"] == "success"
        assert "tower" in obj["record"]


def test_write_does_not_log_error_results(tmp_path: Path, valid_records: list):
    """Error results are silently skipped; only successes reach the log."""
    log_path = tmp_path / "log.jsonl"
    results = [
        _result(valid_records[0], "success"),
        _result(valid_records[1], "error", "Submission failed"),
    ]
    write_submission_log(results, log_path)
    entries = [json.loads(line) for line in log_path.read_text().splitlines()]
    # Only the success record should be in the log
    assert len(entries) == 1
    assert entries[0]["status"] == "success"
    # No error entry should appear anywhere in the log
    for entry in entries:
        assert entry["status"] != "error"


def test_get_submission_log_empty(tmp_path: Path):
    log_path = tmp_path / "empty_log.jsonl"
    assert get_submission_log(log_path) == []


def test_get_submission_log_missing_file(tmp_path: Path):
    log_path = tmp_path / "nonexistent.jsonl"
    assert get_submission_log(log_path) == []


def test_write_appends_to_existing_log(tmp_path: Path, valid_records: list):
    log_path = tmp_path / "append_log.jsonl"
    write_submission_log([_result(r) for r in valid_records[:2]], log_path)
    write_submission_log([_result(r) for r in valid_records[2:]], log_path)
    lines = log_path.read_text().splitlines()
    assert len(lines) == len(valid_records)


# ── load_completed_keys / resume ──────────────────────────────────────────────

def test_load_completed_keys_success_only(tmp_path: Path, valid_records: list):
    """Only 'success' entries count as done; errors must be retried."""
    log_path = tmp_path / "log.jsonl"
    write_submission_log([
        _result(valid_records[0], "success"),
        _result(valid_records[1], "error", "boom"),
    ], log_path)
    keys = load_completed_keys(log_path)
    assert len(keys) == 1
    r0, r1 = valid_records[0], valid_records[1]
    assert f"{r0.tower}|{r0.date_str}|{r0.time_of_day}" in keys
    assert f"{r1.tower}|{r1.date_str}|{r1.time_of_day}" not in keys


def test_load_completed_keys_missing_file(tmp_path: Path):
    assert load_completed_keys(tmp_path / "nope.jsonl") == set()


def test_load_completed_keys_ignores_malformed_lines(
        tmp_path: Path, valid_records: list):
    log_path = tmp_path / "log.jsonl"
    write_submission_log([_result(valid_records[0])], log_path)
    with log_path.open("a") as f:
        f.write('{"record": {"tower": "not-a-tower"}, "status": "success"}\n')
    keys = load_completed_keys(log_path)
    assert len(keys) == 1  # malformed entry silently skipped


def test_resume_key_is_stable_across_serialization(
        tmp_path: Path, valid_records: list):
    """Key computed from a record matches key re-parsed from the log."""
    from darkwing.csv_io import _submission_key
    log_path = tmp_path / "log.jsonl"
    write_submission_log([_result(r) for r in valid_records], log_path)
    keys = load_completed_keys(log_path)
    for rec in valid_records:
        assert _submission_key(rec) in keys
