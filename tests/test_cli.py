from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))

from darkwing.cli import main  # noqa: E402


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture
def sample_csv(sample_csv_path):
    """Return the path to the sample CSV fixture."""
    return sample_csv_path


@pytest.fixture
def mock_env(monkeypatch):
    monkeypatch.setenv("DARKWING_APPS_SCRIPT_URL", "https://script.google.com/macros/s/test/exec")


# ── validate subcommand ───────────────────────────────────────────────────────

def test_validate_success(sample_csv, monkeypatch, capsys):
    rc = main(["validate", str(sample_csv)])
    assert rc == 0
    captured = capsys.readouterr()
    assert "validated successfully" in captured.out
    assert str(sample_csv) in captured.out or "record" in captured.out.lower()


def test_validate_missing_file(capsys):
    rc = main(["validate", "/nonexistent/file.csv"])
    assert rc == 1
    captured = capsys.readouterr()
    assert "Validation failed" in captured.err


def test_validate_bad_csv(tmp_path, capsys):
    bad = tmp_path / "bad.csv"
    bad.write_text("date_str,hour\n2026-06-15,abc\n", encoding="utf-8")
    rc = main(["validate", str(bad)])
    assert rc == 1
    captured = capsys.readouterr()
    assert "Validation failed" in captured.err


# ── submit subcommand ─────────────────────────────────────────────────────────

def test_submit_dry_run(sample_csv, mock_env, monkeypatch, capsys):
    monkeypatch.setenv("DARKWING_APPS_SCRIPT_URL",
                       "https://script.google.com/macros/s/test/exec")
    rc = main(["submit", "--dry-run", str(sample_csv)])
    assert rc == 0
    captured = capsys.readouterr()
    assert "DRY RUN" in captured.out
    assert "submitted" in captured.out


def test_submit_real(sample_csv, mock_env, monkeypatch, capsys):
    monkeypatch.setenv("DARKWING_APPS_SCRIPT_URL",
                       "https://script.google.com/macros/s/test/exec")
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"status": "success"}
    mock_resp.raise_for_status.return_value = None

    with patch("darkwing.form_submit.requests.post", return_value=mock_resp):
        with patch("darkwing.form_submit.get_token", return_value="token"):
            rc = main(["submit", str(sample_csv)])

    assert rc == 0
    captured = capsys.readouterr()
    assert "submitted" in captured.out.lower()


def test_submit_missing_file(mock_env, capsys):
    rc = main(["submit", "/nonexistent/file.csv"])
    assert rc == 1
    captured = capsys.readouterr()
    assert "Failed to read CSV" in captured.err


# ── help ──────────────────────────────────────────────────────────────────────

def test_help(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0
    captured = capsys.readouterr()
    assert "darkwing" in captured.out
    assert "validate" in captured.out
    assert "submit" in captured.out
