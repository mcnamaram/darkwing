# System Architecture

## What this system is

DarkWing is a single-process Python package. It reads a CSV of curated observations, validates each row, expands short codes into the form's long-form text, and POSTs the rows one at a time to a Google Apps Script `doPost` webhook. The webhook constructs and submits Google Form responses on behalf of the authenticated user. A local JSON-Lines log file (`submitted_log.jsonl`) is the only artifact that persists between runs.

## Components

| Component | Path | Role |
| --- | --- | --- |
| Schema | `src/darkwing/schema.py` | Pydantic models and the short-code → form-text translation table. |
| CSV I/O | `src/darkwing/csv_io.py` | Reads the curated CSV; parses the `flights` column (semicolon-delimited short codes, e.g. `in;out`); appends to the submission log. |
| Auth | `src/darkwing/auth.py` | Retrieves a Google OAuth bearer token via `gcloud auth print-access-token`. Caches for 50 minutes. |
| Submit | `src/darkwing/form_submit.py` | Translates a record into form-ready JSON, POSTs it to the Apps Script URL with `Authorization: Bearer <token>`. |
| CLI | `src/darkwing/cli.py` | `darkwing {submit,validate} path/to/file.csv [--dry-run]`. |
| Apps Script | Owned by the user, hosted at `script.google.com` | Receives JSON, builds a `FormApp.createResponse()`, calls `.submit()`. Handles all form item types. |

The Python code owns the *content* of the submission — the field titles, the translation table, the validation. The Apps Script owns the *transport* — the `FormApp` API call that the user's authenticated session can make. This split keeps the script small and low-risk; if the form changes, the Python code changes; if the Apps Script API changes, the script changes.

## Data flow

```ascii
curated CSV
   │  one row per observation (45 rows per day per tower)
   │  columns: tower, date_str, hour, minutes_past_hour,
   │           num_adults, nesting_stage, bill_use, flights,
   │           num_near_nest, awake, notes
   ▼
csv_io.read_rows(path)
   │  parses flights (semicolon-delimited, e.g. `in;out`) into a list of short codes
   ▼
schema.ObservationRecord.model_validate(row)
   │  Pydantic v2; raises on violation
   ▼
record.to_form_payload(submitter_email, submitter_name)
   │  expands short codes via the translation table
   │  returns a flat dict: {form_title: value, ...}
   ▼
form_submit.submit_one(record, *, apps_script_url, token)
   │  POST application/json
   │  Authorization: Bearer <token>
   │  body = to_form_payload output
   ▼
Apps Script doPost
   │  FormApp.openById(FORM_ID).createResponse().submit()
   ▼
local append to ./submitted_log.jsonl
   │  one JSON line per attempt: {uuid, timestamp_utc, http_status, attempt_count, error?}
   ▼
Google Form responses sheet (eventual)
```

## CSV schema and translation table

The CSV has eleven columns. Five are short-code columns with fixed-value translation tables. Three are numeric. Two are text.

### Numeric columns

| Column | Type | Range / format | Notes |
| --- | --- | --- | --- |
| `hour` | int | `[0, 23]` | 24-hour clock. |
| `minutes_past_hour` | int | `[0, 59]` | Any integer. |
| `num_adults` | int | `≥ 0` | Free integer; the form allows up to 10 in the radio list and an "Other" freeform. |
| `num_near_nest` | int | `≥ 0` | Same shape as `num_adults`. |

### Text columns

| Column | Type | Notes |
| --- | --- | --- |
| `tower` | number | e.g. `3` would translate to `Tower 3`. Defaults from `DARKWING_DEFAULT_TOWER` if empty. |
| `date_str` | string | `M/D/YYYY`. Year in `[2024, 2030]`. |
| `notes` | string | Free text. May be empty. |

### Short-code columns

Codes are unique by *what they describe*, scoped by the column they appear in. A code may be reused across columns if the underlying value is the same in spirit (e.g. `egg` for "Eggs" in `nesting_stage` and `bill_use`), but each column has its own translation table.

**`nesting_stage`** (one of):

