from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))

from darkwing.schema import (  # noqa: E402
    AWAKE_CODE_TO_TEXT,
    BILL_USE_CODE_TO_TEXT,
    FLIGHTS_TRANSLATION,
    NESTING_STAGE_CODE_TO_TEXT,
    ObservationRecord,
    parse_observation_row,
)


# ── Fixture row (matches tests/fixtures/sample_observation.csv) ──────────────

@pytest.fixture
def valid_row_dict() -> dict:
    return {
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
        "notes": "1 north, 1 west. west moved to north",
    }


@pytest.fixture
def valid_record(valid_row_dict) -> ObservationRecord:
    return ObservationRecord.model_validate(valid_row_dict)


@pytest.fixture
def apps_script_payload() -> dict:
    """What form_submit expects to POST to the Apps Script webhook."""
    return {
        "date": "06/15/2026",
        "time_of_day": "06:00",
        "tower_id": "Tower 3",
        "adult_swallows_in_chimney": 2,
        "nesting_stage": "No nest",
        "bill_use": "N/A or No",
        "adults_flew_in": ["Yes, at least one adult flew into the chimney"],
        "swallows_near_nest": 1,
        "awake": "Yes",
        "notes": "1 north, 1 west. west moved to north",
    }


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
        "nesting_stage": "no", "bill_use": "na",
        "flights": "[]", "num_near_nest": "0",
        "awake": "y", "notes": None,
    })
    assert r.date_str == "12/05/2026"

def test_date_str_bad_format_rejected():
    with pytest.raises(ValueError, match="date_str"):
        ObservationRecord.model_validate({
            "date_str": "2026-06-15",
            "hour": "6", "minutes_past_hour": "0",
            "tower": "Tower 1", "num_adults": "0",
            "nesting_stage": "no", "bill_use": "na",
            "flights": "[]", "num_near_nest": "0",
            "awake": "y", "notes": None,
        })

def test_date_str_invalid_month_rejected():
    with pytest.raises(ValueError, match="date_str"):
        ObservationRecord.model_validate({
            "date_str": "13/01/2026",
            "hour": "6", "minutes_past_hour": "0",
            "tower": "Tower 1", "num_adults": "0",
            "nesting_stage": "no", "bill_use": "na",
            "flights": "[]", "num_near_nest": "0",
            "awake": "y", "notes": None,
        })


# ── 3. hour range ─────────────────────────────────────────────────────────────

def test_hour_zero_allowed():
    r = ObservationRecord.model_validate({
        "date_str": "6/15/2026",
        "hour": "0", "minutes_past_hour": "0",
        "tower": "Tower 1", "num_adults": "0",
        "nesting_stage": "no", "bill_use": "na",
        "flights": "[]", "num_near_nest": "0",
        "awake": "y", "notes": None,
    })
    assert r.hour == 0

def test_hour_twentythree_allowed():
    r = ObservationRecord.model_validate({
        "date_str": "6/15/2026",
        "hour": "23", "minutes_past_hour": "0",
        "tower": "Tower 1", "num_adults": "0",
        "nesting_stage": "no", "bill_use": "na",
        "flights": "[]", "num_near_nest": "0",
        "awake": "y", "notes": None,
    })
    assert r.hour == 23

def test_hour_out_of_range_rejected():
    with pytest.raises(ValueError, match="hour"):
        ObservationRecord.model_validate({
            "date_str": "6/15/2026",
            "hour": "24", "minutes_past_hour": "0",
            "tower": "Tower 1", "num_adults": "0",
            "nesting_stage": "no", "bill_use": "na",
            "flights": "[]", "num_near_nest": "0",
            "awake": "y", "notes": None,
        })


# ── 4. minutes_past_hour ──────────────────────────────────────────────────────

def test_minutes_zero_allowed():
    r = ObservationRecord.model_validate({
        "date_str": "6/15/2026",
        "hour": "6", "minutes_past_hour": "0",
        "tower": "Tower 1", "num_adults": "0",
        "nesting_stage": "no", "bill_use": "na",
        "flights": "[]", "num_near_nest": "0",
        "awake": "y", "notes": None,
    })
    assert r.minutes_past_hour == 0

