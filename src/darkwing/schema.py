from __future__ import annotations

import json
import re
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


# ── Short-code → long-form translation tables ────────────────────────────────
# Keys are the *short* codes stored in the curated CSV; values are the
# long-form text the Google Form expects.

FLIGHTS_TRANSLATION: Dict[str, str] = {
    "in": "Yes, at least one adult flew into the chimney",
    "out": "Yes, at least one adult flew out of the chimney",
    "chg": "Yes, at least one adult changed position within the chimney but did not enter or exit",
    "non": "None of the above",
}

NESTING_STAGE_CODE_TO_TEXT: Dict[str, str] = {
    "no":   "No nest",
    "bld":  "Nest building",
    "egg":  "Egg(s) present but no nestlings",
    "nst":  "Nestling(s) present",
    "fld":  "Post-fledgling",
}

BILL_USE_CODE_TO_TEXT: Dict[str, str] = {
    "na": "N/A or No",
    "mat": "Yes, handling or placing a stick or nest material",
    "fd": "Yes, handling or feeding a bug or food item",
    "egg": "Yes, tending to eggs with its bill",
    "nst": "Yes, tending to nestling with its bill",
    "ps": "Yes, preening itself",
    "po": "Yes, preening another adult",
    "oth": "Other",
}

AWAKE_CODE_TO_TEXT: Dict[str, str] = {
    "y":   "Yes",
    "n":   "No",
    "mbe": "Maybe",
    "nap": "No adults present",
}

# Reverse maps for validation (code → allowed set)
NESTING_STAGE_CODES = set(NESTING_STAGE_CODE_TO_TEXT.keys())
BILL_USE_CODES = set(BILL_USE_CODE_TO_TEXT.keys())
AWAKE_CODES = set(AWAKE_CODE_TO_TEXT.keys())


# ── ObservationRecord ──────────────────────────────────────────────────────────

