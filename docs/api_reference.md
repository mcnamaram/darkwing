# API Reference

> Last updated: 2026-08-15. Python API for the `darkwing` package.

## Package layout

```sh
darkwing/
├── __init__.py
├── cli.py           # command-line entry points
├── csv_io.py        # CSV and log I/O
├── form_submit.py   # Playwright browser automation
└── schema.py        # Pydantic models + translation tables
```

---

## `darkwing.schema`

### Translation tables (dicts)

Used to expand CSV short codes into Google Form answer text.

```python
from darkwing.schema import (
    FLIGHTS_TRANSLATION,
    NESTING_STAGE_CODE_TO_TEXT,
    BILL_USE_CODE_TO_TEXT,
    AWAKE_CODE_TO_TEXT,
    NUM_NEAR_NEST_CODE_TO_TEXT,
)
```

| Table | Keys → Values |
| --- | --- |
| `FLIGHTS_TRANSLATION` | `in` → "Yes, at least one adult flew into the chimney", `out` → "Yes, at least one adult flew out…", `chg` → "…changed position…", `non` → "None of the above" |
| `NESTING_STAGE_CODE_TO_TEXT` | `no` → "No nest", `bld` → "Nest building", `egg` → "Egg(s) present but no nestlings", `nst` → "Nestling(s) present", `fld` → "Post-fledgling" |
| `BILL_USE_CODE_TO_TEXT` | `na` → "N/A or No", `mat` → "Yes, handling or placing a stick…", `fd` → "…feeding a bug…", `egg` → "…tending to eggs…", `nst` → "…nestling…", `ps` → "…preening itself", `po` → "…preening another adult", `oth` → "Other" |
| `NUM_NEAR_NEST_CODE_TO_TEXT` | `na` → "N/A or Zero", `oth` → "Other" |
| `AWAKE_CODE_TO_TEXT` | `y` → "Yes", `n` → "No", `mbe` → "Maybe", `nap` → "No adults present" |

### ObservationRecord (Pydantic model)

```python
from darkwing.schema import ObservationRecord

rec = ObservationRecord.model_validate({
    "tower": "3",
    "date_str": "6/15/2026",
    "hour": "6",
    "minutes_past_hour": "0",
    "num_adults": "2",
    "nesting_stage": "no",
    "bill_use": ["na"],
    "flights": "non",           # string or list of codes
    "num_near_nest": "1",
    "awake": "y",
    "notes": "test note",
})
```

Fields:

| Field | Type | Notes |
| --- | --- | --- |
| `tower` | `int` | Tower number (1-4) |
| `date_str` | `str` | `M/D/YYYY` |
| `hour` | `int` | 0-23 |
| `minutes_past_hour` | `int` | 0, 20, 40 (or 0-59) |
| `num_adults` | `int` | 0-5+ |
| `num_adults_other` | `str \| None` | "Other response" free text |
| `nesting_stage` | `str` | short code |
| `bill_use` | `list[str]` | short codes |
| `flights` | `list[str]` | short codes |
| `num_near_nest` | `int` | 0+ |
| `num_near_nest_other` | `str \| None` | — |
| `awake` | `str` | short code |
| `notes` | `str \| None` | optional |

Useful helpers:

- `rec.time_of_day` — "06:00" formatted from hour+minutes
- `rec.to_form_payload()` — dict of CSV codes (legacy; used by no current code)

---

## `darkwing/csv_io`

```python
from darkwing.csv_io import read_csv, write_submission_log

records = read_csv(Path("observations.csv"))      # -> list[ObservationRecord]
write_submission_log(records, results)            # -> appends JSONL
```

- `read_csv(path)` — parses CSV, validates each row, returns records. Raises on bad rows.
- `write_submission_log(records, results, log_path=...)` — appends one JSON line per record: `{record, status, error, timestamp}`.

---

## `darkwing/form_submit`

```python
from darkwing.form_submit import submit_csv_records

results = asyncio.run(submit_csv_records(records, dry_run=True))
# or, from the CLI:
#   darkwing submit obs.csv --dry-run
```

### `submit_csv_records(records, dry_run=False) -> list[dict]`

Submit a list of records. Returns one dict per record:

```python
{
    "record": ObservationRecord,
    "status": "success" | "dry-run" | "error",
    "error": None | str,
}
```

`dry_run=True` never launches a browser.

### `load_form() -> (playwright, context)`

Launches Chromium with a **persistent context**:

- profile dir: `google_profile/` (project root)
- user agent: Chrome/126 macOS
- anti-bot: `--disable-blink-features=AutomationControlled`, `--enable-automation` removed
- `slow_mo=500`
- headless from `DARKWING_HEADLESS` (default `true`)

### `unload_form(p, context)`

Closes the context and stops Playwright. Call in a `finally` block.

### `submit_observation(...) -> bool`

Low-level: fill one record into an already-open page. Returns `True` on success. Parameters mirror `ObservationRecord` fields (expanded text via translation tables).

---

## `darkwing/cli`

```sh
darkwing validate <csv> [--dry-run]
darkwing submit   <csv> [--dry-run]
```

| Command | Exit codes |
| --- | --- |
| `validate` | 0 = valid, 1 = errors |
| `submit` | 0 = all records ok, 1 = fatal |