def test_minutes_fiftynine_allowed():
    r = ObservationRecord.model_validate({
        "date_str": "6/15/2026",
        "hour": "6", "minutes_past_hour": "59",
        "tower": "Tower 1", "num_adults": "0",
        "nesting_stage": "no", "bill_use": "na",
        "flights": "[]", "num_near_nest": "0",
        "awake": "y", "notes": None,
    })
    assert r.minutes_past_hour == 59

def test_minutes_out_of_range_rejected():
    with pytest.raises(ValueError, match="minutes_past_hour"):
        ObservationRecord.model_validate({
            "date_str": "6/15/2026",
            "hour": "6", "minutes_past_hour": "60",
            "tower": "Tower 1", "num_adults": "0",
            "nesting_stage": "no", "bill_use": "na",
            "flights": "[]", "num_near_nest": "0",
            "awake": "y", "notes": None,
        })


# ── 5. tower non-empty ────────────────────────────────────────────────────────

def test_tower_empty_rejected():
    with pytest.raises(ValueError, match="tower"):
        ObservationRecord.model_validate({
            "date_str": "6/15/2026",
            "hour": "6", "minutes_past_hour": "0",
            "tower": "",
            "num_adults": "0", "nesting_stage": "no",
            "bill_use": "na", "flights": "[]",
            "num_near_nest": "0", "awake": "y", "notes": None,
        })

def test_tower_whitespace_only_rejected():
    with pytest.raises(ValueError, match="tower"):
        ObservationRecord.model_validate({
            "date_str": "6/15/2026",
            "hour": "6", "minutes_past_hour": "0",
            "tower": "   ",
            "num_adults": "0", "nesting_stage": "no",
            "bill_use": "na", "flights": "[]",
            "num_near_nest": "0", "awake": "y", "notes": None,
        })


# ── 6. nesting_stage codes ────────────────────────────────────────────────────

@pytest.mark.parametrize("code,expected", [
    ("no",   "No nest"),
    ("bld",  "Nest building"),
    ("egg",  "Egg(s) present but no nestlings"),
    ("nst",  "Nestling(s) present"),
    ("fld",  "Post-fledgling"),
])
def test_nesting_stage_valid(code: str, expected: str):
    r = ObservationRecord.model_validate({
        "date_str": "6/15/2026", "hour": "6", "minutes_past_hour": "0",
        "tower": "Tower 1", "num_adults": "0",
        "nesting_stage": code, "bill_use": "na",
        "flights": "[]", "num_near_nest": "0",
        "awake": "y", "notes": None,
    })
    assert r.nesting_stage == code  # stores short code
    # to_form_payload expands it
    assert r.to_form_payload()["nesting_stage"] == expected

def test_nesting_stage_invalid_rejected():
    with pytest.raises(ValueError, match="nesting_stage"):
        ObservationRecord.model_validate({
            "date_str": "6/15/2026", "hour": "6", "minutes_past_hour": "0",
            "tower": "Tower 1", "num_adults": "0",
            "nesting_stage": "unknown", "bill_use": "na",
            "flights": "[]", "num_near_nest": "0",
            "awake": "y", "notes": None,
        })


# ── 7. bill_use codes ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("code,expected", [
    ("na",                        "N/A or No"),
    ("mat",                       "Yes, handling or placing a stick or nest material"),
    ("fd",                        "Yes, handling or feeding a bug or food item"),
    ("egg",                       "Yes, tending to eggs with its bill"),
    ("nst",                       "Yes, tending to nestling with its bill"),
    ("ps",                        "Yes, preening itself"),
    ("po",                        "Yes, preening another adult"),
    ("oth",                       "Other"),
])
def test_bill_use_valid(code: str, expected: str):
    r = ObservationRecord.model_validate({
        "date_str": "6/15/2026", "hour": "6", "minutes_past_hour": "0",
        "tower": "Tower 1", "num_adults": "0",
        "nesting_stage": "no", "bill_use": code,
        "flights": "[]", "num_near_nest": "0",
        "awake": "y", "notes": None,
    })
    assert r.bill_use == code
    assert r.to_form_payload()["bill_use"] == expected