class ObservationRecord(BaseModel):
    """A single chimney‑swift observation row, as stored in the curated CSV.

    The model validates the row in isolation.  ``csv_io`` is responsible for
    loading many rows; ``form_submit`` is responsible for translating them
    into the shape the Apps Script webhook expects.

    Short-code columns (nesting_stage, bill_use, awake, flights) store the
    short code internally but ``to_form_payload()`` expands them to the
    long-form text the Google Form expects.
    """

    # ── core identification ──────────────────────────────────────────────────
    date_str: str = Field(..., description="Date in M/D/YYYY or MM/DD/YYYY format")
    hour: int = Field(..., ge=0, le=23, description="Hour of day (0‑23)")
    minutes_past_hour: int = Field(..., ge=0, le=59, description="Minutes past the hour")
    tower: str = Field(..., description="Tower identifier, e.g. 'Tower 3'")
    num_adults: int = Field(..., ge=0, description="Number of adult swifts seen")
    nesting_stage: str = Field(..., description="Short code for nesting stage (see NESTING_STAGE_CODE_TO_TEXT)")
    bill_use: str = Field(..., description="Short code for bill use (see BILL_USE_CODE_TO_TEXT)")
    flights: List[str] = Field(default_factory=list, min_length=0, max_length=3, description="Short codes for flight activity")
    num_near_nest: int = Field(..., ge=0, description="Number of swifts near the nest")
    awake: str = Field(..., description="Short code for awake status (see AWAKE_CODE_TO_TEXT)")
    notes: Optional[str] = Field(None, description="Free‑form notes")

    # ── validators ───────────────────────────────────────────────────────────

    @field_validator("tower")
    @classmethod
    def validate_tower(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("tower must not be empty after stripping whitespace")
        return v

    @field_validator("date_str")
    @classmethod
    def parse_date_str(cls, v: str) -> str:
        """Accept M/D/YYYY or MM/DD/YYYY; normalise to MM/DD/YYYY."""
        m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", v)
        if not m:
            raise ValueError(f"date_str must match M/D/YYYY or MM/DD/YYYY, got {v!r}")
        month, day, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if not (1 <= month <= 12 and 1 <= day <= 31):
            raise ValueError(f"Invalid month/day in date_str: {v!r}")
        return f"{month:02d}/{day:02d}/{year}"

    @field_validator("nesting_stage")
    @classmethod
    def validate_nesting_stage(cls, v: str) -> str:
        if v not in NESTING_STAGE_CODES:
            raise ValueError(
                f"nesting_stage must be one of {sorted(NESTING_STAGE_CODES)}, got {v!r}"
            )
        return v

    @field_validator("bill_use")
    @classmethod
    def validate_bill_use(cls, v: str) -> str:
        if v not in BILL_USE_CODES:
            raise ValueError(
                f"bill_use must be one of {sorted(BILL_USE_CODES)}, got {v!r}"
            )
        return v

    @field_validator("awake")
    @classmethod
    def validate_awake(cls, v: str) -> str:
        if v not in AWAKE_CODES:
            raise ValueError(
                f"awake must be one of {sorted(AWAKE_CODES)}, got {v!r}"
            )
        return v

    @field_validator("flights", mode="before")
    @classmethod
    def parse_flights(cls, v):
        """Accept a JSON string (from CSV) or a native list."""
        if isinstance(v, str):
            v = json.loads(v)
        return v

    @field_validator("flights")
    @classmethod
    def validate_flights(cls, v: List[str]) -> List[str]:
        valid_keys = set(FLIGHTS_TRANSLATION.keys())
        bad = [item for item in v if item not in valid_keys]
        if bad:
            raise ValueError(
                f"flights entries must be short codes from {sorted(valid_keys)}, got {bad!r}"
            )
        return v

    @model_validator(mode="after")
    def check_minutes_nonnegative(self) -> "ObservationRecord":
        if self.minutes_past_hour < 0:
            raise ValueError("minutes_past_hour must be >= 0")
        return self

    # ── computed helpers ─────────────────────────────────────────────────────

    @property
    def time_of_day(self) -> str:
        """Return 'HH:MM' for the observation time."""
        return f"{self.hour:02d}:{self.minutes_past_hour:02d}"

    @property
    def translation_table(self) -> Dict[str, Dict[str, str]]:
        """Return all short-code → long-form translation tables."""
        return {
            "flights": dict(FLIGHTS_TRANSLATION),
            "nesting_stage": dict(NESTING_STAGE_CODE_TO_TEXT),
            "bill_use": dict(BILL_USE_CODE_TO_TEXT),
            "awake": dict(AWAKE_CODE_TO_TEXT),
        }

    def _expand(self, code: str, table: Dict[str, str]) -> str:
        """Expand a single short code to its long-form text."""
        return table[code]

    def to_form_payload(self) -> Dict[str, object]:
        """Translate this record into the shape the Apps Script webhook expects."""
        return {
            "date": self.date_str,
            "time_of_day": self.time_of_day,
            "tower_id": self.tower,
            "adult_swallows_in_chimney": self.num_adults,
            "nesting_stage": self._expand(self.nesting_stage, NESTING_STAGE_CODE_TO_TEXT),
            "bill_use": self._expand(self.bill_use, BILL_USE_CODE_TO_TEXT),
            "adults_flew_in": [
                FLIGHTS_TRANSLATION[code] for code in self.flights
            ],
            "swallows_near_nest": self.num_near_nest,
            "awake": self._expand(self.awake, AWAKE_CODE_TO_TEXT),
            "notes": self.notes or "",
        }


# ── Convenience ────────────────────────────────────────────────────────────────

def parse_observation_row(row: Dict[str, str]) -> ObservationRecord:
    """Parse a dict from a CSV row into an ObservationRecord.

    All CSV values are strings; the model handles coercion.
    """
    return ObservationRecord.model_validate(row)
