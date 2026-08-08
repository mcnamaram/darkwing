# Test Strategy

This document describes how the system is validated. The strategy is deliberately modest: MVP1 is a small system and the tests should match.

## Goals

1. **Every schema rule is covered by at least one test.** A form change that breaks a field's validation should be caught by a failing test, not by a 4xx response in production.
2. **The submission code path is exercised against a mocked HTTP boundary, not a real one.** The real Apps Script is exercised by the human in the tutorial; CI does not depend on it.
3. **The auth code path is exercised against a mocked `gcloud` CLI, not a real one.** Same reasoning.
4. **Coverage is ≥ 90% on `src/darkwing/`.** The CLI is a thin wrapper exercised by the integration tests.

## What is in the suite

### `tests/test_schema.py` — the Golden Schema

One test per rule, with a positive case and (where applicable) a negative case.

- `flights` accepts semicolon-delimited short codes (`in`, `in;out`) and legacy JSON arrays (`["in"]`) for backwards compatibility.
- `flights` is a list of 0–3 strings, each from the form's four enum values (`in`, `out`, `chg`, `non`).
- `date_str` matches `M/D/YYYY` (e.g. `6/15/2026`) and is normalised to `MM/DD/YYYY`.
- `hour` is an integer in `[0, 23]`.
- `minutes_past_hour` is an integer in `[0, 59]`.
- `num_adults` is a non-negative integer.
- `nesting_stage` is one of the form's five enum codes (`no`, `bld`, `egg`, `nst`, `fld`).
- `bill_use` is one of the form's eight enum codes (`na`, `mat`, `fd`, `egg`, `nst`, `ps`, `po`, `oth`).
- `awake` is one of the form's four enum codes (`y`, `n`, `mbe`, `nap`).
- `notes` is a string (may be empty).

### `tests/test_csv_io.py` — CSV I/O

- `read_csv` yields one `ObservationRecord` per non-empty data line.
- `read_csv` parses semicolon-delimited `flights` values correctly.
- `read_csv` raises a single `ValueError` with per-row details when any row fails validation.
- `write_submission_log` appends JSON lines to a file.
- `get_submission_log` reads the file back.

### `tests/test_form_submit.py` — HTTP submission

- `submit_record` POSTs to the Apps Script URL with the correct `Authorization: Bearer` header.
- `submit_record` expands short codes via `to_form_payload()`.
- `submit_csv_records` posts each record individually and returns a list of results.
- `--dry-run` skips the POST and returns mock results.

### `tests/test_auth.py` — OAuth token

- `get_token` calls `gcloud auth print-access-token` and caches the result for 50 minutes.
- Expired tokens are refreshed on demand.

### `tests/test_cli.py` — CLI entry point

- `darkwing validate <csv>` returns 0 for valid input, 1 for invalid.
- `darkwing submit <csv> --dry-run` prints rows without making HTTP calls.
- `darkwing submit <csv>` calls the submission code path.
- `darkwing --help` exits 0 and prints usage.

## Test data

The fixture `tests/fixtures/sample_observation.csv` is a real CSV with four rows covering common cases: single flight, multiple flights, empty flights, and no adults present. It is used by both `test_csv_io.py` and `test_cli.py`.

## Running the suite

```bash
.venv/bin/pytest -v
.venv/bin/pytest -v --tb=short   # shorter traces
.venv/bin/pytest -k "flights"    # only flights-related tests
```

## Coverage

Run with pytest-cov to check coverage:

```bash
.venv/bin/pytest --cov=src/darkwing --cov-report=term-missing -v
```

Target: ≥ 90% on `src/darkwing/`.