| Code | Form text |
| --- | --- |
| `no` | `No nest` |
| `bld` | `Nest building` |
| `egg` | `Egg(s) present but no nestlings` |
| `nst` | `Nestling(s) present` |
| `fld` | `Post-fledgling` |

**`bill_use`** (one of):

| Code | Form text |
| --- | --- |
| `na` | `N/A or No` |
| `mat` | `Yes, handling or placing a stick or nest material` |
| `fd` | `Yes, handling or feeding a bug or food item` |
| `egg` | `Yes, tending to eggs with its bill` |
| `nst` | `Yes, tending to nestling with its bill` |
| `ps` | `Yes, preening itself` |
| `po` | `Yes, preening another adult` |
| `oth` | `Other` |

**`flights`** (zero to three of):

| Code | Form text |
| --- | --- |
| `in` | `Yes, at least one adult flew into the chimney` |
| `out` | `Yes, at least one adult flew out of the chimney` |
| `chg` | `Yes, at least one adult changed position within the chimney but did not enter or exit` |
| `non` | `None of the above` |

The CSV stores this column as semicolon-delimited short codes, e.g. `in;chg`.

**`awake`** (one of):

| Code | Form text |
| --- | --- |
| `y` | `Yes` |
| `n` | `No` |
| `mbe` | `Maybe` |
| `nap` | `No adults present` |

### Sub-record identity (not a CSV column)

For every row, the system generates a `UUID` and a `TimestampUTC` (the time of the local submission attempt, in UTC). These are the deduplication key: a re-run of the same CSV will not re-submit a row whose `(UUID, TimestampUTC)` pair is already in `submitted_log.jsonl`. They are not on the form; they are for the local audit log.

## Design choices and their reasons

- **One POST per row, not one POST for the whole batch.** The form expects one response per submission; the Apps Script's `createResponse().submit()` model matches that 1:1.
- **Short codes on the wire to the user, full text on the wire to the form.** The CSV is the user-facing surface; the JSON payload is the form-facing surface. The translation lives in the Python code and is testable in isolation.
- **`gcloud auth print-access-token` over `google-auth` library.** One subprocess call; no project, no service account, no OAuth client. Migrating to the library is a small change if the volume or the user count grows.
- **Append-only JSONL log, not a SQLite database.** Resumability needs a "what's already done" record. JSONL gives that with no dependency and no schema migration.
- **No CSV mutation.** The curated CSV is treated as read-only. Submission state lives in `submitted_log.jsonl`.
- **Schema lives in the Python package, not in the form.** The form's titles are the contract, but the Python code owns the field definitions and the translation table. If the form changes, `schema.py` changes with it and tests catch the drift.
- **Logic shifts left to Python.** The Apps Script is a thin pass-through wrapper that builds a `FormApp.createResponse()` from the JSON the Python code sends. The Python code does the title lookup, the type coercion, the date splitting, the translation-table expansion. This keeps the script simple and low-risk; a future "switch to the Google Forms API" change touches only the script, not the Python code.

## Auth and session lifecycle

The bearer token is retrieved by shelling out to `gcloud auth print-access-token`. The token is short-lived (60 minutes); the package caches it for 50 minutes. On a 401 response, the package invalidates the cache, refetches the token, and retries once. A second 401 stops the batch with a clear error.

The token is *never* logged, *never* written to disk. The `submitted_log.jsonl` records only the row UUID, the timestamp, and the HTTP status.

## What is not yet built

The following are scoped but not implemented in MVP1. Each is a future plan.

- **Video download** (MVP2). A wrapper around `reolinkapi.Camera` that downloads a day's worth of 20-minute playback segments given a camera IP, user, password, and date.
- **Detection** (MVP3). Scan a 20-minute segment for an adult swift. If found at any second in the `[0, 19]` minute span, log the minute-start timestamp as the capture window. If not found by minute 19, log a "no swifts" row. Detection is stubbed in MVP3; the user supplies the detection logic.
- **Review UI** (MVP4). A notebook or small web app that lists pending rows and lets the user Approve / Skip / Edit before submission. May be deployed as a Docker image.
