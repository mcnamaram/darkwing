# Test Strategy

> Last updated: 2026-08-15.

## Philosophy

- **Fast, deterministic unit tests** are the default — no network, no browser, no live Google Form.
- **Dry-run flows** are tested without ever launching Chromium.
- **Browser automation** is tested by mocking `load_form` and `submit_observation`; real browser runs happen manually (`DARKWING_HEADLESS=false`) during smoke testing.

## What's covered (95 tests)

| Area | File | What's tested |
| --- | --- | --- |
| Schema | `tests/test_schema.py` | Validation of every field, short-code lookups, defaults, error messages |
| CSV I/O | `tests/test_csv_io.py` | Reading valid/invalid CSVs, multi-value splitting (`;`), BOM, blank lines |
| Submission log & resume | `tests/test_csv_io.py` | Log write/read shape (`{record, status, error, timestamp}`), append behavior, resume-key extraction (success-only, malformed-line tolerance, key stability) |
| Form submit | `tests/test_form_submit.py` | `dry_run` short-circuits (never launches browser), per-record error capture, multiple records |
| CLI | `tests/test_cli.py` | `validate` exit codes, `submit --dry-run` output and no-log guarantee, log writing on real submit, resume skipping/retrying, `--no-resume`, partial-failure exit code |

## What's NOT covered

- **Live Google Form submission.** No CI job posts to the real form. Done manually via `DARKWING_HEADLESS=false darkwing submit`.
- **Google login** — a one-time manual step; the persistent profile (`google_profile/`) holds the session.

## Running tests

```bash
.venv/bin/pytest            # full suite
.venv/bin/pytest tests/test_schema.py -v   # single file
```

## Browser smoke procedure

1. `cp .env.example .env` and set `DARKWING_FORM_URL` + `DARKWING_SUBMITTER_NAME`.
2. `DARKWING_HEADLESS=false .venv/bin/darkwing submit tests/fixtures/sample_observation.csv`
3. Watch the browser fill the form.
4. Verify the form's response spreadsheet has a new row.
