from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))

from darkwing.form_submit import submit_csv_records  # noqa: E402
from darkwing.schema import ObservationRecord  # noqa: E402


@pytest.fixture
def sample_record() -> ObservationRecord:
    return ObservationRecord.model_validate({
        "tower": "3",
        "date_str": "6/15/2026",
        "hour": "6",
        "minutes_past_hour": "0",
        "num_adults": "2",
        "nesting_stage": "no",
        "bill_use": ["na"],
        "flights": "non",
        "num_near_nest": "1",
        "awake": "y",
        "notes": "test note",
    })


@pytest.fixture
def mock_env(monkeypatch):
    monkeypatch.setenv("DARKWING_FORM_URL", "https://docs.google.com/forms/d/test")


def test_submit_csv_records_dry_run(sample_record, mock_env):
    """Dry-run should return dry-run status without network calls."""
    import asyncio
    results = asyncio.run(submit_csv_records([sample_record], dry_run=True))

    assert len(results) == 1
    assert results[0]["status"] == "dry-run"
    assert results[0]["error"] is None


def test_submit_csv_records_real(sample_record, mock_env):
    """Real submission returns error status when browser unavailable."""
    import asyncio
    from unittest.mock import AsyncMock, MagicMock, patch
    with patch("darkwing.form_submit.load_form", new=AsyncMock(return_value=(MagicMock(), MagicMock()))):
        with patch("darkwing.form_submit.submit_observation", new=AsyncMock(side_effect=Exception("no browser"))):
            with patch("darkwing.form_submit.unload_form", new=AsyncMock()):
                results = asyncio.run(submit_csv_records([sample_record], dry_run=False))

    assert len(results) == 1
    assert results[0]["status"] == "error"
    assert results[0]["error"] is not None


def test_submit_csv_records_error(sample_record, mock_env):
    """Error during submission should return error status."""
    import asyncio
    from unittest.mock import AsyncMock, MagicMock, patch
    with patch("darkwing.form_submit.load_form", new=AsyncMock(return_value=(MagicMock(), MagicMock()))):
        with patch("darkwing.form_submit.submit_observation", new=AsyncMock(side_effect=Exception("form error"))):
            with patch("darkwing.form_submit.unload_form", new=AsyncMock()):
                results = asyncio.run(submit_csv_records([sample_record], dry_run=False))
    assert results[0]["status"] == "error"


def test_submit_csv_records_multiple(sample_record, mock_env):
    """Multiple records are processed individually."""
    import asyncio
    from unittest.mock import AsyncMock, MagicMock, patch
    records = [sample_record, sample_record]
    with patch("darkwing.form_submit.load_form", new=AsyncMock(return_value=(MagicMock(), MagicMock()))):
        with patch("darkwing.form_submit.submit_observation", new=AsyncMock(side_effect=Exception("fail"))):
            with patch("darkwing.form_submit.unload_form", new=AsyncMock()):
                results = asyncio.run(submit_csv_records(records, dry_run=False))
    assert len(results) == 2
    assert all(r["status"] == "error" for r in results)
