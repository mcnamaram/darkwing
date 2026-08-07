from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))

from darkwing.schema import (  # noqa: E402
    AWAKE_OPTIONS,
    BILL_USE_OPTIONS,
    FLIGHTS_TRANSLATION,
    NESTING_STAGE_OPTIONS,
    ObservationRecord,
    parse_observation_row,
)


# ── Fixture row (the one from the plan) ───────────────────────────────────────

@pytest.fixture
def valid_row_dict() -> dict:
    return {
        "date_str": "6/15/2026",
        "hour": "6",
        "minutes_past_hour": "0",
        "tower": "Tower 3",
        "num_adults": "2",
        "nesting_stage": "No nest",
        "bill_use": "N/A or No",
        "flights": '["yes_flew_in"]',
        "num_near_nest": "1",
        "awake": "Yes",
        "notes": "1 north, 1 west. west moved to north",
    }


@pytest.fixture
def valid_record(valid_row_dict) -> ObservationRecord:
    return ObservationRecord.model_validate(valid_row_dict)


# ── 1. Minimal valid record parses ───────────────────────────────────────────

def test_minimal_valid_record_parses(valid_record: ObservationRecord):
    assert valid_record.hour == 6
    assert valid_record.date_str == "06/15/2026"
    assert valid_record.tower == "Tower 3"


# ── 2. date_str format ────────────────────────────────────────────────────────

def test_date_str_single_digit_month_day(valid_row_dict, valid_record):
    assert valid_record.date_str == "06/15/2026"

def test_date_str_double_digit_month_day():
    r = ObservationRecord.model_validate({
        "date_str": "12/05/2026",
        "hour": "18", "minutes_past_hour": "0",
        "tower": "Tower 1", "num_adults": "0",
        "nesting_stage": "No nest", "bill_use": "N/A or No",
        "flights": "[]", "num_near_nest": "0",
        "awake": "Yes", "notes": None,
    })
    assert r.date_str == "12/05/2026"

def test_date_str_bad_format_rejected():
    with pytest.raises(ValueError, match="date_str"):
        ObservationRecord.model_validate({
            "date_str": "2026-06-15",
            "hour": "6", "minutes_past_hour": "0",
            "tower": "Tower 1", "num_adults": "0",
            "nesting_stage": "No nest", "bill_use": "N/A or No",
            "flights": "[]", "num_near_nest": "0",
            "awake": "Yes", "notes": None,
        })

def test_date_str_invalid_month_rejected():
    with pytest.raises(ValueError, match="date_str"):
        ObservationRecord.model_validate({
            "date_str": "13/01/2026",
            "hour": "6", "minutes_past_hour": "0",
            "tower": "Tower 1", "num_adults": "0",
            "nesting_stage": "No nest", "bill_use": "N/A or No",
            "flights": "[]", "num_near_nest": "0",
            "awake": "Yes", "notes": None,
        })


# ── 3. hour range ─────────────────────────────────────────────────────────────

def test_hour_zero_allowed():
    r = ObservationRecord.model_validate({
        "date_str": "6/15/2026",
        "hour": "0", "minutes_past_hour": "0",
        "tower": "Tower 1", "num_adults": "0",
        "nesting_stage": "No nest", "bill_use": "N/A or No",
        "flights": "[]", "num_near_nest": "0",
        "awake": "Yes", "notes": None,
    })
    assert r.hour == 0

def test_hour_twentythree_allowed():
    r = ObservationRecord.model_validate({
        "date_str": "6/15/2026",
        "hour": "23", "minutes_past_hour": "0",
        "tower": "Tower 1", "num_adults": "0",
        "nesting_stage": "No nest", "bill_use": "N/A or No",
        "flights": "[]", "num_near_nest": "0",
        "awake": "Yes", "notes": None,
    })
    assert r.hour == 23

def test_hour_out_of_range_rejected():
    with pytest.raises(ValueError, match="hour"):
        ObservationRecord.model_validate({
            "date_str": "6/15/2026",
            "hour": "24", "minutes_past_hour": "0",
            "tower": "Tower 1", "num_adults": "0",
            "nesting_stage": "No nest", "bill_use": "N/A or No",
            "flights": "[]", "num_near_nest": "0",
            "awake": "Yes", "notes": None,
        })


# ── 4. minutes_past_hour ──────────────────────────────────────────────────────

