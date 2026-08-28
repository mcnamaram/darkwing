"""Window segmentation + resume manifest tests."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from darkwing import windows as win


def test_iter_windows_count():
    ws = win.iter_windows(tower=3, date="06/15/2026")
    # hours 6..21 inclusive = 16 hours * 3 windows = 48
    assert len(ws) == 16 * 3
    assert all(w.tower == 3 for w in ws)
    assert ws[0].hour == 6 and ws[0].minute == 0
    assert ws[-1].hour == 21 and ws[-1].minute == 40


def test_window_id_format():
    w = win.WindowId(tower=3, date="06/15/2026", hour=6, minute=20)
    assert w.window_id == "T3_06152026_0620"


def test_iter_windows_rejects_out_of_range():
    with pytest.raises(ValueError):
        win.iter_windows(tower=3, date="06/15/2026", hours=[5])


def test_resume_keys_empty(tmp_path):
    assert win.resume_keys(tmp_path / "missing.jsonl") == set()


def test_resume_keys_and_append(tmp_path):
    m = tmp_path / "review_index.jsonl"
    win.append_result(m, {"window_id": "T3_06152026_0600", "verdict": "skip"})
    win.append_result(m, {"window_id": "T3_06152026_0620", "verdict": "review"})
    keys = win.resume_keys(m)
    assert keys == {"T3_06152026_0600", "T3_06152026_0620"}


def test_pending_windows_filters_done():
    ws = win.iter_windows(tower=3, date="06/15/2026", hours=range(6, 7))
    done = {"T3_06152026_0600"}
    pending = win.pending_windows(ws, done)
    assert all(w.window_id not in done for w in pending)
    assert len(pending) == len(ws) - 1