def test_bill_use_invalid_rejected():
    with pytest.raises(ValueError, match="bill_use"):
        ObservationRecord.model_validate({
            "date_str": "6/15/2026", "hour": "6", "minutes_past_hour": "0",
            "tower": "Tower 1", "num_adults": "0",
            "nesting_stage": "no", "bill_use": "invalid_code",
            "flights": "[]", "num_near_nest": "0",
            "awake": "y", "notes": None,
        })


# ── 8. flights codes ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("code,expected", [
    ("in",  "Yes, at least one adult flew into the chimney"),
    ("out", "Yes, at least one adult flew out of the chimney"),
    ("chg", "Yes, at least one adult changed position within the chimney but did not enter or exit"),
    ("non", "None of the above"),
])
def test_flights_single_code(code: str, expected: str):
    r = ObservationRecord.model_validate({
        "date_str": "6/15/2026", "hour": "6", "minutes_past_hour": "0",
        "tower": "Tower 1", "num_adults": "0",
        "nesting_stage": "no", "bill_use": "na",
        "flights": json.dumps([code]),
        "num_near_nest": "0", "awake": "y", "notes": None,
    })
    assert r.flights == [code]
    assert r.to_form_payload()["adults_flew_in"] == [expected]

def test_flights_empty_list():
    r = ObservationRecord.model_validate({
        "date_str": "6/15/2026", "hour": "6", "minutes_past_hour": "0",
        "tower": "Tower 1", "num_adults": "0",
        "nesting_stage": "no", "bill_use": "na",
        "flights": "[]", "num_near_nest": "0",
        "awake": "y", "notes": None,
    })
    assert r.flights == []

def test_flights_multiple_codes():
    r = ObservationRecord.model_validate({
        "date_str": "6/15/2026", "hour": "6", "minutes_past_hour": "0",
        "tower": "Tower 1", "num_adults": "0",
        "nesting_stage": "no", "bill_use": "na",
        "flights": '["in","out"]',
        "num_near_nest": "0", "awake": "y", "notes": None,
    })
    assert r.flights == ["in", "out"]

def test_flights_three_codes():
    r = ObservationRecord.model_validate({
        "date_str": "6/15/2026", "hour": "6", "minutes_past_hour": "0",
        "tower": "Tower 1", "num_adults": "0",
        "nesting_stage": "no", "bill_use": "na",
        "flights": '["in","out","chg"]',
        "num_near_nest": "0", "awake": "y", "notes": None,
    })
    assert len(r.flights) == 3

def test_flights_four_codes_rejected():
    with pytest.raises(ValueError, match="flights"):
        ObservationRecord.model_validate({
            "date_str": "6/15/2026", "hour": "6", "minutes_past_hour": "0",
            "tower": "Tower 1", "num_adults": "0",
            "nesting_stage": "no", "bill_use": "na",
            "flights": '["in","out","chg","non"]',
            "num_near_nest": "0", "awake": "y", "notes": None,
        })

def test_flights_invalid_code_rejected():
    with pytest.raises(ValueError, match="flights"):
        ObservationRecord.model_validate({
            "date_str": "6/15/2026", "hour": "6", "minutes_past_hour": "0",
            "tower": "Tower 1", "num_adults": "0",
            "nesting_stage": "no", "bill_use": "na",
            "flights": '["bad_code"]',
            "num_near_nest": "0", "awake": "y", "notes": None,
        })


# ── 9. num_near_nest non-negative ─────────────────────────────────────────────