def test_minutes_zero_allowed():
    r = ObservationRecord.model_validate({
        "date_str": "6/15/2026",
        "hour": "6", "minutes_past_hour": "0",
        "tower": "Tower 1", "num_adults": "0",
        "nesting_stage": "No nest", "bill_use": "N/A or No",
        "flights": "[]", "num_near_nest": "0",
        "awake": "Yes", "notes": None,
    })
    assert r.minutes_past_hour == 0

def test_minutes_fiftynine_allowed():
    r = ObservationRecord.model_validate({
        "date_str": "6/15/2026",
        "hour": "6", "minutes_past_hour": "59",
        "tower": "Tower 1", "num_adults": "0",
        "nesting_stage": "No nest", "bill_use": "N/A or No",
        "flights": "[]", "num_near_nest": "0",
        "awake": "Yes", "notes": None,
    })
    assert r.minutes_past_hour == 59

def test_minutes_out_of_range_rejected():
    with pytest.raises(ValueError, match="minutes_past_hour"):
        ObservationRecord.model_validate({
            "date_str": "6/15/2026",
            "hour": "6", "minutes_past_hour": "60",
            "tower": "Tower 1", "num_adults": "0",
            "nesting_stage": "No nest", "bill_use": "N/A or No",
            "flights": "[]", "num_near_nest": "0",
            "awake": "Yes", "notes": None,
        })


# ── 5. tower non-empty ────────────────────────────────────────────────────────

def test_tower_empty_rejected():
    with pytest.raises(ValueError, match="tower"):
        ObservationRecord.model_validate({
            "date_str": "6/15/2026",
            "hour": "6", "minutes_past_hour": "0",
            "tower": "",
            "num_adults": "0", "nesting_stage": "No nest",
            "bill_use": "N/A or No", "flights": "[]",
            "num_near_nest": "0", "awake": "Yes", "notes": None,
        })

def test_tower_whitespace_only_rejected():
    with pytest.raises(ValueError, match="tower"):
        ObservationRecord.model_validate({
            "date_str": "6/15/2026",
            "hour": "6", "minutes_past_hour": "0",
            "tower": "   ",
            "num_adults": "0", "nesting_stage": "No nest",
            "bill_use": "N/A or No", "flights": "[]",
            "num_near_nest": "0", "awake": "Yes", "notes": None,
        })


# ── 6. nesting_stage enum ─────────────────────────────────────────────────────

@pytest.mark.parametrize("stage", NESTING_STAGE_OPTIONS)
def test_nesting_stage_valid(stage: str):
    r = ObservationRecord.model_validate({
        "date_str": "6/15/2026", "hour": "6", "minutes_past_hour": "0",
        "tower": "Tower 1", "num_adults": "0",
        "nesting_stage": stage, "bill_use": "N/A or No",
        "flights": "[]", "num_near_nest": "0",
        "awake": "Yes", "notes": None,
    })
    assert r.nesting_stage == stage

def test_nesting_stage_invalid_rejected():
    with pytest.raises(ValueError, match="nesting_stage"):
        ObservationRecord.model_validate({
            "date_str": "6/15/2026", "hour": "6", "minutes_past_hour": "0",
            "tower": "Tower 1", "num_adults": "0",
            "nesting_stage": "Unknown stage", "bill_use": "N/A or No",
            "flights": "[]", "num_near_nest": "0",
            "awake": "Yes", "notes": None,
        })


# ── 7. bill_use enum ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("bu", BILL_USE_OPTIONS)
def test_bill_use_valid(bu: str):
    r = ObservationRecord.model_validate({
        "date_str": "6/15/2026", "hour": "6", "minutes_past_hour": "0",
        "tower": "Tower 1", "num_adults": "0",
        "nesting_stage": "No nest", "bill_use": bu,
        "flights": "[]", "num_near_nest": "0",
        "awake": "Yes", "notes": None,
    })
    assert r.bill_use == bu

def test_bill_use_invalid_rejected():
    with pytest.raises(ValueError, match="bill_use"):
        ObservationRecord.model_validate({
            "date_str": "6/15/2026", "hour": "6", "minutes_past_hour": "0",
            "tower": "Tower 1", "num_adults": "0",
            "nesting_stage": "No nest", "bill_use": "Holding a twig",
            "flights": "[]", "num_near_nest": "0",
            "awake": "Yes", "notes": None,
        })


# ── 8. flights list (short codes → expansion) ─────────────────────────────────

def test_flights_empty_list():
    r = ObservationRecord.model_validate({
        "date_str": "6/15/2026", "hour": "6", "minutes_past_hour": "0",
        "tower": "Tower 1", "num_adults": "0",
        "nesting_stage": "No nest", "bill_use": "N/A or No",
        "flights": "[]", "num_near_nest": "0",
        "awake": "Yes", "notes": None,
    })
    assert r.flights == []

