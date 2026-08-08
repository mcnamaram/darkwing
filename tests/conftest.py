from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Dict, List

import pytest


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
FIXTURES_ROOT = PROJECT_ROOT / "tests" / "fixtures"

# Ensure `darkwing` is importable from tests regardless of cwd
sys.path.insert(0, str(SRC_ROOT))


# ── CSV fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture
def sample_csv_path() -> Path:
    return FIXTURES_ROOT / "sample_observation.csv"


@pytest.fixture
def sample_csv_rows() -> List[Dict[str, str]]:
    """A tiny hand-curated observation CSV (no header) as a list of row dicts."""
    return [
        {
            "tower": "3",
            "date_str": "6/15/2026",
            "hour": "6",
            "minutes_past_hour": "0",
            "num_adults": "2",
            "nesting_stage": "No nest",
            "bill_use": "N/A or No",
            "flights": '["Yes, at least one adult flew into the chimney"]',
            "num_near_nest": "1",
            "awake": "Yes",
            "notes": "1 north, 1 west. west moved to north",
        }
    ]


# ── App-script payloads ────────────────────────────────────────────────────────

@pytest.fixture
def apps_script_payload() -> Dict:
    """What form_submit expects to POST to the Apps Script webhook."""
    return {
        "tower_id": "Tower 3",
        "date": "6/15/2026",
        "time_of_day": "6:00",
        "adult_swallows_in_chimney": 2,
        "nesting_stage": "No nest",
        "bill_use": "N/A or No",
        "adults_flew_in": [
            "Yes, at least one adult flew into the chimney"
        ],
        "swallows_near_nest": 1,
        "awake": "Yes",
        "notes": "1 north, 1 west. west moved to north",
    }


# ── Helper: load fixture CSV ──────────────────────────────────────────────────

def load_fixture_csv(name: str) -> Path:
    path = FIXTURES_ROOT / name
    if not path.exists():
        raise FileNotFoundError(f"Fixture not found: {path}")
    return path
