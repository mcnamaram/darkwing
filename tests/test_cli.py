from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))

from darkwing.cli import main  # noqa: E402


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _isolate_cwd(tmp_path, monkeypatch):
    """Run every CLI test in a scratch dir so submitted_log.jsonl never
    lands in the repo root."""
    monkeypatch.chdir(tmp_path)
    return tmp_path

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
    monkeypatch.setenv("DARKWING_FORM_URL",
                       "https://docs.google.com/forms/d/test")
    rc = main(["submit", "--dry-run", str(sample_csv)])
    assert rc == 0
    captured = capsys.readouterr()
    assert "would be submitted" in captured.out.lower()
    assert "submitted" in captured.out.lower()


def test_submit_dry_run_writes_no_log(sample_csv, mock_env, monkeypatch,
                                      capsys, tmp_path):
    """Dry-run must never touch submitted_log.jsonl."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DARKWING_FORM_URL",
                       "https://docs.google.com/forms/d/test")
    rc = main(["submit", "--dry-run", str(sample_csv)])
    assert rc == 0
    assert not (tmp_path / "submitted_log.jsonl").exists()


def _patch_browser_success():
    """Context-manager stack mocking a fully successful browser run."""
    from unittest.mock import AsyncMock
    import contextlib

    @contextlib.contextmanager
    def _cm():
        with patch("darkwing.form_submit.load_form",
                   new=AsyncMock(return_value=(MagicMock(), MagicMock()))):
            with patch("darkwing.form_submit.submit_observation",
                       new=AsyncMock(return_value=True)):
                with patch("darkwing.form_submit.unload_form",
                           new=AsyncMock()):
                    with patch("darkwing.form_submit.clear_form",
                               new=AsyncMock()):
                        yield

    return _cm()


def test_submit_real(sample_csv, mock_env, monkeypatch, capsys, tmp_path):
    monkeypatch.chdir(tmp_path)
    with _patch_browser_success():
        rc = main(["submit", str(sample_csv)])
    assert rc == 0
    captured = capsys.readouterr()
    assert "submitted" in captured.out.lower()


def test_submit_writes_submission_log(sample_csv, mock_env, monkeypatch,
                                      capsys, tmp_path):
    """Every real submit appends one log line per record."""
    import json
    monkeypatch.chdir(tmp_path)
    with _patch_browser_success():
        rc = main(["submit", str(sample_csv)])
    assert rc == 0
    log_path = tmp_path / "submitted_log.jsonl"
    assert log_path.exists()
    entries = [json.loads(line)
               for line in log_path.read_text().splitlines()]
    assert len(entries) == 4  # sample fixture has 4 rows
    assert all(e["status"] == "success" for e in entries)
    assert all(e["timestamp"] for e in entries)
    assert all("tower" in e["record"] for e in entries)


def test_submit_resume_skips_logged_records(sample_csv, mock_env, monkeypatch,
                                            capsys, tmp_path):
    """Re-running after success submits nothing new."""
    import json
    from unittest.mock import AsyncMock
    monkeypatch.chdir(tmp_path)
    with _patch_browser_success():
        main(["submit", str(sample_csv)])

    # Second run: browser must not even launch — patch to explode if it does.
    with patch("darkwing.form_submit.load_form",
               new=AsyncMock(side_effect=AssertionError("browser launched"))):
        rc = main(["submit", str(sample_csv)])
    assert rc == 0
    captured = capsys.readouterr()
    assert "already submitted" in captured.out
    # Log unchanged (still 4 lines).
    lines = (tmp_path / "submitted_log.jsonl").read_text().splitlines()
    assert len(lines) == 4


def test_submit_resume_retries_failed_records(sample_csv, mock_env,
                                              monkeypatch, capsys, tmp_path):
    """Failed records are not marked done; re-run retries only those."""
    import asyncio
    from unittest.mock import AsyncMock
    monkeypatch.chdir(tmp_path)

    # First run: all records fail.
    with patch("darkwing.form_submit.load_form",
               new=AsyncMock(return_value=(MagicMock(), MagicMock()))):
        with patch("darkwing.form_submit.submit_observation",
                   new=AsyncMock(side_effect=Exception("down"))):
            with patch("darkwing.form_submit.unload_form", new=AsyncMock()):
                with patch("darkwing.form_submit.clear_form", new=AsyncMock()):
                    rc = main(["submit", str(sample_csv)])
    assert rc == 1  # partial failure now exits non-zero
    log_path = tmp_path / "submitted_log.jsonl"
    # No log file should be created because no records succeeded
    assert not log_path.exists()

    # Second run: browser succeeds; all 4 rows retried.
    with _patch_browser_success():
        rc = main(["submit", str(sample_csv)])
    assert rc == 0
    captured = capsys.readouterr()
    assert "Submitting 4 record(s)" in captured.out


def test_submit_no_resume_flag_submits_all(sample_csv, mock_env, monkeypatch,
                                           capsys, tmp_path):
    """--no-resume re-submits rows already in the log."""
    monkeypatch.chdir(tmp_path)
    with _patch_browser_success():
        main(["submit", str(sample_csv)])
    with _patch_browser_success():
        rc = main(["submit", "--no-resume", str(sample_csv)])
    assert rc == 0
    captured = capsys.readouterr()
    assert "Submitting 4 record(s)" in captured.out
    lines = (tmp_path / "submitted_log.jsonl").read_text().splitlines()
    assert len(lines) == 8


def test_submit_partial_failure_exit_code(sample_csv, mock_env, monkeypatch,
                                          capsys, tmp_path):
    """Some failures → non-zero exit and a retry hint."""
    from unittest.mock import AsyncMock

    calls = {"n": 0}

    async def flaky(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] <= 2:
            return True
        raise Exception("boom")

    monkeypatch.chdir(tmp_path)
    with patch("darkwing.form_submit.load_form",
               new=AsyncMock(return_value=(MagicMock(), MagicMock()))):
        with patch("darkwing.form_submit.submit_observation", new=flaky):
            with patch("darkwing.form_submit.unload_form", new=AsyncMock()):
                with patch("darkwing.form_submit.clear_form", new=AsyncMock()):
                    rc = main(["submit", str(sample_csv)])
    assert rc == 1
    captured = capsys.readouterr()
    assert "failed" in captured.out
    assert "Re-run" in captured.out


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