def test_num_near_nest_zero_allowed():
    r = ObservationRecord.model_validate({
        "date_str": "6/15/2026", "hour": "6", "minutes_past_hour": "0",
        "tower": "Tower 1", "num_adults": "0",
        "nesting_stage": "no", "bill_use": "na",
        "flights": "[]", "num_near_nest": "0",
        "awake": "y", "notes": None,
    })
    assert r.num_near_nest == 0

def test_num_near_nest_negative_rejected():
    with pytest.raises(ValueError, match="num_near_nest"):
        ObservationRecord.model_validate({
            "date_str": "6/15/2026", "hour": "6", "minutes_past_hour": "0",
            "tower": "Tower 1", "num_adults": "0",
            "nesting_stage": "no", "bill_use": "na",
            "flights": "[]", "num_near_nest": "-1",
            "awake": "y", "notes": None,
        })


# ── 10. awake codes ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("code,expected", [
    ("y",       "Yes"),
    ("n",       "No"),
    ("mbe",     "Maybe"),
    ("nap",     "No adults present"),
])
def test_awake_valid(code: str, expected: str):
    r = ObservationRecord.model_validate({
        "date_str": "6/15/2026", "hour": "6", "minutes_past_hour": "0",
        "tower": "Tower 1", "num_adults": "0",
        "nesting_stage": "no", "bill_use": "na",
        "flights": "[]", "num_near_nest": "0",
        "awake": code, "notes": None,
    })
    assert r.awake == code
    assert r.to_form_payload()["awake"] == expected

def test_awake_invalid_rejected():
    with pytest.raises(ValueError, match="awake"):
        ObservationRecord.model_validate({
            "date_str": "6/15/2026", "hour": "6", "minutes_past_hour": "0",
            "tower": "Tower 1", "num_adults": "0",
            "nesting_stage": "no", "bill_use": "na",
            "flights": "[]", "num_near_nest": "0",
            "awake": "unknown", "notes": None,
        })


# ── 11. num_adults non-negative ───────────────────────────────────────────────

def test_num_adults_zero_allowed():
    r = ObservationRecord.model_validate({
        "date_str": "6/15/2026", "hour": "6", "minutes_past_hour": "0",
        "tower": "Tower 1", "num_adults": "0",
        "nesting_stage": "no", "bill_use": "na",
        "flights": "[]", "num_near_nest": "0",
        "awake": "y", "notes": None,
    })
    assert r.num_adults == 0

def test_num_adults_negative_rejected():
    with pytest.raises(ValueError, match="num_adults"):
        ObservationRecord.model_validate({
            "date_str": "6/15/2026", "hour": "6", "minutes_past_hour": "0",
            "tower": "Tower 1", "num_adults": "-1",
            "nesting_stage": "no", "bill_use": "na",
            "flights": "[]", "num_near_nest": "0",
            "awake": "y", "notes": None,
        })


# ── 12. notes optional ────────────────────────────────────────────────────────

def test_notes_none_allowed():
    r = ObservationRecord.model_validate({
        "date_str": "6/15/2026", "hour": "6", "minutes_past_hour": "0",
        "tower": "Tower 1", "num_adults": "0",
        "nesting_stage": "no", "bill_use": "na",
        "flights": "[]", "num_near_nest": "0",
        "awake": "y", "notes": None,
    })
    assert r.notes is None

def test_notes_string_allowed():
    r = ObservationRecord.model_validate({
        "date_str": "6/15/2026", "hour": "6", "minutes_past_hour": "0",
        "tower": "Tower 1", "num_adults": "0",
        "nesting_stage": "no", "bill_use": "na",
        "flights": "[]", "num_near_nest": "0",
        "awake": "y", "notes": "something happened",
    })
    assert r.notes == "something happened"


# ── 13. time_of_day property ──────────────────────────────────────────────────

def test_time_of_day(valid_record: ObservationRecord):
    assert valid_record.time_of_day == "06:00"

