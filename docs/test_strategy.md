# Test Strategy

This document describes how the system is validated. The strategy is deliberately modest: MVP1 is a small system and the tests should match.

## Goals

1. **Every schema rule is covered by at least one test.** A form change that breaks a field's validation should be caught by a failing test, not by a 4xx response in production.
2. **The submission code path is exercised against a mocked HTTP boundary, not a real one.** The real Apps Script is exercised by the human in the tutorial; CI does not depend on it.
3. **The auth code path is exercised against a mocked `gcloud` CLI, not a real one.** Same reasoning.
4. **Coverage is ≥ 90% on `src/darkwing/`.** The CLI and the notebook façade are thin wrappers and are exercised by the integration test.

## What is in the suite

### `tests/test_schema.py` — the Golden Schema

One test per rule, with a positive case and (where applicable) a negative case.

- `UUID` is a valid UUID string.
- `TimestampUTC` is a tz-aware ISO-8601 timestamp in UTC.
- `date_str` matches `M/D/YYYY` (e.g. `6/15/2026`).
- `hour` is an integer in `[0, 23]`.
- `minutes_past_hour` is one of `{0, 20, 40}`.
- `num_adults` is a non-negative integer ≤ 10 (the form's max).
- `nesting_stage` is one of the form's five enum values.
- `bill_use` is one of the form's seven enum values.
- `flights` is a list of 0–3 strings, each from the form's four enum values.
- `num_near_nest` is a non-negative integer.
- `awake` is one of the form's four enum values (`Yes`, `No`, `Maybe`, `No adults present`).
- `notes` is a string (may be empty).
- The batch-level uniqueness check raises on a duplicate `(uuid, timestamp_utc)` pair.

### `tests/test_csv_io.py` — CSV I/O

- `read_rows` yields one dict per non-empty line and tolerates a leading UTF-8 BOM.
- `validate_csv_file` returns `(records, errors)`; one bad row in a 4-row file produces 3 records and 1 error.
- `append_submission_log` is append-only; two calls produce two JSON lines.

### `tests/test_auth.py` — gcloud token retrieval

- `get_token` shells out to `gcloud auth print-access-token` and strips the trailing newline.
- `get_token` caches the token for 50 minutes (verified with an injected clock).
- `get_token` raises a typed `GcloudAuthError` on non-zero exit.
- `get_token` does not invoke the subprocess when a cached token is fresh.

### `tests/test_form_submit.py` — POST behavior

- `submit_one` calls `requests.post` with the configured URL, the bearer header, and `Content-Type: application/json`.
- The request body equals `record.to_form_payload()`.
- A 200 with `{"status": "success"}` returns a `SubmitResult` with `ok=True`.
- A 401 triggers a token refresh and a single retry; a second 401 raises.
- A 5xx triggers exponential backoff with up to 3 attempts, then raises.
- A 4xx (non-401) is a row-level skip — no retry, the row is logged with the response body.
- A network exception is treated as a 5xx (retried with backoff).

### `tests/test_cli.py` — end-to-end façade

- `validate` command prints a summary and exits 0.
- `submit --dry-run` does not call `requests.post`.
- `submit` without `--dry-run` calls `requests.post` once per non-skipped row.
- `submit` resumes from `submitted_log.jsonl` (re-running skips already-submitted rows).
- `submit --force` ignores the log and re-submits.

## What is *not* in the suite

- **No test against a real Apps Script.** CI does not have credentials; the test boundary is the `requests.post` call, fully mocked. The real flow is validated by the human in the [Tutorial](./tutorial-1.md).
- **No test against a real `gcloud` CLI.** Same reason.
- **No load test, no fuzz test, no property test.** The batch size is bounded (≤ 250 rows per the realistic workload) and the input format is fixed. The marginal value of a property test is low; the value of a test that catches a form-title typo is high.
- **No end-to-end test that uses a notebook.** The notebook is a thin wrapper around the same modules that the CLI uses; if the modules' tests pass, the notebook works. A `nbconvert` smoke test is a possible future addition.

## How to run the suite

```bash
.venv/bin/pytest -v
.venv/bin/pytest --cov=darkwing --cov-report=term-missing
```

A clean run reports all tests passing and a coverage report showing ≥ 90% line coverage on `src/darkwing/`.

## When the test suite needs to grow

- The form changes (titles, item types, allowed values). Update `tests/test_schema.py` and `to_form_payload()` in lockstep.
- A new submission field is added. Add a test before adding the field; add the field; add the test for the field. TDD.
- A new error path is added (e.g. a 429 rate-limit response). Add a test that asserts the new behavior; add the behavior; verify the test passes.
- A second submitter is added. Add a CLI flag and a test that exercises the new flag.
