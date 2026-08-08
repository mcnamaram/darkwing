# API Reference

This document describes the public interface of the `darkwing` package. The CLI is the user-facing API; the Python functions are exposed for scripting and testing.

## CLI

```
darkwing {validate,submit} path/to/file.csv [OPTIONS]
```

### `validate`

Reads and validates a CSV against the Pydantic schema. Prints a summary and exits 0 on success, 1 on error.

```bash
darkwing validate observations.csv
```

### `submit`

Validates, expands short codes, and POSTs each row to the Apps Script webhook.

```bash
darkwing submit observations.csv                  # submit for real
darkwing submit observations.csv --dry-run        # preview only
```

### `--help`

```bash
darkwing --help
darkwing validate --help
darkwing submit --help
```

## Python API

### `darkwing.schema.ObservationRecord`

```python
from darkwing.schema import ObservationRecord

# Validate a row dict (e.g. from csv.DictReader)
record = ObservationRecord.model_validate({
    "tower": "3",
    "date_str": "6/15/2026",
    "hour": "6",
    "minutes_past_hour": "0",
    "num_adults": "2",
    "nesting_stage": "no",
    "bill_use": "na",
    "flights": "in;chg",           # semicolon-delimited
    "num_near_nest": "1",
    "awake": "y",
    "notes": "1 north, 1 west",
})

# Expand to form payload
payload = record.to_form_payload()
# {
#   "tower_id": "Tower 3",
#   "date": "06/15/2026",
#   "time_of_day": "06:00",
#   "adult_swallows_in_chimney": 2,
#   "nesting_stage": "No nest",
#   "bill_use": "N/A or No",
#   "adults_flew_in": ["Yes, at least one adult flew into the chimney"],
#   "swallows_near_nest": 1,
#   "awake": "Yes",
#   "notes": "1 north, 1 west",
# }
```

### `darkwing.csv_io`

```python
from darkwing.csv_io import read_csv, write_submission_log, get_submission_log
from pathlib import Path

# Read and validate
records = read_csv(Path("observations.csv"))

# Append to submission log
write_submission_log(records, Path("submitted_log.jsonl"))

# Read log back
log = get_submission_log(Path("submitted_log.jsonl"))
```

### `darkwing.form_submit`

```python
from darkwing.form_submit import submit_record, submit_csv_records

# Submit one record
result = submit_record(record)
# {"uuid": "...", "status": "success", ...}

# Submit many records
results = submit_csv_records(records, dry_run=False)
```

### `darkwing.auth`

```python
from darkwing.auth import get_token

token = get_token()  # returns cached token or refreshes from gcloud
```

## Short-code translation tables

These constants are exported from `darkwing.schema` for reference:

| Constant | Type | Values |
|---|---|---|
| `FLIGHTS_TRANSLATION` | `Dict[str, str]` | `in`, `out`, `chg`, `non` |
| `NESTING_STAGE_CODE_TO_TEXT` | `Dict[str, str]` | `no`, `bld`, `egg`, `nst`, `fld` |
| `BILL_USE_CODE_TO_TEXT` | `Dict[str, str]` | `na`, `mat`, `fd`, `egg`, `nst`, `ps`, `po`, `oth` |
| `AWAKE_CODE_TO_TEXT` | `Dict[str, str]` | `y`, `n`, `mbe`, `nap` |