def test_flights_single_code():
    r = ObservationRecord.model_validate({
        "date_str": "6/15/2026", "hour": "6", "minutes_past_hour": "0",
        "tower": "Tower 1", "num_adults": "0",
        "nesting_stage": "No nest", "bill_use": "N/A or No",
        "flights": '["yes_flew_in"]',
        "num_near_nest": "0", "awake": "Yes", "notes": None,
    })
    assert r.flights == ["yes_flew_in"]

def test_flights_three_codes():
    r = ObservationRecord.model_validate({
        "date_str": "6/15/2026", "hour": "6", "minutes_past_hour": "0",
        "tower": "Tower 1", "num_adults": "0",
        "nesting_stage": "No nest", "bill_use": "N/A or No",
        "flights": '["yes_flew_in","yes_flew_out","yes_both"]',
        "num_near_nest": "0", "awake": "Yes", "notes": None,
    })
    assert len(r.flights) == 3

def test_flights_four_codes_rejected():
    with pytest.raises(ValueError, match="flights"):
        ObservationRecord.model_validate({
            "date_str": "6/15/2026", "hour": "6", "minutes_past_hour": "0",
            "tower": "Tower 1", "num_adults": "0",
            "nesting_stage": "No nest", "bill_use": "N/A or No",
            "flights": '["a","b","c","d"]',
            "num_near_nest": "0", "awake": "Yes", "notes": None,
        })

def test_flights_invalid_code_rejected():
    with pytest.raises(ValueError, match="flights"):
        ObservationRecord.model_validate({
            "date_str": "6/15/2026", "hour": "6", "minutes_past_hour": "0",
            "tower": "Tower 1", "num_adults": "0",
            "nesting_stage": "No nest", "bill_use": "N/A or No",
            "flights": '["bad_code"]',
            "num_near_nest": "0", "awake": "Yes", "notes": None,
        })


# ── 9. num_near_nest non-negative ─────────────────────────────────────────────

def test_num_near_nest_zero_allowed():
    r = ObservationRecord.model_validate({
        "date_str": "6/15/2026", "hour": "6", "minutes_past_hour": "0",
        "tower": "Tower 1", "num_adults": "0",
        "nesting_stage": "No nest", "bill_use": "N/A or No",
        "flights": "[]", "num_near_nest": "0",
        "awake": "Yes", "notes": None,
    })
    assert r.num_near_nest == 0

def test_num_near_nest_negative_rejected():
    with pytest.raises(ValueError, match="num_near_nest"):
        ObservationRecord.model_validate({
            "date_str": "6/15/2026", "hour": "6", "minutes_past_hour": "0",
            "tower": "Tower 1", "num_adults": "0",
            "nesting_stage": "No nest", "bill_use": "N/A or No",
            "flights": "[]", "num_near_nest": "-1",
            "awake": "Yes", "notes": None,
        })


# ── 10. awake enum ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("aw", AWAKE_OPTIONS)
def test_awake_valid(aw: str):
    r = ObservationRecord.model_validate({
        "date_str": "6/15/2026", "hour": "6", "minutes_past_hour": "0",
        "tower": "Tower 1", "num_adults": "0",
        "nesting_stage": "No nest", "bill_use": "N/A or No",
        "flights": "[]", "num_near_nest": "0",
        "awake": aw, "notes": None,
    })
    assert r.awake == aw

def test_awake_invalid_rejected():
    with pytest.raises(ValueError, match="awake"):
        ObservationRecord.model_validate({
            "date_str": "6/15/2026", "hour": "6", "minutes_past_hour": "0",
            "tower": "Tower 1", "num_adults": "0",
            "nesting_stage": "No nest", "bill_use": "N/A or No",
            "flights": "[]", "num_near_nest": "0",
            "awake": "Maybe", "notes": None,
        })


# ── 11. num_adults non-negative ───────────────────────────────────────────────

def test_num_adults_zero_allowed():
    r = ObservationRecord.model_validate({
        "date_str": "6/15/2026", "hour": "6", "minutes_past_hour": "0",
        "tower": "Tower 1", "num_adults": "0",
        "nesting_stage": "No nest", "bill_use": "N/A or No",
        "flights": "[]", "num_near_nest": "0",
        "awake": "Yes", "notes": None,
    })
    assert r.num_adults == 0

