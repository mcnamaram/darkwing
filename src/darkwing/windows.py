"""MVP2 window segmentation + resume manifest.

The observation protocol defines 20-minute windows starting at the top of
each hour from 06:00 - 21:00 (per protocol, hours 6..21). Each window is
identified by (tower, date, hour, minute) where minute is 0 or 20 or 40
within that hour — but the canonical observation unit is the 20-min window
itself, keyed by (tower, date, hour, window_index).

This module is pure: it produces WindowId dataclasses and a manifest with
append/resume semantics (reused from MVP1 submit log pattern, plan R3).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Set

# Protocol: targeted hours 6..21, windows of WINDOW_MIN minutes.
OBSERVATION_HOURS: range = range(6, 22)
WINDOW_MIN = 20
WINDOWS_PER_HOUR = 60 // WINDOW_MIN  # 3 (minutes 0, 20, 40)


@dataclass(frozen=True)
class WindowId:
    tower: int
    date: str          # MM/DD/YYYY
    hour: int
    minute: int        # 0, 20, 40

    @property
    def window_id(self) -> str:
        return f"T{self.tower}_{self.date.replace('/', '')}_{self.hour:02d}{self.minute:02d}"

    @property
    def start_minute(self) -> int:
        return self.hour * 60 + self.minute

    def range_seconds(self, clip_start_hour: int) -> Tuple[int, int]:
        """Absolute (start, end) seconds within a clip that begins at clip_start_hour."""
        base = (self.hour - clip_start_hour) * 3600 + self.minute * 60
        return base, base + WINDOW_MIN * 60


def iter_windows(tower: int, date: str,
                 hours: Iterable[int] = OBSERVATION_HOURS) -> List[WindowId]:
    out: List[WindowId] = []
    for h in sorted(hours):
        if h not in OBSERVATION_HOURS:
            raise ValueError(f"hour {h} outside observation range {OBSERVATION_HOURS}")
        for w in range(WINDOWS_PER_HOUR):
            out.append(WindowId(tower=tower, date=date, hour=h, minute=w * WINDOW_MIN))
    return out


def resume_keys(manifest_path: Path) -> Set[str]:
    """Load already-completed window keys from a JSONL manifest."""
    keys: Set[str] = set()
    if not manifest_path.exists():
        return keys
    for line in manifest_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        wid = obj.get("window_id")
        if wid:
            keys.add(wid)
    return keys


def append_result(manifest_path: Path, record: Dict) -> None:
    """Append one window result as a JSONL line (resume-safe)."""
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with manifest_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, default=str) + "\n")


def pending_windows(all_windows: Iterable[WindowId],
                    done: Set[str]) -> List[WindowId]:
    return [w for w in all_windows if w.window_id not in done]


# re-export for callers that import the alias used in plan text
from typing import Tuple  # noqa: E402
