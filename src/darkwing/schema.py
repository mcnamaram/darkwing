from __future__ import annotations

import json
import re
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


# ── Enums ──────────────────────────────────────────────────────────────────────

NestingStage = str  # constrained enum below
BillUse = str      # constrained enum below
AwakeStatus = str  # constrained enum below


# ── Short-code translation table ───────────────────────────────────────────────
# Keys are the *short* codes stored in the curated CSV; values are the
# long-form text the Google Form expects.
FLIGHTS_TRANSLATION: Dict[str, str] = {
    "yes_flew_in": "Yes, at least one adult flew into the chimney",
    "yes_flew_out": "Yes, at least one adult flew out of the chimney",
    "yes_both": "Yes, at least one adult flew in and at least one adult flew out",
    "no_flight": "No, no adult flew in or out of the chimney",
}

NESTING_STAGE_OPTIONS: List[str] = [
    "No nest",
    "Nest building",
    "Eggs",
    "Nestlings",
    "Fledglings",
]

BILL_USE_OPTIONS: List[str] = [
    "N/A or No",
    "Carrying nesting material",
    "Carrying food",
    "Both",
]

AWAKE_OPTIONS: List[str] = [
    "Yes",
    "No",
    "Unknown",
]


# ── ObservationRecord ──────────────────────────────────────────────────────────

class ObservationRecord(BaseModel):
    """A single chimney‑swift observation row, as stored in the curated CSV.

    The model validates the row in isolation.  ``csv_io`` is responsible for
    loading many rows; ``form_submit`` is responsible for translating them
    into the shape the Apps Script webhook expects.
    """

    # ── core identification ──────────────────────────────────────────────────
    date_str: str = Field(..., description="Date in M/D/YYYY or MM/DD/YYYY format")
    hour: int = Field(..., ge=0, le=23, description="Hour of day (0‑23)")
    minutes_past_hour: int = Field(..., ge=0, le=59, description="Minutes past the hour")
    tower: str = Field(..., description="Tower identifier, e.g. 'Tower 3'")
    num_adults: int = Field(..., ge=0, description="Number of adult swifts seen")
    nesting_stage: NestingStage = Field(..., description="Current nesting stage")
    bill_use: BillUse = Field(..., description="What the swifts are carrying, if anything")
    flights: List[str] = Field(default_factory=list, min_length=0, max_length=3, description="Short codes for flight activity")
    num_near_nest: int = Field(..., ge=0, description="Number of swifts near the nest")
    awake: AwakeStatus = Field(..., description="Whether the swifts appear awake")
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
        if v not in NESTING_STAGE_OPTIONS:
            raise ValueError(
                f"nesting_stage must be one of {NESTING_STAGE_OPTIONS!r}, got {v!r}"
            )
        return v

    @field_validator("bill_use")
    @classmethod
    def validate_bill_use(cls, v: str) -> str:
        if v not in BILL_USE_OPTIONS:
            raise ValueError(
                f"bill_use must be one of {BILL_USE_OPTIONS!r}, got {v!r}"
            )
        return v

    @field_validator("awake")
    @classmethod
    def validate_awake(cls, v: str) -> str:
        if v not in AWAKE_OPTIONS:
            raise ValueError(
                f"awake must be one of {AWAKE_OPTIONS!r}, got {v!r}"
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
        """Sanity check: minutes can't be negative."""
        if self.minutes_past_hour < 0:
            raise ValueError("minutes_past_hour must be >= 0")
        return self

    # ── computed helpers ─────────────────────────────────────────────────────

    @property
    def time_of_day(self) -> str:
        """Return 'HH:MM' for the observation time."""
        return f"{self.hour:02d}:{self.minutes_past_hour:02d}"

    @property
    def translation_table(self) -> Dict[str, str]:
        """The full short‑code → long‑form table (useful for tests / docs)."""
        return dict(FLIGHTS_TRANSLATION)

    def to_form_payload(self) -> Dict[str, object]:
        """Translate this record into the shape the Apps Script webhook expects."""
        expanded_flights = [
            FLIGHTS_TRANSLATION[code] for code in self.flights
        ]
        return {
            "date": self.date_str,
            "time_of_day": self.time_of_day,
            "tower_id": self.tower,
            "adult_swallows_in_chimney": self.num_adults,
            "nesting_stage": self.nesting_stage,
            "bill_use": self.bill_use,
            "adults_flew_in": expanded_flights,
            "swallows_near_nest": self.num_near_nest,
            "awake": self.awake,
            "notes": self.notes or "",
        }


# ── Convenience ────────────────────────────────────────────────────────────────

def parse_observation_row(row: Dict[str, str]) -> ObservationRecord:
    """Parse a dict from a CSV row into an ObservationRecord.

    All CSV values are strings; the model handles coercion.
    """
    return ObservationRecord.model_validate(row)
