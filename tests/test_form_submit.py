from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))

from darkwing.form_submit import (  # noqa: E402
    _get_apps_script_url,
    submit_record,
    submit_csv_records,
)
from darkwing.schema import ObservationRecord  # noqa: E402


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture
def sample_record() -> ObservationRecord:
    return ObservationRecord.model_validate({
        "date_str": "6/15/2026",
        "hour": "6",
        "minutes_past_hour": "0",
        "tower": "Tower 3",
        "num_adults": "2",
        "nesting_stage": "no",
        "bill_use": "na",
        "flights": '["in"]',
        "num_near_nest": "1",
        "awake": "y",
        "notes": "test note",
    })


@pytest.fixture
def mock_env(monkeypatch):
    monkeypatch.setenv("DARKWING_APPS_SCRIPT_URL", "https://script.google.com/macros/s/test/exec")


# ── _get_apps_script_url ──────────────────────────────────────────────────────

def test_get_apps_script_url_from_env(monkeypatch):
    monkeypatch.setenv("DARKWING_APPS_SCRIPT_URL", "https://example.com/exec")
    assert _get_apps_script_url() == "https://example.com/exec"


def test_get_apps_script_url_missing(monkeypatch, tmp_path: Path):
    monkeypatch.delenv("DARKWING_APPS_SCRIPT_URL", raising=False)
    # Ensure no .env file is found
    monkeypatch.setattr("pathlib.Path.exists", lambda self, *a, **k: False)
    with pytest.raises(OSError, match="DARKWING_APPS_SCRIPT_URL"):
        _get_apps_script_url()


# ── submit_record ─────────────────────────────────────────────────────────────

def test_submit_record_posts_to_webhook(sample_record, mock_env):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"status": "success", "response_id": "abc123"}
    mock_resp.raise_for_status.return_value = None

    with patch("darkwing.form_submit.requests.post", return_value=mock_resp) as mock_post:
        with patch("darkwing.form_submit.get_token", return_value="test-token"):
            result = submit_record(sample_record)

    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    assert args[0] == "https://script.google.com/macros/s/test/exec"
    assert kwargs["headers"] == {"Authorization": "Bearer test-token"}
    payload = kwargs["json"]
    assert payload["tower_id"] == "Tower 3"
    assert payload["adult_swallows_in_chimney"] == 2
    assert result == {"status": "success", "response_id": "abc123"}


def test_submit_record_raises_on_http_error(sample_record, mock_env):
    mock_resp = MagicMock()
    mock_resp.raise_for_status.side_effect = Exception("400 Bad Request")

    with patch("darkwing.form_submit.requests.post", return_value=mock_resp):
        with patch("darkwing.form_submit.get_token", return_value="test-token"):
            with pytest.raises(Exception, match="400"):
                submit_record(sample_record)


# ── submit_csv_records ────────────────────────────────────────────────────────

def test_submit_csv_records_dry_run(sample_record, mock_env):
    records = [sample_record]
    with patch("darkwing.form_submit.submit_record") as mock_submit:
        results = submit_csv_records(records, dry_run=True)
    mock_submit.assert_not_called()
    assert len(results) == 1
    assert results[0]["status"] == "dry-run"
    assert results[0]["tower"] == "Tower 3"


def test_submit_csv_records_real(sample_record, mock_env):
    records = [sample_record]
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"status": "success"}
    mock_resp.raise_for_status.return_value = None

    with patch("darkwing.form_submit.requests.post", return_value=mock_resp):
        with patch("darkwing.form_submit.get_token", return_value="token"):
            results = submit_csv_records(records, dry_run=False)
    assert len(results) == 1
    assert results[0]["status"] == "success"


def test_submit_csv_records_multiple(sample_record, mock_env):
    records = [sample_record, sample_record]
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"status": "success"}
    mock_resp.raise_for_status.return_value = None

    with patch("darkwing.form_submit.requests.post", return_value=mock_resp):
        with patch("darkwing.form_submit.get_token", return_value="token"):
            results = submit_csv_records(records, dry_run=False)
    assert len(results) == 2
    assert mock_resp.raise_for_status.call_count == 2