def test_num_adults_negative_rejected():
    with pytest.raises(ValueError, match="num_adults"):
        ObservationRecord.model_validate({
            "date_str": "6/15/2026", "hour": "6", "minutes_past_hour": "0",
            "tower": "Tower 1", "num_adults": "-1",
            "nesting_stage": "No nest", "bill_use": "N/A or No",
            "flights": "[]", "num_near_nest": "0",
            "awake": "Yes", "notes": None,
        })


# ── 12. notes optional ────────────────────────────────────────────────────────

def test_notes_none_allowed():
    r = ObservationRecord.model_validate({
        "date_str": "6/15/2026", "hour": "6", "minutes_past_hour": "0",
        "tower": "Tower 1", "num_adults": "0",
        "nesting_stage": "No nest", "bill_use": "N/A or No",
        "flights": "[]", "num_near_nest": "0",
        "awake": "Yes", "notes": None,
    })
    assert r.notes is None

def test_notes_string_allowed():
    r = ObservationRecord.model_validate({
        "date_str": "6/15/2026", "hour": "6", "minutes_past_hour": "0",
        "tower": "Tower 1", "num_adults": "0",
        "nesting_stage": "No nest", "bill_use": "N/A or No",
        "flights": "[]", "num_near_nest": "0",
        "awake": "Yes", "notes": "something happened",
    })
    assert r.notes == "something happened"


# ── 13. time_of_day property ──────────────────────────────────────────────────

def test_time_of_day(valid_record: ObservationRecord):
    assert valid_record.time_of_day == "06:00"

def test_time_of_day_nonzero_minutes():
    r = ObservationRecord.model_validate({
        "date_str": "6/15/2026", "hour": "18", "minutes_past_hour": "30",
        "tower": "Tower 1", "num_adults": "0",
        "nesting_stage": "No nest", "bill_use": "N/A or No",
        "flights": "[]", "num_near_nest": "0",
        "awake": "Yes", "notes": None,
    })
    assert r.time_of_day == "18:30"


# ── 14. translation_table ─────────────────────────────────────────────────────

def test_translation_table_keys():
    r = ObservationRecord.model_validate({
        "date_str": "6/15/2026", "hour": "6", "minutes_past_hour": "0",
        "tower": "Tower 1", "num_adults": "0",
        "nesting_stage": "No nest", "bill_use": "N/A or No",
        "flights": "[]", "num_near_nest": "0",
        "awake": "Yes", "notes": None,
    })
    table = r.translation_table
    assert "yes_flew_in" in table
    assert "no_flight" in table
    assert table["yes_flew_in"] == "Yes, at least one adult flew into the chimney"


# ── 15. to_form_payload ───────────────────────────────────────────────────────

def test_to_form_payload_expands_flights(valid_record: ObservationRecord, apps_script_payload: dict):
    payload = valid_record.to_form_payload()
    # The fixture row has one flight code → one expanded string
    assert payload["adults_flew_in"] == [
        "Yes, at least one adult flew into the chimney"
    ]
    assert payload["date"] == "06/15/2026"
    assert payload["time_of_day"] == "06:00"
    assert payload["tower_id"] == "Tower 3"
    assert payload["adult_swallows_in_chimney"] == 2
    assert payload["notes"] == "1 north, 1 west. west moved to north"

def test_to_form_payload_empty_flights():
    r = ObservationRecord.model_validate({
        "date_str": "6/15/2026", "hour": "6", "minutes_past_hour": "0",
        "tower": "Tower 1", "num_adults": "0",
        "nesting_stage": "No nest", "bill_use": "N/A or No",
        "flights": "[]", "num_near_nest": "0",
        "awake": "Yes", "notes": "hello",
    })
    payload = r.to_form_payload()
    assert payload["adults_flew_in"] == []
    assert payload["notes"] == "hello"

def test_to_form_payload_notes_none_becomes_empty_string():
    r = ObservationRecord.model_validate({
        "date_str": "6/15/2026", "hour": "6", "minutes_past_hour": "0",
        "tower": "Tower 1", "num_adults": "0",
        "nesting_stage": "No nest", "bill_use": "N/A or No",
        "flights": "[]", "num_near_nest": "0",
        "awake": "Yes", "notes": None,
    })
    payload = r.to_form_payload()
    assert payload["notes"] == ""


# ── 16. parse_observation_row helper ──────────────────────────────────────────

def test_parse_observation_row(valid_row_dict):
    r = parse_observation_row(valid_row_dict)
    assert isinstance(r, ObservationRecord)
    assert r.hour == 6
