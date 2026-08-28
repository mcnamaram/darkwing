"""CLI `detect` smoke test — uses synthetic source (no hardware, plan R7)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from darkwing.cli import main


def test_detect_synthetic(tmp_path, capsys):
    out = tmp_path / "footage"
    rc = main([
        "detect",
        "--date", "06/15/2026",
        "--tower", "3",
        "--source", "synthetic",
        "--hours", "6", "7",
        "--glare-hours", "12",
        "--out-dir", str(out),
    ])
    assert rc == 0
    manifest = out / "06/15/2026" / "tower3" / "review_index.jsonl"
    assert manifest.exists()
    lines = [json.loads(l) for l in manifest.read_text().splitlines() if l.strip()]
    assert len(lines) == 6  # 2 hours * 3 windows
    verdicts = {r["window_id"]: r["verdict"] for r in lines}
    # hour 6 & 7 are not glare hours -> SKIP (no blobs in synthetic default)
    assert all(v == "skip" for v in verdicts.values())


def test_detect_resume_skips_done(tmp_path, capsys):
    out = tmp_path / "footage"
    main([
        "detect", "--date", "06/15/2026", "--tower", "3",
        "--source", "synthetic", "--hours", "6", "6", "--out-dir", str(out),
    ])
    # re-run same; should report nothing pending
    rc = main([
        "detect", "--date", "06/15/2026", "--tower", "3",
        "--source", "synthetic", "--hours", "6", "6", "--out-dir", str(out),
    ])
    assert rc == 0
    captured = capsys.readouterr()
    assert "Nothing to do" in captured.out
