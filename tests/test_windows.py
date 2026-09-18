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

# ── Mutant-killing tests for windows.py ──────────────────────────────────────
# Entries 49-51: windows.py:38, 42, ... - bitshift and operator misuse

# Entry 49: windows.py:38 - bitshift misuse for start minute
def test_window_start_minute_not_bitshift():
    """Mutant: bitshift misuse — start_minute calculation should use arithmetic not >>."""
    from darkwing import windows as win
    from darkwing.windows import WindowId
    
    # Test WindowId start_minute property
    w = WindowId(tower=3, date="06/15/2026", hour=6, minute=0)
    # start_minute should be hour*60 + minute = 360 for hour=6, minute=0
    assert w.start_minute == 360, f"Expected start_minute=360 for hour=6 minute=0, got {w.start_minute}"
    
    # Test with minute=20
    w2 = WindowId(tower=3, date="06/15/2026", hour=6, minute=20)
    # start_minute should be 380 (6*60 + 20)
    assert w2.start_minute == 380, f"Expected start_minute=380 for hour=6 minute=20, got {w2.start_minute}"
    
    # Test with minute=40
    w3 = WindowId(tower=3, date="06/15/2026", hour=6, minute=40)
    assert w3.start_minute == 400, f"Expected start_minute=400 for hour=6 minute=40, got {w3.start_minute}"

# Entry 50: windows.py:42 - complex operator misuse in time calculation
def test_iter_windows_correct_time_calculation():
    """Mutant: operator misuse — iter_windows should produce correct window IDs."""
    from darkwing import windows as win
    
    # Test iter_windows produces correct number of windows
    # Hours 6..21 inclusive = 16 hours, 3 windows per hour (minutes 0, 20, 40)
    # Total = 16 * 3 = 48 windows
    ws = win.iter_windows(tower=3, date="06/15/2026")
    assert len(ws) == 48, f"Expected 48 windows, got {len(ws)}"
    
    # Test window IDs have correct format
    for w in ws:
        assert w.window_id.startswith("T3_"), f"Window ID should start with T3_, got {w.window_id}"
        # minute should be 0, 20, or 40
        assert w.minute in (0, 20, 40), f"Minute should be 0, 20, or 40, got {w.minute}"
    
    # Test first and last window
    assert ws[0].hour == 6 and ws[0].minute == 0, \
        f"First window should be hour 6, minute 0, got hour={ws[0].hour}, minute={ws[0].minute}"
    assert ws[-1].hour == 21 and ws[-1].minute == 40, \
        f"Last window should be hour 21, minute 40, got hour={ws[-1].hour}, minute={ws[-1].minute}"

# Entry 51: windows.py: ... - additional operator misuse
def test_resume_keys_and_pending():
    """Mutant: operator misuse — resume and pending window calculations should be correct."""
    from darkwing import windows as win
    from pathlib import Path
    import tempfile
    
    # Test resume_keys
    m = Path(tempfile.mkstemp(suffix='.jsonl')[1])
    win.append_result(m, {"window_id": "T3_06152026_0600", "verdict": "skip"})
    win.append_result(m, {"window_id": "T3_06152026_0620", "verdict": "review"})
    keys = win.resume_keys(m)
    assert keys == {"T3_06152026_0600", "T3_06152026_0620"}, \
        f"Expected specific keys, got {keys}"
    
    # Test pending_windows
    all_windows = win.iter_windows(tower=3, date="06/15/2026", hours=range(6, 7))
    done = {"T3_06152026_0600"}
    pending = win.pending_windows(all_windows, done)
    # Should have 3 windows minus 1 done = 2 pending
    assert len(pending) == 2, f"Expected 2 pending windows, got {len(pending)}"
    # Pending should not include the done window
    assert all(w.window_id not in done for w in pending)
