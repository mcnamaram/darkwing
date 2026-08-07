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

from darkwing.csv_io import read_csv, read_csv_iter, write_submission_log, get_submission_log  # noqa: E402
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
    assert r.tower == "Tower 3"
    assert r.num_adults == 2
    assert r.flights == ["in"]
    assert r.date_str == "06/15/2026"
    assert r.time_of_day == "06:00"


def test_read_csv_last_row(valid_records):
    r = valid_records[-1]
    assert r.tower == "Tower 2"
    assert r.hour == 18
    assert r.minutes_past_hour == 30
    assert r.time_of_day == "18:30"
    assert r.awake == "n"


def test_read_csv_empty_flights(valid_records: list):
    """Row with empty flights array parses correctly."""
    r = valid_records[2]  # the "0 adults, no flight" row
    assert r.flights == []
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
        "date_str,hour,minutes_past_hour,tower,num_adults,"
        "nesting_stage,bill_use,flights,num_near_nest,awake,notes\n"
        "2026-06-15,6,0,Tower 1,0,No nest,N/A or No,[],0,Yes,\n",
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
        "date_str,hour,minutes_past_hour,tower,num_adults,"
        "nesting_stage,bill_use,flights,num_near_nest,awake,notes\n"
        "6/15/2026,6,0,Tower 1,0,Invalid stage,N/A or No,[],0,Yes,\n",
        encoding="utf-8",
    )
    try:
        with pytest.raises(ValueError, match="nesting_stage"):
            read_csv(bad_csv)
    finally:
        bad_csv.unlink()


# ── write_submission_log / get_submission_log ─────────────────────────────────

def test_write_and_read_submission_log(tmp_path: Path, valid_records: list):
    log_path = tmp_path / "submitted_log.jsonl"
    write_submission_log(valid_records, log_path)
    assert log_path.exists()
    lines = log_path.read_text().splitlines()
    assert len(lines) == len(valid_records)
    # each line is valid JSON
    for line in lines:
        obj = json.loads(line)
        assert "date_str" in obj
        assert "tower" in obj


def test_get_submission_log_empty(tmp_path: Path):
    log_path = tmp_path / "empty_log.jsonl"
    assert get_submission_log(log_path) == []


def test_get_submission_log_missing_file(tmp_path: Path):
    log_path = tmp_path / "nonexistent.jsonl"
    assert get_submission_log(log_path) == []


def test_write_appends_to_existing_log(tmp_path: Path, valid_records: list):
    log_path = tmp_path / "append_log.jsonl"
    write_submission_log(valid_records[:2], log_path)
    write_submission_log(valid_records[2:], log_path)
    lines = log_path.read_text().splitlines()
    assert len(lines) == len(valid_records)