def test_time_of_day_nonzero_minutes():
    r = ObservationRecord.model_validate({
        "date_str": "6/15/2026", "hour": "18", "minutes_past_hour": "30",
        "tower": "Tower 1", "num_adults": "0",
        "nesting_stage": "no", "bill_use": "na",
        "flights": "[]", "num_near_nest": "0",
        "awake": "y", "notes": None,
    })
    assert r.time_of_day == "18:30"


# ── 14. translation_table ─────────────────────────────────────────────────────

def test_translation_table_keys():
    r = ObservationRecord.model_validate({
        "date_str": "6/15/2026", "hour": "6", "minutes_past_hour": "0",
        "tower": "Tower 1", "num_adults": "0",
        "nesting_stage": "no", "bill_use": "na",
        "flights": "[]", "num_near_nest": "0",
        "awake": "y", "notes": None,
    })
    tables = r.translation_table
    assert "flights" in tables
    assert "nesting_stage" in tables
    assert "bill_use" in tables
    assert "awake" in tables
    assert tables["flights"]["in"] == "Yes, at least one adult flew into the chimney"
    assert tables["nesting_stage"]["no"] == "No nest"
    assert tables["bill_use"]["mat"] == "Yes, handling or placing a stick or nest material"
    assert tables["awake"]["mbe"] == "Maybe"


# ── 15. to_form_payload ───────────────────────────────────────────────────────

def test_to_form_payload_expands_all_codes(valid_record: ObservationRecord, apps_script_payload: dict):
    payload = valid_record.to_form_payload()
    assert payload["adults_flew_in"] == ["Yes, at least one adult flew into the chimney"]
    assert payload["date"] == "06/15/2026"
    assert payload["time_of_day"] == "06:00"
    assert payload["tower_id"] == "Tower 3"
    assert payload["adult_swallows_in_chimney"] == 2
    assert payload["nesting_stage"] == "No nest"
    assert payload["bill_use"] == "N/A or No"
    assert payload["awake"] == "Yes"
    assert payload["notes"] == "1 north, 1 west. west moved to north"

def test_to_form_payload_empty_flights():
    r = ObservationRecord.model_validate({
        "date_str": "6/15/2026", "hour": "6", "minutes_past_hour": "0",
        "tower": "Tower 1", "num_adults": "0",
        "nesting_stage": "no", "bill_use": "na",
        "flights": "[]", "num_near_nest": "0",
        "awake": "y", "notes": "hello",
    })
    payload = r.to_form_payload()
    assert payload["adults_flew_in"] == []
    assert payload["notes"] == "hello"

def test_to_form_payload_notes_none_becomes_empty_string():
    r = ObservationRecord.model_validate({
        "date_str": "6/15/2026", "hour": "6", "minutes_past_hour": "0",
        "tower": "Tower 1", "num_adults": "0",
        "nesting_stage": "no", "bill_use": "na",
        "flights": "[]", "num_near_nest": "0",
        "awake": "y", "notes": None,
    })
    payload = r.to_form_payload()
    assert payload["notes"] == ""

def test_to_form_payload_multi_flight_expansion():
    r = ObservationRecord.model_validate({
        "date_str": "6/15/2026", "hour": "6", "minutes_past_hour": "0",
        "tower": "Tower 1", "num_adults": "1",
        "nesting_stage": "egg", "bill_use": "mat",
        "flights": '["in","out"]',
        "num_near_nest": "2", "awake": "mbe", "notes": None,
    })
    payload = r.to_form_payload()
    assert payload["adults_flew_in"] == [
        "Yes, at least one adult flew into the chimney",
        "Yes, at least one adult flew out of the chimney",
    ]
    assert payload["nesting_stage"] == "Egg(s) present but no nestlings"
    assert payload["bill_use"] == "Yes, handling or placing a stick or nest material"
    assert payload["awake"] == "Maybe"


# ── 16. parse_observation_row helper ──────────────────────────────────────────

def test_parse_observation_row(valid_row_dict):
    r = parse_observation_row(valid_row_dict)
    assert isinstance(r, ObservationRecord)
    assert r.hour == 6
