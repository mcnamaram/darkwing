from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))

from darkwing.auth import get_token, _load_cache, _save_cache  # noqa: E402


# ── helpers ────────────────────────────────────────────────────────────────────

@pytest.fixture
def cache_file(tmp_path: Path):
    """Point auth module at a temp cache file for testing."""
    import darkwing.auth as auth_mod
    original = auth_mod._CACHE_FILE
    auth_mod._CACHE_FILE = tmp_path / "token_cache.json"
    yield auth_mod._CACHE_FILE
    auth_mod._CACHE_FILE = original


# ── test_get_token_shells_out_to_gcloud ───────────────────────────────────────

def test_get_token_shells_out_to_gcloud(cache_file: Path):
    """First call invokes subprocess.run and returns the token."""
    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_proc.stdout = "ya29.test-token\n"
    mock_proc.stderr = ""

    with patch("darkwing.auth.subprocess.run", return_value=mock_proc) as mock_run:
        token = get_token()

    mock_run.assert_called_once_with(
        ["gcloud", "auth", "print-access-token"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert token == "ya29.test-token"


def test_get_token_strips_trailing_whitespace(cache_file: Path):
    mock_proc = MagicMock(returncode=0, stdout="  ya29.token  \n", stderr="")
    with patch("darkwing.auth.subprocess.run", return_value=mock_proc):
        token = get_token()
    assert token == "ya29.token"


def test_get_token_empty_output_raises(cache_file: Path):
    mock_proc = MagicMock(returncode=0, stdout="\n", stderr="")
    with patch("darkwing.auth.subprocess.run", return_value=mock_proc):
        with pytest.raises(RuntimeError, match="empty token"):
            get_token()


def test_get_token_nonzero_exit_raises(cache_file: Path):
    mock_proc = MagicMock(returncode=1, stdout="", stderr="error")
    mock_proc.check_returncode.side_effect = Exception("gcloud failed")
    with patch("darkwing.auth.subprocess.run", return_value=mock_proc):
        with pytest.raises(Exception):
            get_token()


# ── caching: 50-minute window ─────────────────────────────────────────────────

def test_cached_token_returned_within_50_minutes(cache_file: Path):
    """Second call within 50 min returns cached token, no subprocess call."""
    import darkwing.auth as auth_mod
    auth_mod._save_cache("cached-token")

    with patch("darkwing.auth.subprocess.run") as mock_run:
        token = get_token()

    mock_run.assert_not_called()
    assert token == "cached-token"


def test_cache_miss_after_51_minutes(cache_file: Path):
    """Token older than 50 min is discarded; gcloud is called again."""
    import darkwing.auth as auth_mod
    import time
    # Simulate an old cache entry (51 minutes ago)
    auth_mod._CACHE_FILE.write_text(json.dumps({
        "token": "old-token",
        "acquired_at": time.time() - 51 * 60,
    }))

    mock_proc = MagicMock(returncode=0, stdout="fresh-token\n", stderr="")
    with patch("darkwing.auth.subprocess.run", return_value=mock_proc) as mock_run:
        token = get_token()

    mock_run.assert_called_once()
    assert token == "fresh-token"


def test_corrupt_cache_file_treated_as_miss(cache_file: Path):
    cache_file.write_text("not valid json{{{")
    mock_proc = MagicMock(returncode=0, stdout="new-token\n", stderr="")
    with patch("darkwing.auth.subprocess.run", return_value=mock_proc) as mock_run:
        token = get_token()
    mock_run.assert_called_once()
    assert token == "new-token"


def test_missing_cache_file_triggers_gcloud(cache_file: Path):
    """No cache file → gcloud is called."""
    if cache_file.exists():
        cache_file.unlink()
    mock_proc = MagicMock(returncode=0, stdout="fresh-token\n", stderr="")
    with patch("darkwing.auth.subprocess.run", return_value=mock_proc) as mock_run:
        token = get_token()
    mock_run.assert_called_once()
    assert token == "fresh-token"
    # cache file was created
    assert cache_file.exists()
